import socket
import threading
import os
from datetime import datetime, timedelta
import hashlib
import json
import base64
import time
import struct
import re
import random

# ========== АБСОЛЮТНЫЕ ПУТИ К ФАЙЛАМ ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
CHAT_HISTORY_FILE = os.path.join(BASE_DIR, "chat_history.json")
PRIVATE_MESSAGES_FILE = os.path.join(BASE_DIR, "private_messages.json")
BANNED_IPS_FILE = os.path.join(BASE_DIR, "banned_ips.json")
RECEIVED_FILES_DIR = os.path.join(BASE_DIR, "received_files")
# =============================================

class ChatServer:
    VERSION = "0.39.1"
    
    def __init__(self, host='0.0.0.0', port=5555, file_port=5556):
        self.host = host
        self.port = port
        self.file_port = file_port
        self.clients = []
        self.client_data = {}
        self.messages_history = []
        self.private_messages = {}
        self.files_list = []
        self.message_counter = 0
        self.lock = threading.Lock()
        self.users_db = {}
        self.banned_ips = set()
        self.muted_users = {}
        self.running = True
        self.recovery_codes = {}
        
        if not os.path.exists(RECEIVED_FILES_DIR):
            os.makedirs(RECEIVED_FILES_DIR)
            print(f"📁 Создана папка: {RECEIVED_FILES_DIR}")
        
        self.load_data()
        self.load_bans()
        
        self.start_chat_server()
        self.start_file_server()
        
        local_ip = self.get_local_ip()
        print("="*70)
        print(f"🚀 СЕРВЕР ЧАТА ЗАПУЩЕН (v{self.VERSION})")
        print(f"📂 Рабочая папка: {BASE_DIR}")
        print(f"📍 IP адрес сервера: {local_ip}")
        print(f"💬 Чат сервер: {self.port}")
        print(f"📁 Файловый сервер: {self.file_port}")
        print("="*70)
        print("💡 Доступные команды администратора:")
        print("   /kick <ник> - кикнуть пользователя")
        print("   /ban <ник> - забанить пользователя по IP")
        print("   /unban <IP> - разбанить IP")
        print("   /mute <ник> <минуты> - замутить пользователя")
        print("   /unmute <ник> - снять мут")
        print("   /delmsg <id> - удалить сообщение")
        print("   /delfile <id> - удалить файл")
        print("   /users - показать онлайн пользователей")
        print("   /banned - показать забаненные IP")
        print("   /history - показать последние 10 сообщений")
        print("   /clearusers - очистить базу пользователей")
        print("   /clearhistory - очистить историю чата")
        print("="*70)
        print("Ожидание подключений...\n")
        
        self.console_handler()
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def get_chat_id(self, user1, user2):
        """Создаёт уникальный ID для чата между двумя пользователями"""
        return "|".join(sorted([user1, user2]))
    
    def load_data(self):
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    self.users_db = json.load(f)
                print(f"✅ Загружено {len(self.users_db)} пользователей")
            except Exception as e:
                print(f"❌ Ошибка загрузки пользователей: {e}")
        
        if os.path.exists(CHAT_HISTORY_FILE):
            try:
                with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.messages_history = data.get('messages', [])
                    self.files_list = data.get('files', [])
                    self.message_counter = data.get('counter', 0)
                print(f"✅ Загружено {len(self.messages_history)} сообщений")
                print(f"✅ Загружено {len(self.files_list)} файлов")
            except Exception as e:
                print(f"❌ Ошибка загрузки истории: {e}")
                self.messages_history = []
                self.files_list = []
                self.message_counter = 0
        
        if os.path.exists(PRIVATE_MESSAGES_FILE):
            try:
                with open(PRIVATE_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                    self.private_messages = json.load(f)
                total_pm = sum(len(msgs) for msgs in self.private_messages.values())
                print(f"✅ Загружено {total_pm} личных сообщений")
            except Exception as e:
                print(f"❌ Ошибка загрузки личных сообщений: {e}")
                self.private_messages = {}
                
    def load_bans(self):
        if os.path.exists(BANNED_IPS_FILE):
            try:
                with open(BANNED_IPS_FILE, 'r') as f:
                    self.banned_ips = set(json.load(f))
                print(f"✅ Загружено {len(self.banned_ips)} забаненных IP")
            except Exception as e:
                print(f"❌ Ошибка загрузки банов: {e}")

    def save_bans(self):
        try:
            with open(BANNED_IPS_FILE, 'w') as f:
                json.dump(list(self.banned_ips), f)
        except Exception as e:
            print(f"❌ Ошибка сохранения банов: {e}")

    def save_users(self):
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.users_db, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения пользователей: {e}")
    
    def save_history(self):
        try:
            clean_files = []
            for f in self.files_list:
                clean_files.append({
                    'id': str(f.get('id', '')),
                    'name': str(f.get('name', '')),
                    'path': str(f.get('path', '')),
                    'size': int(f.get('size', 0)),
                    'sender': str(f.get('sender', '')),
                    'date': str(f.get('date', '')),
                    'chat': str(f.get('chat', 'general'))
                })
            
            clean_messages = []
            for m in self.messages_history:
                clean_messages.append({
                    'id': str(m.get('id', '')),
                    'sender': str(m.get('sender', '')),
                    'text': str(m.get('text', '')),
                    'time': str(m.get('time', '')),
                    'edited': bool(m.get('edited', False))
                })
            
            data = {
                'messages': clean_messages,
                'files': clean_files,
                'counter': int(self.message_counter)
            }
            
            json_str = json.dumps(data, ensure_ascii=True, indent=2)
            
            with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
                f.write(json_str)
        except Exception as e:
            print(f"❌ Ошибка сохранения истории: {e}")
    
    def save_private_messages(self):
        try:
            json_str = json.dumps(self.private_messages, ensure_ascii=True, indent=2)
            with open(PRIVATE_MESSAGES_FILE, 'w', encoding='utf-8') as f:
                f.write(json_str)
        except Exception as e:
            print(f"❌ Ошибка сохранения личных сообщений: {e}")
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()[:32]
    
    def decode_base64(self, encoded):
        return base64.b64decode(encoded.encode()).decode()
    
    def register_user(self, username, password, nickname):
        if username in self.users_db:
            return False, "❌ Логин уже занят! Выберите другой."
        if len(username) < 3:
            return False, "❌ Логин должен быть не менее 3 символов!"
        if len(username) > 20:
            return False, "❌ Логин должен быть не более 20 символов!"
        if len(password) < 4:
            return False, "❌ Пароль должен быть не менее 4 символов!"
        if not nickname or nickname.strip() == "":
            nickname = username
        
        self.users_db[username] = {
            "password": self.hash_password(password),
            "nickname": nickname
        }
        self.save_users()
        return True, "✅ Регистрация успешна!"
    
    def login_user(self, username, password):
        if username not in self.users_db:
            return False, "❌ Пользователь с таким логином не найден!"
        if self.users_db[username]["password"] != self.hash_password(password):
            return False, "❌ Неверный пароль!"
        return True, self.users_db[username]["nickname"]
    
    def broadcast(self, message, exclude_socket=None):
        with self.lock:
            message_bytes = (message + "\n").encode('utf-8')
            for client in self.clients[:]:
                if client != exclude_socket:
                    try:
                        client.send(message_bytes)
                    except:
                        self.remove_client(client)
    
    def send_to_client(self, client, data):
        try:
            client.send((data + "\n").encode('utf-8'))
        except:
            self.remove_client(client)

    def remove_client(self, client):
        if client in self.clients:
            data = self.client_data.get(client, {})
            name = data.get('nickname', 'Unknown')
            self.clients.remove(client)
            if client in self.client_data:
                del self.client_data[client]
            try:
                client.close()
            except:
                pass
            self.broadcast(json.dumps({"type": "notification", "text": f"{name} покинул чат"}, ensure_ascii=False))
            print(f"   👤 {name} отключился | Онлайн: {len(self.clients)}")
    
    def kick_user(self, nickname, reason="Кикнут администратором"):
        for client, data in list(self.client_data.items()):
            if data['nickname'] == nickname:
                self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "kicked", "reason": reason}, ensure_ascii=False))
                time.sleep(0.1)
                self.remove_client(client)
                print(f"🛡️ Пользователь {nickname} кикнут. Причина: {reason}")
                return True
        print(f"❌ Пользователь {nickname} не найден в онлайне")
        return False
    
    def ban_user(self, nickname, reason="Забанен администратором"):
        for client, data in list(self.client_data.items()):
            if data['nickname'] == nickname:
                ip = data['addr']
                self.banned_ips.add(ip)
                self.save_bans()
                self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "banned", "reason": reason}, ensure_ascii=False))
                time.sleep(0.1)
                self.remove_client(client)
                print(f"🛡️ Пользователь {nickname} забанен (IP: {ip}). Причина: {reason}")
                return True
        print(f"❌ Пользователь {nickname} не найден в онлайне")
        return False
    
    def unban_ip(self, ip):
        if ip in self.banned_ips:
            self.banned_ips.remove(ip)
            self.save_bans()
            print(f"✅ IP {ip} разбанен")
            return True
        print(f"❌ IP {ip} не найден в списке банов")
        return False
    
    def mute_user(self, nickname, minutes):
        until = datetime.now() + timedelta(minutes=minutes)
        self.muted_users[nickname] = until
        self.broadcast(json.dumps({"type": "notification", "text": f"🔇 {nickname} получил мут на {minutes} мин."}, ensure_ascii=False))
        print(f"🛡️ Пользователь {nickname} замучен на {minutes} минут")
    
    def unmute_user(self, nickname):
        if nickname in self.muted_users:
            del self.muted_users[nickname]
            self.broadcast(json.dumps({"type": "notification", "text": f"🔈 Мут с {nickname} снят."}, ensure_ascii=False))
            print(f"🛡️ Мут с пользователя {nickname} снят")
            return True
        print(f"❌ Пользователь {nickname} не в муте")
        return False
    
    def delete_message(self, msg_id):
        for i, msg in enumerate(self.messages_history):
            if msg.get('id') == msg_id:
                deleted_msg = self.messages_history.pop(i)
                self.save_history()
                self.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "message_deleted", "id": msg_id}, ensure_ascii=False))
                print(f"🛡️ Сообщение {msg_id} удалено (автор: {deleted_msg.get('sender')})")
                return True
        print(f"❌ Сообщение с ID {msg_id} не найдено")
        return False
    
    def delete_file(self, file_id):
        for i, f in enumerate(self.files_list):
            if f['id'] == file_id:
                try:
                    os.remove(f['path'])
                except:
                    pass
                deleted_file = self.files_list.pop(i)
                self.save_history()
                self.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "file_deleted", "id": file_id}, ensure_ascii=False))
                print(f"🛡️ Файл {file_id} удалён (название: {deleted_file.get('name')})")
                return True
        print(f"❌ Файл с ID {file_id} не найден")
        return False
    
    def show_online_users(self):
        print("\n" + "="*50)
        print(f"👥 ОНЛАЙН ПОЛЬЗОВАТЕЛИ ({len(self.clients)}):")
        for client, data in self.client_data.items():
            nickname = data.get('nickname', 'Unknown')
            username = data.get('username', 'Unknown')
            addr = data.get('addr', 'Unknown')
            muted = "🔇" if nickname in self.muted_users else ""
            print(f"   {muted} {nickname} (@{username}) - {addr}")
        print("="*50 + "\n")
    
    def show_banned_ips(self):
        print("\n" + "="*50)
        print(f"🚫 ЗАБАНЕННЫЕ IP ({len(self.banned_ips)}):")
        for ip in self.banned_ips:
            print(f"   ❌ {ip}")
        print("="*50 + "\n")
    
    def show_recent_history(self, count=10):
        print("\n" + "="*50)
        print(f"📜 ПОСЛЕДНИЕ {min(count, len(self.messages_history))} СООБЩЕНИЙ:")
        for msg in self.messages_history[-count:]:
            sender = msg.get('sender', 'Unknown')
            text = msg.get('text', '')[:50]
            msg_id = msg.get('id', '')
            print(f"   [{msg_id}] {sender}: {text}...")
        print("="*50 + "\n")
    
    def console_handler(self):
        def handle_input():
            while self.running:
                try:
                    cmd = input().strip()
                    if not cmd:
                        continue
                    
                    parts = cmd.split()
                    if not parts:
                        continue
                    
                    command = parts[0].lower()
                    
                    if command == "/kick" and len(parts) >= 2:
                        nickname = parts[1]
                        reason = " ".join(parts[2:]) if len(parts) > 2 else "Кикнут администратором"
                        self.kick_user(nickname, reason)
                        
                    elif command == "/ban" and len(parts) >= 2:
                        nickname = parts[1]
                        reason = " ".join(parts[2:]) if len(parts) > 2 else "Забанен администратором"
                        self.ban_user(nickname, reason)
                        
                    elif command == "/unban" and len(parts) >= 2:
                        ip = parts[1]
                        self.unban_ip(ip)
                        
                    elif command == "/mute" and len(parts) >= 3:
                        nickname = parts[1]
                        try:
                            minutes = int(parts[2])
                            self.mute_user(nickname, minutes)
                        except:
                            print("❌ Укажите количество минут числом!")
                            
                    elif command == "/unmute" and len(parts) >= 2:
                        nickname = parts[1]
                        self.unmute_user(nickname)
                        
                    elif command == "/delmsg" and len(parts) >= 2:
                        msg_id = parts[1]
                        self.delete_message(msg_id)
                        
                    elif command == "/delfile" and len(parts) >= 2:
                        file_id = parts[1]
                        self.delete_file(file_id)
                        
                    elif command == "/users":
                        self.show_online_users()
                        
                    elif command == "/banned":
                        self.show_banned_ips()
                        
                    elif command == "/history":
                        count = int(parts[1]) if len(parts) > 1 else 10
                        self.show_recent_history(count)
                        
                    elif command == "/clearusers":
                        self.users_db = {}
                        self.save_users()
                        print("✅ База пользователей очищена")
                        
                    elif command == "/clearhistory":
                        self.messages_history = []
                        self.files_list = []
                        self.private_messages = {}
                        self.message_counter = 0
                        self.save_history()
                        self.save_private_messages()
                        print("✅ История чата очищена")
                        
                    elif command == "/help":
                        print("\n💡 Доступные команды:")
                        print("   /kick <ник> [причина]")
                        print("   /ban <ник> [причина]")
                        print("   /unban <IP>")
                        print("   /mute <ник> <минуты>")
                        print("   /unmute <ник>")
                        print("   /delmsg <id>")
                        print("   /delfile <id>")
                        print("   /users")
                        print("   /banned")
                        print("   /history [количество]")
                        print("   /clearusers")
                        print("   /clearhistory")
                        print("   /stop - остановить сервер\n")
                        
                    elif command == "/stop":
                        print("\n🛑 Остановка сервера...")
                        self.running = False
                        break
                        
                    else:
                        print(f"❌ Неизвестная команда: {command}")
                        
                except EOFError:
                    break
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
        
        threading.Thread(target=handle_input, daemon=True).start()
    
    def start_chat_server(self):
        chat_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        chat_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        chat_server.bind((self.host, self.port))
        chat_server.listen(100)
        
        def accept_clients():
            while self.running:
                try:
                    chat_server.settimeout(1)
                    client, addr = chat_server.accept()
                    ip = addr[0]
                    
                    if ip in self.banned_ips:
                        client.send("BANNED\n".encode('utf-8'))
                        client.close()
                        print(f"🚫 Забаненный IP: {ip}")
                        continue
                        
                    print(f"[+] Новое подключение: {addr}")
                    client.send("AUTH_REQUIRED\n".encode('utf-8'))
                    threading.Thread(target=self.handle_auth_loop, args=(client, addr), daemon=True).start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"Ошибка accept: {e}")
        
        threading.Thread(target=accept_clients, daemon=True).start()
        print(f"💬 Чат сервер запущен на порту {self.port}")
    
    def handle_auth_loop(self, client, addr):
        auth_attempts = 0
        max_attempts = 5
        
        while auth_attempts < max_attempts and self.running:
            try:
                client.settimeout(60)
                auth_data = client.recv(4096).decode('utf-8').strip()
                
                if not auth_data:
                    break
                
                parts = auth_data.split('|')
                action = parts[0]
                
                if action == "LOGIN":
                    if len(parts) != 3:
                        self.send_to_client(client, "AUTH_FAIL|❌ Неверный формат запроса!")
                        auth_attempts += 1
                        continue
                    
                    username = parts[1]
                    password = self.decode_base64(parts[2])
                    success, result = self.login_user(username, password)
                    
                    if success:
                        nickname = result
                        self.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                        
                        self.clients.append(client)
                        self.client_data[client] = {"nickname": nickname, "username": username, "addr": addr[0]}
                        
                        history_payload = "JSON_PAYLOAD:" + json.dumps({
                            "type": "history",
                            "messages": self.messages_history[-100:],
                            "files": [f for f in self.files_list if f.get('chat', 'general') == 'general']
                        }, ensure_ascii=True)
                        self.send_to_client(client, history_payload)
                        time.sleep(0.1)
                        
                        client.settimeout(None)
                        self.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "notification", "text": f"{nickname} присоединился к чату!"}, ensure_ascii=False), exclude_socket=client)
                        print(f"   👤 {nickname} (@{username}) вошёл | Онлайн: {len(self.clients)}")
                        
                        self.handle_chat(client, nickname)
                        return
                    else:
                        self.send_to_client(client, f"AUTH_FAIL|{result}")
                        auth_attempts += 1
                        
                elif action == "REGISTER":
                    if len(parts) != 4:
                        self.send_to_client(client, "AUTH_FAIL|❌ Неверный формат запроса!")
                        auth_attempts += 1
                        continue
                    
                    username = parts[1]
                    password = self.decode_base64(parts[2])
                    nickname = parts[3]
                    
                    success, result = self.register_user(username, password, nickname)
                    
                    if success:
                        self.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                        
                        self.clients.append(client)
                        self.client_data[client] = {"nickname": nickname, "username": username, "addr": addr[0]}
                        
                        history_payload = "JSON_PAYLOAD:" + json.dumps({
                            "type": "history",
                            "messages": [],
                            "files": []
                        }, ensure_ascii=True)
                        self.send_to_client(client, history_payload)
                        time.sleep(0.1)
                        
                        client.settimeout(None)
                        self.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "notification", "text": f"{nickname} присоединился к чату!"}, ensure_ascii=False), exclude_socket=client)
                        print(f"   👤 {nickname} (@{username}) зарегистрировался | Онлайн: {len(self.clients)}")
                        
                        self.handle_chat(client, nickname)
                        return
                    else:
                        self.send_to_client(client, f"AUTH_FAIL|{result}")
                        auth_attempts += 1
                        
                else:
                    self.send_to_client(client, "AUTH_FAIL|❌ Неизвестная команда!")
                    auth_attempts += 1
                    
            except socket.timeout:
                print(f"   ⏰ Таймаут авторизации для {addr}")
                break
            except Exception as e:
                print(f"   ❌ Ошибка авторизации: {e}")
                break
        
        try:
            client.close()
        except:
            pass
    
    def handle_chat(self, client, name):
        buffer = ""
        while self.running:
            try:
                data = client.recv(4096).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Проверка мута
                    if name in self.muted_users:
                        if datetime.now() < self.muted_users[name]:
                            self.send_to_client(client, "MSG:СЕРВЕР: 🔇 Вы в муте!")
                            continue
                        else:
                            del self.muted_users[name]
                    
                    # Обработка команд
                    if line.startswith("CMD:"):
                        parts = line[4:].split('|')
                        cmd = parts[0]
                        
                        if cmd == "PM" and len(parts) >= 3:
                            target = parts[1]
                            msg = "|".join(parts[2:])
                            
                            # Сохраняем сообщение
                            chat_id = self.get_chat_id(name, target)
                            if chat_id not in self.private_messages:
                                self.private_messages[chat_id] = []
                            
                            pm = {
                                'sender': name,
                                'text': msg,
                                'time': datetime.now().strftime("%H:%M:%S")
                            }
                            self.private_messages[chat_id].append(pm)
                            self.save_private_messages()
                            
                            # Отправляем получателю
                            target_socket = None
                            for s, data in self.client_data.items():
                                if data['nickname'] == target:
                                    target_socket = s
                                    break
                            
                            if target_socket:
                                payload = json.dumps({"type": "private_message", "from": name, "text": msg}, ensure_ascii=False)
                                self.send_to_client(target_socket, "JSON_PAYLOAD:" + payload)
                            
                            # Подтверждение отправителю
                            self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "private_sent", "to": target, "text": msg}, ensure_ascii=False))
                            print(f"   💬 ЛС от {name} для {target}")
                            
                        elif cmd == "GET_PM_HISTORY" and len(parts) >= 2:
                            target = parts[1]
                            chat_id = self.get_chat_id(name, target)
                            history = self.private_messages.get(chat_id, [])
                            self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                                "type": "private_history",
                                "target": target,
                                "messages": history
                            }, ensure_ascii=True))
                            
                        elif cmd == "EDIT" and len(parts) >= 3:
                            msg_id = parts[1]
                            new_text = "|".join(parts[2:])
                            for msg in self.messages_history:
                                if msg.get('id') == msg_id and msg.get('sender') == name:
                                    msg['text'] = new_text
                                    msg['edited'] = True
                                    self.save_history()
                                    edit_msg = "JSON_PAYLOAD:" + json.dumps({"type": "message_edited", "id": msg_id, "text": new_text}, ensure_ascii=False)
                                    self.broadcast(edit_msg)
                                    print(f"   ✏️ {name} отредактировал {msg_id}")
                                    break
                            
                        elif cmd == "COLOR" and len(parts) >= 2:
                            color = parts[1]
                            color_msg = "JSON_PAYLOAD:" + json.dumps({"type": "color_update", "nick": name, "color": color}, ensure_ascii=False)
                            self.broadcast(color_msg)
                            print(f"   🎨 {name} изменил цвет на {color}")
                            
                        elif cmd == "FORGOT" and len(parts) >= 2:
                            username = parts[1]
                            if username in self.users_db:
                                code = str(random.randint(100000, 999999))
                                self.recovery_codes[username] = code
                                print("\n" + "="*50)
                                print(f"🔐 ЗАПРОС ВОССТАНОВЛЕНИЯ")
                                print(f"👤 Логин: {username}")
                                print(f"🔑 Код: {code}")
                                print("="*50 + "\n")
                                self.send_to_client(client, f"RECOVERY_CODE:{code}")
                            else:
                                self.send_to_client(client, "USER_NOT_FOUND")
                        continue
                    
                    # Обычное сообщение
                    self.message_counter += 1
                    msg_id = f"msg_{self.message_counter}"
                    message = {
                        "id": msg_id,
                        "sender": name,
                        "text": line,
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "edited": False
                    }
                    self.messages_history.append(message)
                    self.save_history()
                    
                    broadcast_msg = "JSON_PAYLOAD:" + json.dumps({"type": "message", "data": message}, ensure_ascii=False)
                    self.broadcast(broadcast_msg)
                    print(f"📝 {name}: {line[:50]}...")
                    
            except Exception as e:
                print(f"Ошибка handle_chat для {name}: {e}")
                break
        self.remove_client(client)
    
    def start_file_server(self):
        file_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        file_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        file_server.bind((self.host, self.file_port))
        file_server.listen(100)
        
        def handle_file_connections():
            while self.running:
                try:
                    file_server.settimeout(1)
                    file_socket, addr = file_server.accept()
                    print(f"[+] Файловое подключение: {addr}")
                    threading.Thread(target=self.handle_file, args=(file_socket, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"Ошибка файлового сервера: {e}")
        
        threading.Thread(target=handle_file_connections, daemon=True).start()
        print(f"📁 Файловый сервер запущен на порту {self.file_port}")
    
    def recv_exact(self, sock, size):
        data = b''
        while len(data) < size:
            packet = sock.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data
    
    def handle_file(self, file_socket, addr):
        try:
            file_socket.settimeout(60)
            
            cmd_byte = file_socket.recv(1)
            if not cmd_byte:
                file_socket.close()
                return
            
            cmd = cmd_byte.decode('utf-8', errors='ignore')
            
            if cmd == 'L':  # LIST GENERAL
                general_files = [f for f in self.files_list if f.get('chat', 'general') == 'general']
                files_json = json.dumps(general_files, ensure_ascii=True).encode('utf-8')
                file_socket.send(struct.pack('>I', len(files_json)))
                file_socket.send(files_json)
                print(f"📋 Список общих файлов: {len(general_files)}")
                
            elif cmd == 'P':  # LIST PRIVATE
                nick_len_data = self.recv_exact(file_socket, 4)
                if not nick_len_data:
                    file_socket.close()
                    return
                nick_len = struct.unpack('>I', nick_len_data)[0]
                nick = self.recv_exact(file_socket, nick_len).decode('utf-8')
                
                private_files = [f for f in self.files_list if f.get('chat') == nick]
                files_json = json.dumps(private_files, ensure_ascii=True).encode('utf-8')
                file_socket.send(struct.pack('>I', len(files_json)))
                file_socket.send(files_json)
                print(f"📋 Личные файлы для {nick}: {len(private_files)}")
                
            elif cmd == 'D':  # DOWNLOAD
                id_len_data = self.recv_exact(file_socket, 4)
                if not id_len_data:
                    file_socket.close()
                    return
                id_len = struct.unpack('>I', id_len_data)[0]
                file_id = self.recv_exact(file_socket, id_len).decode('utf-8')
                
                found = False
                for f in self.files_list:
                    if f['id'] == file_id:
                        file_socket.send(b'K')
                        file_socket.send(struct.pack('>Q', f['size']))
                        name_bytes = f['name'].encode('utf-8')
                        file_socket.send(struct.pack('>I', len(name_bytes)))
                        file_socket.send(name_bytes)
                        
                        with open(f['path'], 'rb') as file:
                            while True:
                                data = file.read(8192)
                                if not data:
                                    break
                                file_socket.send(data)
                        print(f"📤 Файл {f['name']} отправлен")
                        found = True
                        break
                
                if not found:
                    file_socket.send(b'E')
                    
            elif cmd == 'U':  # UPLOAD GENERAL
                name_len_data = self.recv_exact(file_socket, 4)
                if not name_len_data:
                    file_socket.close()
                    return
                name_len = struct.unpack('>I', name_len_data)[0]
                filename = self.recv_exact(file_socket, name_len).decode('utf-8')
                
                size_data = self.recv_exact(file_socket, 8)
                filesize = struct.unpack('>Q', size_data)[0]
                
                sender_len_data = self.recv_exact(file_socket, 4)
                if not sender_len_data:
                    file_socket.close()
                    return
                sender_len = struct.unpack('>I', sender_len_data)[0]
                sender = self.recv_exact(file_socket, sender_len).decode('utf-8')
                
                print(f"📥 Общий файл от {sender}: {filename} ({filesize/1024:.1f} KB)")
                
                file_socket.send(b'K')
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
                base, ext = os.path.splitext(safe_filename)
                save_path = os.path.join(RECEIVED_FILES_DIR, f"{base}_{timestamp}{ext}")
                
                received = 0
                with open(save_path, 'wb') as f:
                    while received < filesize:
                        data = file_socket.recv(min(8192, filesize - received))
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                
                file_id = hashlib.md5(f"{filename}{timestamp}{sender}".encode()).hexdigest()[:8]
                file_info = {
                    'id': file_id,
                    'name': filename,
                    'path': save_path,
                    'size': filesize,
                    'sender': sender,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'chat': 'general'
                }
                self.files_list.append(file_info)
                self.save_history()
                
                print(f"✅ Файл сохранён: {save_path}")
                
                self.broadcast("JSON_PAYLOAD:" + json.dumps({
                    "type": "file",
                    "data": {"sender": sender, "name": filename, "size": filesize, "id": file_id}
                }, ensure_ascii=True))
                
            elif cmd == 'V':  # UPLOAD PRIVATE
                target_len_data = self.recv_exact(file_socket, 4)
                if not target_len_data:
                    file_socket.close()
                    return
                target_len = struct.unpack('>I', target_len_data)[0]
                target = self.recv_exact(file_socket, target_len).decode('utf-8')
                
                name_len_data = self.recv_exact(file_socket, 4)
                if not name_len_data:
                    file_socket.close()
                    return
                name_len = struct.unpack('>I', name_len_data)[0]
                filename = self.recv_exact(file_socket, name_len).decode('utf-8')
                
                size_data = self.recv_exact(file_socket, 8)
                filesize = struct.unpack('>Q', size_data)[0]
                
                sender_len_data = self.recv_exact(file_socket, 4)
                if not sender_len_data:
                    file_socket.close()
                    return
                sender_len = struct.unpack('>I', sender_len_data)[0]
                sender = self.recv_exact(file_socket, sender_len).decode('utf-8')
                
                print(f"📥 Личный файл от {sender} для {target}: {filename} ({filesize/1024:.1f} KB)")
                
                file_socket.send(b'K')
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
                base, ext = os.path.splitext(safe_filename)
                save_path = os.path.join(RECEIVED_FILES_DIR, f"{base}_{timestamp}{ext}")
                
                received = 0
                with open(save_path, 'wb') as f:
                    while received < filesize:
                        data = file_socket.recv(min(8192, filesize - received))
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                
                file_id = hashlib.md5(f"{filename}{timestamp}{sender}{target}".encode()).hexdigest()[:8]
                file_info = {
                    'id': file_id,
                    'name': filename,
                    'path': save_path,
                    'size': filesize,
                    'sender': sender,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'chat': target
                }
                self.files_list.append(file_info)
                self.save_history()
                
                print(f"✅ Личный файл сохранён: {save_path}")
                
                target_socket = None
                for s, data in self.client_data.items():
                    if data['nickname'] == target:
                        target_socket = s
                        break
                
                payload = json.dumps({
                    "type": "private_file",
                    "target": target,
                    "data": {"sender": sender, "name": filename, "size": filesize, "id": file_id}
                }, ensure_ascii=True)
                
                if target_socket:
                    self.send_to_client(target_socket, "JSON_PAYLOAD:" + payload)
                self.send_to_client(client, "JSON_PAYLOAD:" + payload)
                
            file_socket.close()
                
        except Exception as e:
            print(f"❌ Ошибка файла от {addr}: {e}")
            try:
                file_socket.close()
            except:
                pass

if __name__ == "__main__":
    print(f"🚀 Запуск сервера v{ChatServer.VERSION}...")
    server = ChatServer()
    try:
        while server.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Сервер остановлен")
        server.running = False