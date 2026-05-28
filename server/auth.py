# server/auth.py
import json
import time
import random
import socket
import base64
from datetime import datetime, timedelta
from typing import Optional, Tuple

from utils import decode_base64
from security import SecurityValidator, SimpleHash
from logger import logger


class AuthManager:
    """Управление аутентификацией и авторизацией пользователей"""
    
    def __init__(self, server):
        self.server = server
        self.recovery_codes: dict = {}
        self.login_attempts: dict = {}
        self.recovery_attempts: dict = {}
        self.code_expiry: dict = {}
        self.max_login_attempts = 5
        self.login_block_time = 300  # 5 минут
        self.recovery_code_lifetime = 600  # 10 минут
    
    def check_login_attempts(self, ip: str) -> Tuple[bool, int]:
        """Проверка количества попыток входа с IP"""
        now = time.time()
        
        if ip in self.login_attempts:
            data = self.login_attempts[ip]
            
            # Сброс после блокировки
            if data.get('blocked_until', 0) > now:
                remaining = int(data['blocked_until'] - now)
                return False, remaining
            
            # Сброс счетчика через 5 минут после последней попытки
            if now - data.get('last_attempt', 0) > self.login_block_time:
                self.login_attempts[ip] = {'count': 1, 'last_attempt': now}
                return True, 0
            
            # Проверка лимита
            if data.get('count', 0) >= self.max_login_attempts:
                self.login_attempts[ip]['blocked_until'] = now + self.login_block_time
                return False, self.login_block_time
            
            self.login_attempts[ip]['count'] = data.get('count', 0) + 1
            self.login_attempts[ip]['last_attempt'] = now
        else:
            self.login_attempts[ip] = {'count': 1, 'last_attempt': now}
        
        return True, 0
    
    def reset_login_attempts(self, ip: str):
        """Сброс попыток входа после успешной авторизации"""
        if ip in self.login_attempts:
            del self.login_attempts[ip]
    
    def generate_recovery_code(self, username: str) -> str:
        """Генерация кода восстановления"""
        code = str(random.randint(100000, 999999))
        self.recovery_codes[username] = code
        self.code_expiry[username] = time.time() + self.recovery_code_lifetime
        return code
    
    def verify_recovery_code(self, username: str, code: str) -> bool:
        """Проверка кода восстановления"""
        if username not in self.recovery_codes:
            return False
        
        if username in self.code_expiry and time.time() > self.code_expiry[username]:
            del self.recovery_codes[username]
            del self.code_expiry[username]
            return False
        
        if self.recovery_codes.get(username) == code:
            return True
        
        return False
    
    def clear_recovery_code(self, username: str):
        """Очистка кода восстановления"""
        if username in self.recovery_codes:
            del self.recovery_codes[username]
        if username in self.code_expiry:
            del self.code_expiry[username]
    
    def send_offline_messages_on_login(self, client, username: str, nickname: str):
        """Отправка оффлайн-сообщений при входе пользователя"""
        try:
            offline_messages = self.server.storage.get_offline_messages(username)
            
            if offline_messages:
                logger.info(f"Sending {len(offline_messages)} offline messages to {username}")
                
                for msg in offline_messages:
                    self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                        "type": "private_message",
                        "from": msg['sender'],
                        "text": msg['message'],
                        "time": msg['timestamp'][11:16] if len(msg['timestamp']) > 16 else msg['timestamp']
                    }, ensure_ascii=False))
                
                msg_ids = [m['id'] for m in offline_messages]
                self.server.storage.mark_offline_messages_delivered(msg_ids)
                
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                    "type": "notification",
                    "text": f"📬 Доставлено {len(offline_messages)} offline сообщений"
                }, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Failed to send offline messages: {e}")
    
    def handle_auth_loop(self, client: socket.socket, addr: tuple):
        """Основной цикл аутентификации"""
        ip = addr[0]
        auth_attempts = 0
        max_auth_attempts = 5
        
        # Проверка бана
        if self.server.storage.is_banned(ip):
            self.server.network.send_to_client(client, "BANNED\n")
            client.close()
            logger.warning(f"Banned IP attempted connection: {ip}")
            return
        
        while auth_attempts < max_auth_attempts and self.server.running:
            try:
                client.settimeout(60)
                data = client.recv(4096).decode('utf-8').strip()
                if not data:
                    break
                
                parts = data.split('|')
                action = parts[0]
                
                # ========== ЛОГИН ==========
                if action == "LOGIN" and len(parts) == 3:
                    can_login, wait_time = self.check_login_attempts(ip)
                    if not can_login:
                        self.server.network.send_to_client(
                            client, f"AUTH_FAIL|Too many attempts, try again in {wait_time} seconds"
                        )
                        logger.warning(f"Login rate limit exceeded from {ip}")
                        break
                    
                    username = parts[1]
                    try:
                        password = base64.b64decode(parts[2]).decode('utf-8')
                    except Exception as e:
                        logger.warning(f"Invalid base64 password from {ip}: {e}")
                        self.server.network.send_to_client(client, "AUTH_FAIL|Invalid credentials format")
                        continue
                    
                    # Валидация
                    valid, err = SecurityValidator.validate_username(username)
                    if not valid:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|{err}")
                        continue
                    
                    user = self.server.storage.get_user(username)
                    if not user:
                        self.server.network.send_to_client(client, "AUTH_FAIL|Invalid username or password")
                        auth_attempts += 1
                        logger.warning(f"Login failed: user {username} not found from {ip}")
                        continue
                    
                    # Проверка пароля
                    salt = user.get('salt', '')
                    expected_hash = user.get('password_hash', '')
                    
                    if not SimpleHash.verify_password(password, salt, expected_hash):
                        self.server.network.send_to_client(client, "AUTH_FAIL|Invalid username or password")
                        auth_attempts += 1
                        logger.warning(f"Login failed: wrong password for {username} from {ip}")
                        continue
                    
                    # Успешный логин
                    self.reset_login_attempts(ip)
                    nickname = user.get('nickname', username)
                    is_admin = bool(user.get('is_admin', False))
                    
                    self.server.network.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                    
                    self.server.clients.append(client)
                    self.server.client_data[client] = {
                        "nickname": nickname,
                        "username": username,
                        "addr": ip,
                        "is_admin": is_admin,
                        "login_time": datetime.now().isoformat()
                    }
                    
                    # Обновляем статус в БД
                    self.server.storage.update_user_status(username, True)
                    
                    # Отправляем историю сообщений
                    messages = self.server.storage.get_messages_history(100)
                    self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                        "type": "history",
                        "messages": messages,
                        "files": []
                    }, ensure_ascii=False))
                    
                    # Отправляем группы пользователя
                    user_id = user.get('id')
                    if user_id and hasattr(self.server.storage, 'get_user_groups'):
                        try:
                            user_groups = self.server.storage.get_user_groups(user_id)
                            if user_groups:
                                group_names = [g.get('name', '') for g in user_groups if g.get('name')]
                                if group_names:
                                    self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                                        "type": "user_groups",
                                        "groups": group_names
                                    }, ensure_ascii=False))
                        except Exception as e:
                            logger.error(f"Failed to send groups: {e}")
                    
                    # Отправляем оффлайн-сообщения
                    self.send_offline_messages_on_login(client, username, nickname)
                    
                    # Оповещаем всех о новом пользователе
                    self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
                        "type": "notification",
                        "text": f"{nickname} joined the chat!"
                    }, ensure_ascii=False), exclude_socket=client)
                    
                    # Отправляем обновленный список онлайн
                    online_users = [data['nickname'] for data in self.server.client_data.values()]
                    self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
                        "type": "online_users",
                        "users": online_users
                    }, ensure_ascii=False))
                    
                    logger.success(f"User logged in via socket: {nickname} ({username}) from {ip}")
                    
                    if hasattr(self.server, 'update_online_display'):
                        self.server.update_online_display()
                    
                    client.settimeout(None)
                    self.server.chat.handle_chat(client, nickname)
                    return
                
                # ========== РЕГИСТРАЦИЯ ==========
                elif action == "REGISTER" and len(parts) == 4:
                    can_login, wait_time = self.check_login_attempts(ip)
                    if not can_login:
                        self.server.network.send_to_client(
                            client, f"AUTH_FAIL|Too many registration attempts, try again in {wait_time} seconds"
                        )
                        break
                    
                    username = parts[1]
                    try:
                        password = base64.b64decode(parts[2]).decode('utf-8')
                    except Exception:
                        self.server.network.send_to_client(client, "AUTH_FAIL|Invalid credentials format")
                        continue
                    
                    nickname = parts[3]
                    
                    # Валидация
                    valid, err = SecurityValidator.validate_username(username)
                    if not valid:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|{err}")
                        continue
                    
                    valid, err = SecurityValidator.validate_password(password)
                    if not valid:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|{err}")
                        continue
                    
                    valid, err = SecurityValidator.validate_nickname(nickname)
                    if not valid:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|{err}")
                        continue
                    
                    existing = self.server.storage.get_user(username)
                    if existing:
                        self.server.network.send_to_client(client, "AUTH_FAIL|Username already exists")
                        logger.warning(f"Registration failed: username {username} already exists from {ip}")
                        continue
                    
                    # Создание пользователя
                    salt = SimpleHash.generate_salt()
                    password_hash = SimpleHash.hash_password(password, salt)
                    user_id = self.server.storage.create_user(username, password_hash, salt, is_admin=False)
                    
                    if not user_id:
                        self.server.network.send_to_client(client, "AUTH_FAIL|Registration error")
                        logger.error(f"Registration failed: database error for {username}")
                        continue
                    
                    # Установка никнейма
                    self.server.storage.update_user_nickname(username, nickname)
                    
                    self.reset_login_attempts(ip)
                    
                    self.server.network.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                    self.server.clients.append(client)
                    self.server.client_data[client] = {
                        "nickname": nickname,
                        "username": username,
                        "addr": ip,
                        "is_admin": False,
                        "login_time": datetime.now().isoformat()
                    }
                    
                    # Отправляем пустую историю для нового пользователя
                    self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                        "type": "history",
                        "messages": [],
                        "files": []
                    }, ensure_ascii=False))
                    
                    # Оповещаем всех о новом пользователе
                    self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
                        "type": "notification",
                        "text": f"{nickname} joined the chat!"
                    }, ensure_ascii=False), exclude_socket=client)
                    
                    logger.success(f"User registered via socket: {nickname} ({username}) from {ip}")
                    logger.save_event("registration", {"username": username, "ip": ip})
                    
                    if hasattr(self.server, 'update_online_display'):
                        self.server.update_online_display()
                    
                    client.settimeout(None)
                    self.server.chat.handle_chat(client, nickname)
                    return
                
                # ========== ВОССТАНОВЛЕНИЕ ПАРОЛЯ - ЗАПРОС КОДА ==========
                elif action == "FORGOT" and len(parts) == 2:
                    username = parts[1]
                    user = self.server.storage.get_user(username)
                    
                    if not user:
                        self.server.network.send_to_client(client, "RECOVERY_CODE|ERROR")
                        logger.warning(f"Password recovery failed: user {username} not found")
                        continue
                    
                    # Rate limiting для восстановления
                    if ip in self.recovery_attempts:
                        if time.time() - self.recovery_attempts[ip].get('last', 0) < 60:
                            remaining = 60 - (time.time() - self.recovery_attempts[ip]['last'])
                            self.server.network.send_to_client(
                                client, f"RECOVERY_CODE|RATE_LIMIT|Please wait {int(remaining)} seconds"
                            )
                            continue
                    
                    code = self.generate_recovery_code(username)
                    self.recovery_attempts[ip] = {'last': time.time(), 'attempts': 1}
                    
                    self.server.network.send_to_client(client, f"RECOVERY_CODE|{code}")
                    logger.info(f"Recovery code for {username}: {code} (from {ip})")
                    logger.save_event("password_recovery", {"username": username, "ip": ip})
                    continue
                
                # ========== ВОССТАНОВЛЕНИЕ ПАРОЛЯ - ПРОВЕРКА КОДА ==========
                elif action == "VERIFY_CODE" and len(parts) == 3:
                    username = parts[1]
                    code = parts[2]
                    
                    if self.verify_recovery_code(username, code):
                        self.server.network.send_to_client(client, "VERIFY_SUCCESS")
                        logger.info(f"Recovery code verified for {username}")
                    else:
                        self.server.network.send_to_client(client, "VERIFY_FAIL")
                        logger.warning(f"Invalid recovery code for {username}")
                    continue
                
                # ========== ВОССТАНОВЛЕНИЕ ПАРОЛЯ - СБРОС ==========
                elif action == "RESET_PASSWORD" and len(parts) == 3:
                    username = parts[1]
                    try:
                        new_password = base64.b64decode(parts[2]).decode('utf-8')
                    except Exception:
                        self.server.network.send_to_client(client, "AUTH_FAIL|Invalid password format")
                        continue
                    
                    user = self.server.storage.get_user(username)
                    if not user:
                        self.server.network.send_to_client(client, "AUTH_FAIL|User not found")
                        continue
                    
                    valid, err = SecurityValidator.validate_password(new_password)
                    if not valid:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|{err}")
                        continue
                    
                    # Обновление пароля
                    salt = SimpleHash.generate_salt()
                    password_hash = SimpleHash.hash_password(new_password, salt)
                    
                    with self.server.storage.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            'UPDATE users SET password_hash = ?, salt = ? WHERE username = ?',
                            (password_hash, salt, username)
                        )
                    
                    self.clear_recovery_code(username)
                    self.server.network.send_to_client(client, "PASSWORD_RESET_OK")
                    logger.success(f"Password reset for {username} from {ip}")
                    logger.save_event("password_reset", {"username": username, "ip": ip})
                    continue
                
                # ========== СМЕНА ПАРОЛЯ (АВТОРИЗОВАННЫЙ ПОЛЬЗОВАТЕЛЬ) ==========
                elif action == "CHANGEPASS" and len(parts) == 4:
                    # Этот кейс обрабатывается в chat.py
                    # Здесь только для совместимости
                    self.server.network.send_to_client(client, "AUTH_FAIL|Use this command after login")
                    continue
                
                else:
                    self.server.network.send_to_client(client, "AUTH_FAIL|Unknown command")
                    auth_attempts += 1
                    logger.warning(f"Unknown auth command: {action} from {ip}")
                    
            except socket.timeout:
                logger.warning(f"Auth timeout for {ip}")
                break
            except ConnectionResetError:
                logger.warning(f"Connection reset by {ip}")
                break
            except UnicodeDecodeError as e:
                logger.warning(f"Unicode decode error from {ip}: {e}")
                self.server.network.send_to_client(client, "AUTH_FAIL|Invalid encoding")
                continue
            except Exception as e:
                logger.error(f"Auth error from {ip}: {e}")
                break
        
        # Очистка при неудачной аутентификации
        try:
            client.close()
        except:
            pass
        
        logger.connection(ip, "auth failed - disconnected")
    
    def get_auth_stats(self) -> dict:
        """Получение статистики по аутентификации"""
        return {
            "active_recovery_codes": len(self.recovery_codes),
            "blocked_ips": len([ip for ip, data in self.login_attempts.items() if data.get('blocked_until', 0) > time.time()]),
            "total_login_attempts": sum(data.get('count', 0) for data in self.login_attempts.values())
        }
    
    def cleanup_expired_data(self):
        """Очистка просроченных данных (вызывается периодически)"""
        now = time.time()
        
        # Очистка просроченных кодов восстановления
        expired_codes = [u for u, expiry in self.code_expiry.items() if expiry < now]
        for username in expired_codes:
            self.clear_recovery_code(username)
        
        # Очистка старых записей о попытках входа
        expired_attempts = []
        for ip, data in self.login_attempts.items():
            last_attempt = data.get('last_attempt', 0)
            if now - last_attempt > 3600:  # Через час удаляем
                expired_attempts.append(ip)
        
        for ip in expired_attempts:
            del self.login_attempts[ip]
        
        if expired_codes or expired_attempts:
            logger.debug(f"Cleaned up {len(expired_codes)} recovery codes and {len(expired_attempts)} login attempts")