# server/chat.py
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict
from utils import hash_password, decode_base64

class ChatManager:
    def __init__(self, server):
        self.server = server
        self.message_timestamps = defaultdict(list)
        self.muted_users = {}
        self.spam_mute_minutes = 15
        self.spam_threshold = 5
        self.spam_interval = 1.5
    
    def get_chat_id(self, user1, user2):
        return "|".join(sorted([user1, user2]))
    
    def check_spam(self, nickname):
        now = time.time()
        self.message_timestamps[nickname].append(now)
        cutoff = now - self.spam_interval
        self.message_timestamps[nickname] = [t for t in self.message_timestamps[nickname] if t > cutoff]
        
        if len(self.message_timestamps[nickname]) >= self.spam_threshold:
            self.server.admin.mute_user(nickname, self.spam_mute_minutes)
            self.message_timestamps[nickname] = []
            for client, data in self.server.client_data.items():
                if data['nickname'] == nickname:
                    self.server.network.send_to_client(client, "MSG:СЕРВЕР: 🔇 Вы замучены на 15 минут за спам!")
                    break
            self.server.log(f"🔇 {nickname} замучен на 15 минут за спам", "admin")
            return True
        return False
    
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
                            self.server.root.after(0, self.server.update_online_display)
                    
                    if line.startswith("CMD:"):
                        self.process_command(line[4:], client, name)
                        continue
                    
                    if self.check_spam(name):
                        continue
                    
                    self.server.storage.message_counter += 1
                    msg_id = f"msg_{self.server.storage.message_counter}"
                    message = {
                        "id": msg_id,
                        "sender": name,
                        "text": line,
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "edited": False
                    }
                    self.server.storage.messages_history.append(message)
                    self.server.storage.save_history()
                    
                    broadcast_msg = "JSON_PAYLOAD:" + json.dumps({"type": "message", "data": message}, ensure_ascii=False)
                    self.server.network.broadcast(broadcast_msg)
                    self.server.log(f"📝 {name}: {line[:50]}... [ID: {msg_id}]", "system")
                    
            except Exception as e:
                self.server.log(f"Ошибка handle_chat для {name}: {e}", "error")
                break
        self.server.network.remove_client(client)
    
    def process_command(self, cmd_str, client, name):
        parts = cmd_str.split('|')
        cmd = parts[0]
        
        if cmd == "PM" and len(parts) >= 3:
            target = parts[1]
            msg = "|".join(parts[2:])
            chat_id = self.get_chat_id(name, target)
            
            if chat_id not in self.server.storage.private_messages:
                self.server.storage.private_messages[chat_id] = []
            
            pm = {
                'id': f"pm_{int(time.time()*1000)}",
                'sender': name,
                'text': msg,
                'time': datetime.now().strftime("%H:%M:%S")
            }
            self.server.storage.private_messages[chat_id].append(pm)
            self.server.storage.save_private_messages()
            
            target_socket = None
            for s, data in self.server.client_data.items():
                if data['nickname'] == target:
                    target_socket = s
                    break
            
            if target_socket:
                payload = json.dumps({"type": "private_message", "from": name, "text": msg}, ensure_ascii=False)
                self.server.network.send_to_client(target_socket, "JSON_PAYLOAD:" + payload)
            
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(
                {"type": "private_sent", "to": target, "text": msg}, ensure_ascii=False))
            self.server.log(f"💬 ЛС от {name} для {target}", "system")
        
        elif cmd == "GET_PM_HISTORY" and len(parts) >= 2:
            target = parts[1]
            chat_id = self.get_chat_id(name, target)
            history = self.server.storage.private_messages.get(chat_id, [])
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(
                {"type": "private_history", "target": target, "messages": history}, ensure_ascii=True))
        
        elif cmd == "EDIT" and len(parts) >= 4:
            chat_type = parts[1]
            msg_id = parts[2]
            new_text = "|".join(parts[3:])
            
            if chat_type == "general":
                for msg in self.server.storage.messages_history:
                    if msg.get('id') == msg_id and msg.get('sender') == name:
                        msg['text'] = new_text
                        msg['edited'] = True
                        self.server.storage.save_history()
                        edit_msg = "JSON_PAYLOAD:" + json.dumps(
                            {"type": "message_edited", "id": msg_id, "text": new_text}, ensure_ascii=False)
                        self.server.network.broadcast(edit_msg)
                        break
            else:
                target = chat_type
                chat_id = self.get_chat_id(name, target)
                if chat_id in self.server.storage.private_messages:
                    for msg in self.server.storage.private_messages[chat_id]:
                        if msg.get('id') == msg_id and msg.get('sender') == name:
                            msg['text'] = new_text
                            msg['edited'] = True
                            self.server.storage.save_private_messages()
                            edit_msg = "JSON_PAYLOAD:" + json.dumps({
                                "type": "private_message_edited",
                                "target": target, "id": msg_id, "text": new_text
                            }, ensure_ascii=False)
                            self.server.network.send_to_client(client, edit_msg)
                            target_socket = None
                            for s, data in self.server.client_data.items():
                                if data['nickname'] == target:
                                    target_socket = s
                                    break
                            if target_socket:
                                self.server.network.send_to_client(target_socket, edit_msg)
                            break
        
        elif cmd == "COLOR" and len(parts) >= 2:
            color = parts[1]
            color_msg = "JSON_PAYLOAD:" + json.dumps({"type": "color_update", "nick": name, "color": color}, ensure_ascii=False)
            self.server.network.broadcast(color_msg)
        
        elif cmd == "ONLINE":
            online_users = [data['nickname'] for data in self.server.client_data.values()]
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(
                {"type": "online_users", "users": online_users}, ensure_ascii=False))
        
        elif cmd == "CHANGENICK" and len(parts) >= 2:
            new_nick = parts[1]
            old_nick = name
            for client_sock, data in self.server.client_data.items():
                if data['nickname'] == old_nick:
                    self.server.client_data[client_sock]['nickname'] = new_nick
                    break
            self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps(
                {"type": "nickname_changed", "old": old_nick, "new": new_nick}, ensure_ascii=False))
        
        elif cmd == "CHANGEPASS" and len(parts) >= 4:
            username = parts[1]
            old_pass = decode_base64(parts[2])
            new_pass = decode_base64(parts[3])
            from utils import hash_password as hp
            if username in self.server.storage.users_db and \
               self.server.storage.users_db[username]["password"] == hp(old_pass):
                self.server.storage.users_db[username]["password"] = hp(new_pass)
                self.server.storage.save_users()
                self.server.network.send_to_client(client, "MSG:СЕРВЕР: ✅ Пароль успешно изменён")
            else:
                self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Неверный старый пароль")
        
        elif cmd == "STATUS" and len(parts) >= 2:
            status = parts[1]
            self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps(
                {"type": "status_update", "nick": name, "status": status}, ensure_ascii=False))
        
        elif cmd == "TYPING" and len(parts) >= 2:
            target = parts[1]
            target_socket = None
            for s, data in self.server.client_data.items():
                if data['nickname'] == target:
                    target_socket = s
                    break
            if target_socket:
                self.server.network.send_to_client(target_socket, "JSON_PAYLOAD:" + json.dumps(
                    {"type": "typing", "nick": name}, ensure_ascii=False))
        
        elif cmd == "FINDUSER" and len(parts) >= 2:
            query = parts[1].lower()
            found = []
            for data in self.server.client_data.values():
                if query in data['nickname'].lower():
                    found.append(data['nickname'])
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(
                {"type": "find_result", "users": found}, ensure_ascii=False))
        
        elif cmd == "SEND_FRIEND_REQUEST" and len(parts) >= 2:
            target = parts[1]
            target_socket = None
            for s, data in self.server.client_data.items():
                if data['nickname'] == target:
                    target_socket = s
                    break
            if target_socket:
                self.server.network.send_to_client(target_socket, "JSON_PAYLOAD:" + json.dumps(
                    {"type": "friend_request", "from": name}, ensure_ascii=False))
                self.server.log(f"👥 {name} отправил запрос в друзья {target}", "system")
            else:
                self.server.log(f"❌ Пользователь {target} не в сети", "error")
        
        elif cmd == "ACCEPT_FRIEND" and len(parts) >= 2:
            from_user = parts[1]
            current_user = name
            
            if self.server.storage.add_friend(current_user, from_user):
                for s, data in self.server.client_data.items():
                    if data['nickname'] == from_user:
                        updated_friends = self.server.storage.get_friends(from_user)
                        self.server.network.send_to_client(s, "JSON_PAYLOAD:" + json.dumps({
                            "type": "friends_list",
                            "friends": updated_friends
                        }, ensure_ascii=False))
                    if data['nickname'] == current_user:
                        updated_friends = self.server.storage.get_friends(current_user)
                        self.server.network.send_to_client(s, "JSON_PAYLOAD:" + json.dumps({
                            "type": "friends_list",
                            "friends": updated_friends
                        }, ensure_ascii=False))
                self.server.log(f"👥 {current_user} и {from_user} теперь друзья", "system")
        
        elif cmd == "DECLINE_FRIEND" and len(parts) >= 2:
            from_user = parts[1]
            self.server.log(f"👥 {name} отклонил запрос в друзья от {from_user}", "system")
        
        # ГРУППОВЫЕ КОМАНДЫ
        elif cmd == "CREATE_GROUP" and len(parts) >= 2:
            group_name = parts[1]
            members = [name]
            if self.server.storage.create_group(group_name, name, members):
                self.server.log(f"👥 Создана группа {group_name} пользователем {name}", "system")
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(
                    {"type": "group_created", "group": group_name}, ensure_ascii=False))
            else:
                self.server.network.send_to_client(client, "MSG:СЕРВЕР: Группа уже существует")
        
        elif cmd == "ADD_TO_GROUP" and len(parts) >= 3:
            group_name = parts[1]
            member = parts[2]
            if self.server.storage.add_member_to_group(group_name, member):
                self.server.log(f"👥 {member} добавлен в группу {group_name} пользователем {name}", "system")
                
                # Получаем обновлённый список участников
                updated_members = self.server.storage.get_group_members(group_name)
                
                # Рассылаем обновления всем участникам группы
                for s, data in self.server.client_data.items():
                    if data['nickname'] in updated_members:
                        # Отправляем обновлённый список участников
                        self.server.network.send_to_client(s, "JSON_PAYLOAD:" + json.dumps({
                            "type": "group_members",
                            "group": group_name,
                            "members": updated_members
                        }, ensure_ascii=False))
                        
                        # Если это новый участник, отправляем ему историю группы
                        if data['nickname'] == member:
                            group_data = self.server.storage.groups.get(group_name, {})
                            group_history = "JSON_PAYLOAD:" + json.dumps({
                                "type": "group_history",
                                "group": group_name,
                                "messages": group_data.get("messages", []),
                                "files": group_data.get("files", [])
                            }, ensure_ascii=True)
                            self.server.network.send_to_client(s, group_history)
        
        elif cmd == "GROUP_MSG" and len(parts) >= 3:
            group_name = parts[1]
            text = "|".join(parts[2:])
            msg_id = f"group_{int(time.time()*1000)}"
            message = {
                "id": msg_id,
                "sender": name,
                "text": text,
                "time": datetime.now().strftime("%H:%M:%S"),
                "edited": False
            }
            self.server.storage.add_group_message(group_name, message)
            
            members = self.server.storage.get_group_members(group_name)
            for s, data in self.server.client_data.items():
                if data['nickname'] in members:
                    self.server.network.send_to_client(s, "JSON_PAYLOAD:" + json.dumps(
                        {"type": "group_message", "group": group_name, "data": message}, ensure_ascii=False))
                    
        elif cmd == "RENAME_GROUP" and len(parts) >= 3:
            old_name = parts[1]
            new_name = parts[2]
            if old_name in self.server.storage.groups:
                self.server.storage.groups[new_name] = self.server.storage.groups.pop(old_name)
                self.server.storage.save_groups()
                # Рассылаем участникам новое название
                members = self.server.storage.get_group_members(new_name)
                for s, data in self.server.client_data.items():
                    if data['nickname'] in members:
                        self.server.network.send_to_client(s, "JSON_PAYLOAD:" + json.dumps(
                            {"type": "group_renamed", "old": old_name, "new": new_name}, ensure_ascii=False))
                self.server.log(f"✏️ Группа {old_name} переименована в {new_name}", "system")
        
        elif cmd == "DELETE_GROUP" and len(parts) >= 2:
            group_name = parts[1]
            if group_name in self.server.storage.groups:
                del self.server.storage.groups[group_name]
                self.server.storage.save_groups()
                self.server.log(f"🗑️ Группа {group_name} удалена", "system")