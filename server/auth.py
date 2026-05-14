import json
import time
import random
import socket
from utils import hash_password, decode_base64
from security import SecurityValidator

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
                
                if action == "LOGIN" and len(parts) == 3:
                    if not self.check_login_attempts(ip):
                        self.server.network.send_to_client(client, "AUTH_FAIL|❌ Слишком много попыток, подожди")
                        break
                    
                    username = parts[1]
                    password = decode_base64(parts[2])
                    
                    valid, err = SecurityValidator.validate_username(username)
                    if not valid:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|❌ {err}")
                        continue
                    
                    user = self.server.storage.db.get_user_by_username(username)
                    if not user or user['password'] != hash_password(password):
                        self.server.network.send_to_client(client, "AUTH_FAIL|❌ Неверный логин или пароль")
                        auth_attempts += 1
                        continue
                    
                    nickname = user['nickname']
                    self.server.network.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                    self.server.clients.append(client)
                    self.server.client_data[client] = {"nickname": nickname, "username": username, "addr": ip}
                    
                    # Отправляем историю
                    messages = self.server.storage.get_messages_history(100)
                    self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "history", "messages": messages, "files": []}))
                    
                    # Группы
                    user_groups = self.server.storage.db.get_user_groups(user['id']) if hasattr(self.server.storage.db, 'get_user_groups') else []
                    for g in user_groups:
                        self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "user_groups", "groups": [g['name']]}))
                    
                    self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "notification", "text": f"{nickname} присоединился к чату!"}), exclude_socket=client)
                    self.server.log(f"👤 {nickname} вошёл | Онлайн: {len(self.server.clients)}")
                    self.server.root.after(0, self.server.update_online_display)
                    
                    client.settimeout(None)
                    self.server.chat.handle_chat(client, nickname)
                    return
                
                elif action == "REGISTER" and len(parts) == 4:
                    username = parts[1]
                    password = decode_base64(parts[2])
                    nickname = parts[3]
                    
                    valid, err = SecurityValidator.validate_username(username)
                    if not valid:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|❌ {err}")
                        continue
                    valid, err = SecurityValidator.validate_password(password)
                    if not valid:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|❌ {err}")
                        continue
                    valid, err = SecurityValidator.validate_nickname(nickname)
                    if not valid:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|❌ {err}")
                        continue
                    
                    existing = self.server.storage.db.get_user_by_username(username)
                    if existing:
                        self.server.network.send_to_client(client, "AUTH_FAIL|❌ Логин уже занят")
                        continue
                    
                    password_hash = hash_password(password)
                    self.server.storage.db.create_user(username, password_hash, nickname)
                    self.server.network.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                    self.server.clients.append(client)
                    self.server.client_data[client] = {"nickname": nickname, "username": username, "addr": ip}
                    
                    self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "history", "messages": [], "files": []}))
                    self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "notification", "text": f"{nickname} присоединился к чату!"}), exclude_socket=client)
                    self.server.log(f"👤 {nickname} зарегистрировался | Онлайн: {len(self.server.clients)}")
                    self.server.root.after(0, self.server.update_online_display)
                    
                    client.settimeout(None)
                    self.server.chat.handle_chat(client, nickname)
                    return
                
                elif action == "FORGOT" and len(parts) == 2:
                    username = parts[1]
                    code = str(random.randint(100000, 999999))
                    self.recovery_codes[username] = code
                    self.server.log(f"🔐 Код восстановления для {username}: {code}", "admin")
                    self.server.network.send_to_client(client, f"RECOVERY_CODE|{code}")
                
                elif action == "VERIFY_CODE" and len(parts) == 3:
                    username = parts[1]
                    code = parts[2]
                    if username in self.recovery_codes and self.recovery_codes[username] == code:
                        self.server.network.send_to_client(client, "VERIFY_SUCCESS")
                    else:
                        self.server.network.send_to_client(client, "VERIFY_FAIL")
                
                elif action == "RESET_PASSWORD" and len(parts) == 3:
                    username = parts[1]
                    new_password = decode_base64(parts[2])
                    user = self.server.storage.db.get_user_by_username(username)
                    if user:
                        self.server.storage.db.update_user_password(user['id'], hash_password(new_password))
                        self.server.network.send_to_client(client, "PASSWORD_RESET_OK")
                        self.server.log(f"🔐 Пароль для {username} сброшен")
                    else:
                        self.server.network.send_to_client(client, "AUTH_FAIL|❌ Пользователь не найден")
                
                else:
                    self.server.network.send_to_client(client, "AUTH_FAIL|❌ Неизвестная команда")
                    auth_attempts += 1
                    
            except socket.timeout:
                break
            except Exception as e:
                self.server.log(f"Ошибка авторизации: {e}", "error")
                break
        
        try:
            client.close()
        except:
            pass