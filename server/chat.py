import json
import time
from datetime import datetime
from collections import defaultdict
from utils import hash_password, decode_base64
from rate_limiter import RateLimiter
from security import SecurityValidator

class ChatManager:
    def __init__(self, server):
        self.server = server
        self.muted_users = {}
        self.rate_limiter = RateLimiter()
    
    def get_chat_id(self, user1, user2):
        return "|".join(sorted([user1, user2]))
    
    def handle_chat(self, client, name):
        buffer = ""
        while self.server.running:
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
                    
                    if name in self.muted_users:
                        if datetime.now() < self.muted_users[name]:
                            continue
                        else:
                            del self.muted_users[name]
                    
                    if line.startswith("CMD:"):
                        self.process_command(line[4:], client, name)
                        continue
                    
                    text = SecurityValidator.sanitize_text(line)
                    if not text:
                        continue
                    
                    self.server.storage.message_counter += 1
                    msg_id = f"msg_{self.server.storage.message_counter}"
                    message = {
                        "id": msg_id,
                        "sender": name,
                        "text": text,
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "edited": False
                    }
                    self.server.storage.add_message(message)
                    self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "message", "data": message}))
                    
            except Exception as e:
                self.server.log(f"Ошибка handle_chat: {e}", "error")
                break
        self.server.network.remove_client(client)
    
    def process_command(self, cmd_str, client, name):
        parts = cmd_str.split('|')
        cmd = parts[0]
        
        user = self.server.storage.db.get_user_by_nickname(name)
        user_id = user['id'] if user else 0
        
        # Ограничения
        if cmd in ["CREATE_GROUP", "ADD_TO_GROUP", "SEND_FRIEND_REQUEST"]:
            if not self.rate_limiter.check_limit(user_id, cmd.lower()):
                self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ❌ Слишком часто, подожди")
                return
        
        # === ЛИЧНЫЕ СООБЩЕНИЯ ===
        if cmd == "PM" and len(parts) >= 3:
            target = parts[1]
            msg = "|".join(parts[2:])
            msg = SecurityValidator.sanitize_text(msg)
            if not msg:
                return
            
            chat_id = self.get_chat_id(name, target)
            message = {
                'id': f"pm_{int(time.time()*1000)}",
                'sender': name,
                'text': msg,
                'time': datetime.now().strftime("%H:%M:%S")
            }
            self.server.storage.db.add_private_message(
                chat_id, message['id'], user_id, name, msg, message['time']
            )
            
            target_socket = None
            for s, data in self.server.client_data.items():
                if data['nickname'] == target:
                    target_socket = s
                    break
            if target_socket:
                self.server.network.send_to_client(target_socket, "JSON_PAYLOAD:" + json.dumps({"type": "private_message", "from": name, "text": msg}))
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "private_sent", "to": target, "text": msg}))
        
        # === ИСТОРИЯ ЛС ===
        elif cmd == "GET_PM_HISTORY" and len(parts) >= 2:
            target = parts[1]
            chat_id = self.get_chat_id(name, target)
            messages = self.server.storage.db.get_private_messages(chat_id)
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "private_history", "target": target, "messages": messages}))
        
        # === ОНЛАЙН ===
        elif cmd == "ONLINE":
            users = [data['nickname'] for data in self.server.client_data.values()]
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "online_users", "users": users}))
        
        # === СМЕНА ЦВЕТА ===
        elif cmd == "COLOR" and len(parts) >= 2:
            color = parts[1]
            self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "color_update", "nick": name, "color": color}))
        
        # === ДРУЗЬЯ ===
        elif cmd == "SEND_FRIEND_REQUEST" and len(parts) >= 2:
            target = parts[1]
            target_socket = None
            for s, data in self.server.client_data.items():
                if data['nickname'] == target:
                    target_socket = s
                    break
            if target_socket:
                self.server.network.send_to_client(target_socket, "JSON_PAYLOAD:" + json.dumps({"type": "friend_request", "from": name}))
        
        # === ГРУППЫ ===
        elif cmd == "CREATE_GROUP" and len(parts) >= 2:
            group_name = parts[1]
            valid, err = SecurityValidator.validate_group_name(group_name)
            if not valid:
                self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ❌ {err}")
                return
            existing = self.server.storage.db.get_group_by_name(group_name)
            if existing:
                self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Группа уже существует")
                return
            group_id = self.server.storage.db.create_group(group_name, user_id)
            if group_id:
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "group_created", "group": group_name}))
        
        elif cmd == "ADD_TO_GROUP" and len(parts) >= 3:
            group_name = parts[1]
            member = parts[2]
            group = self.server.storage.db.get_group_by_name(group_name)
            if not group:
                return
            member_user = self.server.storage.db.get_user_by_nickname(member)
            if not member_user:
                return
            self.server.storage.db.add_group_member(group['id'], member_user['id'])
            self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "group_member_added", "group": group_name, "member": member}))
        
        elif cmd == "GROUP_MSG" and len(parts) >= 3:
            group_name = parts[1]
            text = "|".join(parts[2:])
            text = SecurityValidator.sanitize_text(text)
            if not text:
                return
            group = self.server.storage.db.get_group_by_name(group_name)
            if not group:
                return
            msg_id = f"group_{int(time.time()*1000)}"
            message = {
                "id": msg_id,
                "sender": name,
                "text": text,
                "time": datetime.now().strftime("%H:%M:%S")
            }
            self.server.storage.db.add_group_message(group['id'], msg_id, user_id, name, text, message['time'])
            members = self.server.storage.db.get_group_members(group['id'])
            for s, data in self.server.client_data.items():
                if data['nickname'] in members:
                    self.server.network.send_to_client(s, "JSON_PAYLOAD:" + json.dumps({"type": "group_message", "group": group_name, "data": message}))