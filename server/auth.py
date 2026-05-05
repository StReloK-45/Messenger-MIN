# server/auth.py
import json
import time
import random
import base64
import socket
from utils import hash_password, decode_base64

class AuthManager:
    def __init__(self, server):
        self.server = server
        self.recovery_codes = {}
    
    def handle_auth_loop(self, client, addr):
        auth_attempts = 0
        max_attempts = 5
        
        while auth_attempts < max_attempts and self.server.running:
            try:
                client.settimeout(60)
                auth_data = client.recv(4096).decode('utf-8').strip()
                
                if not auth_data:
                    break
                
                parts = auth_data.split('|')
                action = parts[0]
                
                if action == "LOGIN" and len(parts) >= 2:
                    self.server.log(f"🔑 Попытка входа: {parts[1]}", "system")
                elif action == "REGISTER" and len(parts) >= 2:
                    self.server.log(f"📝 Попытка регистрации: {parts[1]}", "system")
                
                if action == "LOGIN":
                    if len(parts) != 3:
                        self.server.network.send_to_client(client, "AUTH_FAIL|❌ Неверный формат запроса!")
                        auth_attempts += 1
                        continue
                    
                    username = parts[1]
                    password = decode_base64(parts[2])
                    success, result = self.login(username, password)
                    
                    if success:
                        nickname = result
                        self.server.network.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                        
                        self.server.clients.append(client)
                        self.server.client_data[client] = {"nickname": nickname, "username": username, "addr": addr[0]}
                        
                        # Отправляем историю общего чата
                        history_payload = "JSON_PAYLOAD:" + json.dumps({
                            "type": "history",
                            "messages": self.server.storage.messages_history[-100:],
                            "files": [f for f in self.server.storage.files_list if f.get('chat', 'general') == 'general']
                        }, ensure_ascii=True)
                        self.server.network.send_to_client(client, history_payload)
                        time.sleep(0.1)
                        
                        # Отправляем все личные чаты пользователя
                        private_chats_count = 0
                        for chat_id, messages in self.server.storage.private_messages.items():
                            if nickname in chat_id.split('|'):
                                other_user = chat_id.split('|')[0] if chat_id.split('|')[1] == nickname else chat_id.split('|')[1]
                                history_pm = "JSON_PAYLOAD:" + json.dumps({
                                    "type": "private_history",
                                    "target": other_user,
                                    "messages": messages
                                }, ensure_ascii=True)
                                self.server.network.send_to_client(client, history_pm)
                                private_chats_count += 1
                                time.sleep(0.05)
                        
                        self.server.log(f"📨 Отправлено {private_chats_count} личных чатов для {nickname}", "system")
                        
                        # Отправляем список друзей
                        friends_list = self.server.storage.get_friends(nickname)
                        friends_payload = "JSON_PAYLOAD:" + json.dumps({
                            "type": "friends_list",
                            "friends": friends_list
                        }, ensure_ascii=True)
                        self.server.network.send_to_client(client, friends_payload)
                        self.server.log(f"📨 Отправлен список друзей для {nickname}: {friends_list}", "system")
                        
                        # Отправляем список групп пользователя
                        user_groups = []
                        for group_name, group_data in self.server.storage.groups.items():
                            if nickname in group_data.get("members", []):
                                user_groups.append(group_name)
                                # Отправляем историю группы
                                group_history = "JSON_PAYLOAD:" + json.dumps({
                                    "type": "group_history",
                                    "group": group_name,
                                    "messages": group_data.get("messages", []),
                                    "files": group_data.get("files", [])
                                }, ensure_ascii=True)
                                self.server.network.send_to_client(client, group_history)
                                time.sleep(0.05)
                                # ОТПРАВЛЯЕМ СПИСОК УЧАСТНИКОВ ГРУППЫ (ЭТО НОВЫЙ КОД)
                                group_members = "JSON_PAYLOAD:" + json.dumps({
                                    "type": "group_members",
                                    "group": group_name,
                                    "members": group_data.get("members", [])
                                }, ensure_ascii=True)
                                self.server.network.send_to_client(client, group_members)
                                time.sleep(0.05)
                        
                        groups_payload = "JSON_PAYLOAD:" + json.dumps({
                            "type": "user_groups",
                            "groups": user_groups
                        }, ensure_ascii=True)
                        self.server.network.send_to_client(client, groups_payload)
                        self.server.log(f"📨 Отправлено {len(user_groups)} групп для {nickname}", "system")
                        
                        client.settimeout(None)
                        self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps(
                            {"type": "notification", "text": f"{nickname} присоединился к чату!"}, ensure_ascii=False),
                            exclude_socket=client)
                        self.server.log(f"👤 {nickname} (@{username}) вошёл | Онлайн: {len(self.server.clients)}", "online")
                        self.server.root.after(0, self.server.update_online_display)
                        
                        self.server.chat.handle_chat(client, nickname)
                        return
                    else:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|{result}")
                        auth_attempts += 1
                
                elif action == "REGISTER":
                    if len(parts) != 4:
                        self.server.network.send_to_client(client, "AUTH_FAIL|❌ Неверный формат запроса!")
                        auth_attempts += 1
                        continue
                    
                    username = parts[1]
                    password = decode_base64(parts[2])
                    nickname = parts[3]
                    
                    success, result = self.register(username, password, nickname)
                    
                    if success:
                        self.server.network.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                        
                        self.server.clients.append(client)
                        self.server.client_data[client] = {"nickname": nickname, "username": username, "addr": addr[0]}
                        
                        self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                            "type": "history", "messages": [], "files": []}, ensure_ascii=True))
                        time.sleep(0.1)
                        
                        # Отправляем список друзей (для нового пользователя - пустой)
                        friends_payload = "JSON_PAYLOAD:" + json.dumps({
                            "type": "friends_list",
                            "friends": []
                        }, ensure_ascii=True)
                        self.server.network.send_to_client(client, friends_payload)
                        
                        # Отправляем список групп (для нового пользователя - пустой)
                        groups_payload = "JSON_PAYLOAD:" + json.dumps({
                            "type": "user_groups",
                            "groups": []
                        }, ensure_ascii=True)
                        self.server.network.send_to_client(client, groups_payload)
                        
                        client.settimeout(None)
                        self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps(
                            {"type": "notification", "text": f"{nickname} присоединился к чату!"}, ensure_ascii=False),
                            exclude_socket=client)
                        self.server.log(f"👤 {nickname} (@{username}) зарегистрировался | Онлайн: {len(self.server.clients)}", "system")
                        self.server.root.after(0, self.server.update_online_display)
                        
                        self.server.chat.handle_chat(client, nickname)
                        return
                    else:
                        self.server.network.send_to_client(client, f"AUTH_FAIL|{result}")
                        auth_attempts += 1
                
                elif action == "GET_PM_HISTORY" and len(parts) >= 2:
                    target = parts[1]
                    nickname = self.server.client_data.get(client, {}).get('nickname', '')
                    chat_id = "|".join(sorted([nickname, target]))
                    messages = self.server.storage.private_messages.get(chat_id, [])
                    
                    history_pm = "JSON_PAYLOAD:" + json.dumps({
                        "type": "private_history",
                        "target": target,
                        "messages": messages
                    }, ensure_ascii=True)
                    self.server.network.send_to_client(client, history_pm)
                    self.server.log(f"📨 Отправлена история ЛС с {target} ({len(messages)} сообщений)", "system")
                
                elif action == "FORGOT" and len(parts) >= 2:
                    username = parts[1]
                    code = self.generate_recovery_code(username)
                    if code:
                        self.server.log("="*50, "admin")
                        self.server.log(f"🔐 ЗАПРОС ВОССТАНОВЛЕНИЯ ПАРОЛЯ", "admin")
                        self.server.log(f"👤 Логин: {username}", "admin")
                        self.server.log(f"🔑 Код восстановления: {code}", "admin")
                        self.server.log("="*50, "admin")
                        self.server.network.send_to_client(client, f"RECOVERY_CODE|{code}")
                    else:
                        self.server.network.send_to_client(client, "RECOVERY_CODE|ERROR")
                
                elif action == "VERIFY_CODE" and len(parts) >= 3:
                    username = parts[1]
                    code = parts[2]
                    if username in self.recovery_codes and self.recovery_codes[username] == code:
                        self.server.network.send_to_client(client, "VERIFY_SUCCESS")
                    else:
                        self.server.network.send_to_client(client, "VERIFY_FAIL|❌ Неверный код!")
                
                elif action == "RESET_PASSWORD" and len(parts) >= 3:
                    username = parts[1]
                    new_password = decode_base64(parts[2])
                    if username in self.server.storage.users_db:
                        self.server.storage.users_db[username]["password"] = hash_password(new_password)
                        self.server.storage.save_users()
                        self.server.network.send_to_client(client, "PASSWORD_RESET_OK")
                        self.server.log(f"🔐 Пароль для {username} сброшен", "admin")
                    else:
                        self.server.network.send_to_client(client, "AUTH_FAIL|❌ Пользователь не найден!")
                
                else:
                    self.server.network.send_to_client(client, "AUTH_FAIL|❌ Неизвестная команда!")
                    auth_attempts += 1
                    
            except socket.timeout:
                self.server.log(f"⏰ Таймаут авторизации для {addr}", "error")
                break
            except Exception as e:
                self.server.log(f"❌ Ошибка авторизации: {e}", "error")
                break
        
        try:
            client.close()
        except:
            pass
    
    def forgot_password(self, username, client):
        code = self.generate_recovery_code(username)
        if code:
            self.server.log("="*50, "admin")
            self.server.log(f"🔐 ЗАПРОС ВОССТАНОВЛЕНИЯ ПАРОЛЯ", "admin")
            self.server.log(f"👤 Логин: {username}", "admin")
            self.server.log(f"🔑 Код восстановления: {code}", "admin")
            self.server.log("="*50, "admin")
            self.server.network.send_to_client(client, f"RECOVERY_CODE|{code}")
        else:
            self.server.network.send_to_client(client, "RECOVERY_CODE|ERROR")
    
    def generate_recovery_code(self, username):
        if username not in self.server.storage.users_db:
            return None
        code = str(random.randint(100000, 999999))
        self.recovery_codes[username] = code
        return code
    
    def login(self, username, password):
        if username not in self.server.storage.users_db:
            return False, "❌ Пользователь с таким логином не найден!"
        if self.server.storage.users_db[username]["password"] != hash_password(password):
            return False, "❌ Неверный пароль!"
        return True, self.server.storage.users_db[username]["nickname"]
    
    def register(self, username, password, nickname):
        if username in self.server.storage.users_db:
            return False, "❌ Логин уже занят!"
        if len(username) < 3:
            return False, "❌ Логин должен быть не менее 3 символов!"
        if len(username) > 20:
            return False, "❌ Логин должен быть не более 20 символов!"
        if len(password) < 4:
            return False, "❌ Пароль должен быть не менее 4 символов!"
        if not nickname:
            nickname = username
        
        self.server.storage.users_db[username] = {
            "password": hash_password(password),
            "nickname": nickname
        }
        self.server.storage.save_users()
        return True, "✅ Регистрация успешна!"
    
    @property
    def users_db(self):
        return self.server.storage.users_db