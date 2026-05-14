# server/auth.py
import json
import time
import random
import socket
from utils import decode_base64
from security import SecurityValidator, SimpleHash
from logger import logger

class AuthManager:
    def __init__(self, server):
        self.server = server
        self.recovery_codes = {}
        self.login_attempts = {}
    
    def check_login_attempts(self, ip):
        now = time.time()
        if ip in self.login_attempts:
            if now - self.login_attempts[ip]['last'] > 300:
                self.login_attempts[ip] = {'count': 1, 'last': now}
                return True
            if self.login_attempts[ip]['count'] >= 5:
                return False
            self.login_attempts[ip]['count'] += 1
            self.login_attempts[ip]['last'] = now
        else:
            self.login_attempts[ip] = {'count': 1, 'last': now}
        return True
    
    def handle_auth_loop(self, client, addr):
        ip = addr[0]
        auth_attempts = 0
        
        while auth_attempts < 5 and self.server.running:
            try:
                client.settimeout(60)
                data = client.recv(4096).decode('utf-8').strip()
                if not data:
                    break
                
                parts = data.split('|')
                action = parts[0]
                
                # ========== ЛОГИН ==========
                if action == "LOGIN" and len(parts) == 3:
                    if not self.check_login_attempts(ip):
                        self.server.network.send_to_client(client, "AUTH_FAIL|Too many attempts, wait")
                        break
                    
                    username = parts[1]
                    password = decode_base64(parts[2])
                    
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
                    
                    # Проверка пароля через SimpleHash (совместимость с API)
                    salt = user.get('salt', '')
                    expected_hash = user.get('password_hash', '')
                    
                    if not SimpleHash.verify_password(password, salt, expected_hash):
                        self.server.network.send_to_client(client, "AUTH_FAIL|Invalid username or password")
                        auth_attempts += 1
                        logger.warning(f"Login failed: wrong password for {username} from {ip}")
                        continue
                    
                    # Успешный логин
                    nickname = user.get('username', username)
                    self.server.network.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                    self.server.clients.append(client)
                    self.server.client_data[client] = {"nickname": nickname, "username": username, "addr": ip}
                    
                    # Отправляем историю сообщений
                    messages = self.server.storage.get_messages_history(100)
                    self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                        "type": "history", 
                        "messages": messages, 
                        "files": []
                    }, ensure_ascii=False))
                    
                    # Отправляем группы пользователя
                    if hasattr(self.server.storage, 'get_user_groups'):
                        try:
                            user_groups = self.server.storage.get_user_groups(user['id'])
                            for g in user_groups:
                                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                                    "type": "user_groups", 
                                    "groups": [g['name']]
                                }, ensure_ascii=False))
                        except Exception as e:
                            logger.error(f"Failed to send groups: {e}")
                    
                    # Оповещаем всех о новом пользователе
                    self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
                        "type": "notification", 
                        "text": f"{nickname} joined the chat!"
                    }, ensure_ascii=False), exclude_socket=client)
                    
                    logger.success(f"User logged in via socket: {nickname} ({username}) from {ip}")
                    
                    if hasattr(self.server, 'update_online_display'):
                        self.server.update_online_display()
                    
                    client.settimeout(None)
                    self.server.chat.handle_chat(client, nickname)
                    return
                
                # ========== РЕГИСТРАЦИЯ ==========
                elif action == "REGISTER" and len(parts) == 4:
                    username = parts[1]
                    password = decode_base64(parts[2])
                    nickname = parts[3]
                    
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
                    
                    # Создаём пользователя с хешированием через SimpleHash
                    salt = SimpleHash.generate_salt()
                    password_hash = SimpleHash.hash_password(password, salt)
                    user_id = self.server.storage.create_user(username, password_hash, salt, is_admin=False)
                    
                    if not user_id:
                        self.server.network.send_to_client(client, "AUTH_FAIL|Registration error")
                        logger.error(f"Registration failed: database error for {username}")
                        continue
                    
                    self.server.network.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                    self.server.clients.append(client)
                    self.server.client_data[client] = {"nickname": nickname, "username": username, "addr": ip}
                    
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
                    
                    if hasattr(self.server, 'update_online_display'):
                        self.server.update_online_display()
                    
                    client.settimeout(None)
                    self.server.chat.handle_chat(client, nickname)
                    return
                
                # ========== ВОССТАНОВЛЕНИЕ ПАРОЛЯ ==========
                elif action == "FORGOT" and len(parts) == 2:
                    username = parts[1]
                    user = self.server.storage.get_user(username)
                    
                    if not user:
                        self.server.network.send_to_client(client, "RECOVERY_CODE|ERROR")
                        logger.warning(f"Password recovery failed: user {username} not found")
                        continue
                    
                    code = str(random.randint(100000, 999999))
                    self.recovery_codes[username] = code
                    self.server.network.send_to_client(client, f"RECOVERY_CODE|{code}")
                    logger.info(f"Recovery code for {username}: {code} (check logs)")
                    continue
                
                elif action == "VERIFY_CODE" and len(parts) == 3:
                    username = parts[1]
                    code = parts[2]
                    
                    if username in self.recovery_codes and self.recovery_codes[username] == code:
                        self.server.network.send_to_client(client, "VERIFY_SUCCESS")
                        logger.info(f"Recovery code verified for {username}")
                    else:
                        self.server.network.send_to_client(client, "VERIFY_FAIL")
                        logger.warning(f"Invalid recovery code for {username}")
                    continue
                
                elif action == "RESET_PASSWORD" and len(parts) == 3:
                    username = parts[1]
                    new_password = decode_base64(parts[2])
                    
                    user = self.server.storage.get_user(username)
                    if not user:
                        self.server.network.send_to_client(client, "AUTH_FAIL|User not found")
                        continue
                    
                    # Обновляем пароль через SimpleHash
                    salt = SimpleHash.generate_salt()
                    password_hash = SimpleHash.hash_password(new_password, salt)
                    
                    with self.server.storage.db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('UPDATE users SET password_hash = ?, salt = ? WHERE username = ?', 
                                     (password_hash, salt, username))
                    
                    self.server.network.send_to_client(client, "PASSWORD_RESET_OK")
                    logger.success(f"Password reset for {username}")
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
            except Exception as e:
                logger.error(f"Auth error: {e}")
                break
        
        try:
            client.close()
        except:
            pass
        
        logger.connection(ip, "auth failed - disconnected")