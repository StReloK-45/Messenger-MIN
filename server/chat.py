# server/chat.py
import json
import time
import socket
from datetime import datetime
from typing import Dict, Optional, List, Any

from rate_limiter import RateLimiter
from security import SecurityValidator
from logger import logger


class ChatManager:
    """Управление чатами, командами и сообщениями"""
    
    def __init__(self, server):
        self.server = server
        self.muted_users: Dict[str, datetime] = {}
        self.rate_limiter = RateLimiter()
        self.typing_users: Dict[str, float] = {}
        self.pending_group_invites: Dict[str, List[str]] = {}
    
    def get_chat_id(self, user1: str, user2: str) -> str:
        """Генерирует ID для приватного чата"""
        return "|".join(sorted([user1, user2]))
    
    def is_muted(self, nickname: str) -> bool:
        """Проверяет, замьючен ли пользователь"""
        if nickname in self.muted_users:
            if datetime.now() < self.muted_users[nickname]:
                return True
            else:
                del self.muted_users[nickname]
        return False
    
    def handle_chat(self, client: socket.socket, nickname: str):
        """Основной цикл обработки чата"""
        buffer = ""
        
        while self.server.running:
            try:
                client.settimeout(1.0)
                data = client.recv(4096).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue
                    
                    if self.is_muted(nickname):
                        continue
                    
                    if line.startswith("CMD:"):
                        self.process_command(line[4:], client, nickname)
                    else:
                        self.process_message(line, client, nickname)
                        
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError):
                logger.warning(f"Connection lost: {nickname}")
                break
            except Exception as e:
                logger.error(f"Chat handler error for {nickname}: {e}")
                break
        
        self.cleanup_client(client, nickname)
    
    def process_message(self, text: str, client: socket.socket, sender: str):
        """Обработка обычного текстового сообщения"""
        sanitized = SecurityValidator.sanitize_text(text)
        if not sanitized:
            return
        
        # Rate limiting
        user = self.server.storage.get_user_by_nickname(sender)
        if user and not self.rate_limiter.check_limit(user['id'], 'message'):
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Слишком много сообщений, подождите")
            return
        
        self.server.storage.message_counter += 1
        msg_id = f"msg_{self.server.storage.message_counter}"
        
        message = {
            "id": msg_id,
            "sender": sender,
            "text": sanitized,
            "time": datetime.now().strftime("%H:%M:%S"),
            "edited": False
        }
        
        self.server.storage.add_message(message)
        self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
            "type": "message", 
            "data": message
        }, ensure_ascii=False))
        
        logger.chat(sender, sanitized)
    
    def process_command(self, cmd_str: str, client: socket.socket, sender: str):
        """Обработка команд от клиента"""
        parts = cmd_str.split('|')
        cmd = parts[0].upper()
        
        user = self.server.storage.get_user_by_nickname(sender)
        user_id = user['id'] if user else 0
        
        # Rate limiting для чувствительных команд
        sensitive_commands = ["CREATE_GROUP", "ADD_TO_GROUP", "SEND_FRIEND_REQUEST", 
                              "RENAME_GROUP", "DELETE_GROUP", "CHANGEPASS"]
        if cmd in sensitive_commands:
            if not self.rate_limiter.check_limit(user_id, cmd.lower()):
                self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Слишком часто, подождите")
                return
        
        # ========== ПРИВАТНЫЕ СООБЩЕНИЯ ==========
        if cmd == "PM" and len(parts) >= 3:
            self.handle_private_message(parts, client, sender)
        
        # ========== ИСТОРИЯ ЛИЧНЫХ СООБЩЕНИЙ ==========
        elif cmd == "GET_PM_HISTORY" and len(parts) >= 2:
            self.handle_get_pm_history(parts[1], client, sender)
        
        # ========== ОНЛАЙН ПОЛЬЗОВАТЕЛИ ==========
        elif cmd == "ONLINE":
            self.handle_get_online(client)
        
        # ========== СМЕНА ЦВЕТА НИКА ==========
        elif cmd == "COLOR" and len(parts) >= 2:
            self.handle_change_color(parts[1], client, sender)
        
        # ========== УПРАВЛЕНИЕ ДРУЗЬЯМИ ==========
        elif cmd == "SEND_FRIEND_REQUEST" and len(parts) >= 2:
            self.handle_friend_request(parts[1], client, sender, user_id)
        
        elif cmd == "ACCEPT_FRIEND" and len(parts) >= 2:
            self.handle_accept_friend(parts[1], client, sender, user_id)
        
        elif cmd == "DECLINE_FRIEND" and len(parts) >= 2:
            self.handle_decline_friend(parts[1], sender)
        
        # ========== УПРАВЛЕНИЕ ГРУППАМИ ==========
        elif cmd == "CREATE_GROUP" and len(parts) >= 2:
            self.handle_create_group(parts[1], client, sender, user_id)
        
        elif cmd == "RENAME_GROUP" and len(parts) >= 3:
            self.handle_rename_group(parts[1], parts[2], client, sender, user_id)
        
        elif cmd == "ADD_TO_GROUP" and len(parts) >= 3:
            self.handle_add_to_group(parts[1], parts[2], client, sender, user_id)
        
        elif cmd == "REMOVE_FROM_GROUP" and len(parts) >= 3:
            self.handle_remove_from_group(parts[1], parts[2], client, sender, user_id)
        
        elif cmd == "DELETE_GROUP" and len(parts) >= 2:
            self.handle_delete_group(parts[1], client, sender, user_id)
        
        elif cmd == "LEAVE_GROUP" and len(parts) >= 2:
            self.handle_leave_group(parts[1], client, sender, user_id)
        
        elif cmd == "GROUP_MSG" and len(parts) >= 3:
            self.handle_group_message(parts, client, sender, user_id)
        
        # ========== АККАУНТ ==========
        elif cmd == "CHANGENICK" and len(parts) >= 2:
            self.handle_change_nickname(parts[1], client, sender, user_id)
        
        elif cmd == "CHANGEPASS" and len(parts) >= 4:
            self.handle_change_password(parts, client, sender, user_id)
        
        # ========== СТАТУС ПЕЧАТИ ==========
        elif cmd == "TYPING" and len(parts) >= 2:
            self.handle_typing(parts[1], client, sender)
        
        else:
            logger.warning(f"Unknown command from {sender}: {cmd}")
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ❌ Неизвестная команда: {cmd}")
    
    # ========== ОБРАБОТЧИКИ КОМАНД ==========
    
    def handle_private_message(self, parts: List[str], client: socket.socket, sender: str):
        """Отправка приватного сообщения"""
        target = parts[1]
        msg = "|".join(parts[2:])
        msg = SecurityValidator.sanitize_text(msg)
        
        if not msg:
            return
        
        # Проверка на блокировку (безопасно, даже если privacy отсутствует)
        is_blocked = False
        if hasattr(self.server, 'privacy') and self.server.privacy:
            if hasattr(self.server.privacy, 'is_blocked'):
                is_blocked = self.server.privacy.is_blocked(sender, target)
        
        if is_blocked:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Вы заблокированы этим пользователем")
            return
        
        chat_id = self.get_chat_id(sender, target)
        message = {
            'id': f"pm_{int(time.time()*1000)}",
            'sender': sender,
            'text': msg,
            'time': datetime.now().strftime("%H:%M:%S")
        }
        
        # Сохраняем в БД
        self.server.storage.db.save_private_message(sender, target, msg)
        
        # Поиск получателя онлайн
        target_socket = None
        for sock, data in self.server.client_data.items():
            if data.get('nickname') == target:
                target_socket = sock
                break
        
        if target_socket:
            self.server.network.send_to_client(target_socket, "JSON_PAYLOAD:" + json.dumps({
                "type": "private_message", 
                "from": sender, 
                "text": msg,
                "time": message['time']
            }, ensure_ascii=False))
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                "type": "private_sent", 
                "to": target, 
                "text": msg
            }, ensure_ascii=False))
        else:
            # Сохраняем оффлайн-сообщение
            self.server.storage.save_offline_message(target, sender, msg, is_private=True)
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                "type": "private_sent_offline", 
                "to": target, 
                "text": msg
            }, ensure_ascii=False))
            logger.info(f"Offline message saved from {sender} to {target}")
    
    def handle_get_pm_history(self, target: str, client: socket.socket, sender: str):
        """Получение истории приватных сообщений"""
        messages = self.server.storage.get_private_messages(sender, target, 100)
        
        formatted = []
        for m in messages:
            formatted.append({
                'sender': m.get('sender', ''),
                'text': m.get('message', ''),
                'time': m.get('timestamp', '')[11:16] if m.get('timestamp') else ""
            })
        
        self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
            "type": "private_history", 
            "target": target, 
            "messages": formatted
        }, ensure_ascii=False))
    
    def handle_get_online(self, client: socket.socket):
        """Отправка списка онлайн пользователей"""
        users = [data['nickname'] for data in self.server.client_data.values()]
        self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
            "type": "online_users", 
            "users": users
        }, ensure_ascii=False))
    
    def handle_change_color(self, color: str, client: socket.socket, sender: str):
        """Смена цвета ника"""
        if not color.startswith('#'):
            color = '#' + color
        self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
            "type": "color_update", 
            "nick": sender, 
            "color": color
        }, ensure_ascii=False))
    
    def handle_friend_request(self, target: str, client: socket.socket, sender: str, user_id: int):
        """Отправка запроса в друзья"""
        target_user = self.server.storage.get_user_by_nickname(target)
        if not target_user:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Пользователь не найден")
            return
        
        # Добавляем в таблицу друзей
        try:
            self.server.storage.db.add_friend(user_id, target_user['id'])
        except Exception as e:
            logger.error(f"Add friend error: {e}")
        
        target_socket = None
        for sock, data in self.server.client_data.items():
            if data.get('nickname') == target:
                target_socket = sock
                break
        
        if target_socket:
            self.server.network.send_to_client(target_socket, "JSON_PAYLOAD:" + json.dumps({
                "type": "friend_request", 
                "from": sender
            }, ensure_ascii=False))
        
        self.server.network.send_to_client(client, "MSG:СЕРВЕР: ✅ Запрос отправлен")
    
    def handle_accept_friend(self, target: str, client: socket.socket, sender: str, user_id: int):
        """Принятие запроса в друзья"""
        logger.info(f"Friend request accepted: {target} -> {sender}")
        self.server.network.send_to_client(client, "MSG:СЕРВЕР: ✅ Пользователь добавлен в друзья")
    
    def handle_decline_friend(self, target: str, sender: str):
        """Отклонение запроса в друзья"""
        logger.info(f"Friend request declined: {target} -> {sender}")
    
    # ========== УПРАВЛЕНИЕ ГРУППАМИ ==========
    
    def handle_create_group(self, group_name: str, client: socket.socket, sender: str, user_id: int):
        """Создание новой группы"""
        valid, err = SecurityValidator.validate_group_name(group_name)
        if not valid:
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ❌ {err}")
            return
        
        existing = self.server.storage.get_group_by_name(group_name)
        if existing:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Группа уже существует")
            return
        
        group_id = self.server.storage.create_group(group_name, user_id)
        if group_id:
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                "type": "group_created", 
                "group": group_name
            }, ensure_ascii=False))
            logger.success(f"Group created: {group_name} by {sender}")
        else:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Ошибка создания группы")
    
    def handle_rename_group(self, old_name: str, new_name: str, client: socket.socket, sender: str, user_id: int):
        """Переименование группы (только создатель)"""
        group = self.server.storage.get_group_by_name(old_name)
        if not group:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Группа не найдена")
            return
        
        if group['creator_id'] != user_id:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Только создатель может переименовать группу")
            return
        
        valid, err = SecurityValidator.validate_group_name(new_name)
        if not valid:
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ❌ {err}")
            return
        
        if self.server.storage.rename_group(group['id'], new_name):
            members = self.server.storage.get_group_member_names(group['id'])
            
            for sock, data in self.server.client_data.items():
                if data.get('nickname') in members:
                    self.server.network.send_to_client(sock, "JSON_PAYLOAD:" + json.dumps({
                        "type": "group_renamed",
                        "old_name": old_name,
                        "new_name": new_name
                    }, ensure_ascii=False))
            
            logger.admin(f"Group renamed: {old_name} -> {new_name} by {sender}")
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ✅ Группа переименована в {new_name}")
        else:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Ошибка переименования")
    
    def handle_add_to_group(self, group_name: str, member: str, client: socket.socket, sender: str, user_id: int):
        """Добавление участника в группу"""
        group = self.server.storage.get_group_by_name(group_name)
        if not group:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Группа не найдена")
            return
        
        member_user = self.server.storage.get_user_by_nickname(member)
        if not member_user:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Пользователь не найден")
            return
        
        if self.server.storage.add_group_member(group['id'], member_user['id']):
            members = self.server.storage.get_group_member_names(group['id'])
            
            for sock, data in self.server.client_data.items():
                if data.get('nickname') in members:
                    self.server.network.send_to_client(sock, "JSON_PAYLOAD:" + json.dumps({
                        "type": "group_member_added",
                        "group": group_name,
                        "member": member
                    }, ensure_ascii=False))
            
            logger.info(f"User {member} added to group {group_name} by {sender}")
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ✅ {member} добавлен в группу")
        else:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Ошибка добавления")
    
    def handle_remove_from_group(self, group_name: str, member: str, client: socket.socket, sender: str, user_id: int):
        """Удаление участника из группы"""
        group = self.server.storage.get_group_by_name(group_name)
        if not group:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Группа не найдена")
            return
        
        if group['creator_id'] != user_id and sender != member:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Только создатель может удалять участников")
            return
        
        member_user = self.server.storage.get_user_by_nickname(member)
        if not member_user:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Пользователь не найден")
            return
        
        if self.server.storage.remove_group_member(group['id'], member_user['id']):
            members = self.server.storage.get_group_member_names(group['id'])
            
            for sock, data in self.server.client_data.items():
                if data.get('nickname') in members:
                    self.server.network.send_to_client(sock, "JSON_PAYLOAD:" + json.dumps({
                        "type": "group_member_removed",
                        "group": group_name,
                        "member": member
                    }, ensure_ascii=False))
            
            logger.info(f"User {member} removed from group {group_name} by {sender}")
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ✅ {member} удалён из группы")
        else:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Ошибка удаления")
    
    def handle_delete_group(self, group_name: str, client: socket.socket, sender: str, user_id: int):
        """Удаление группы (только создатель)"""
        group = self.server.storage.get_group_by_name(group_name)
        if not group:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Группа не найдена")
            return
        
        if group['creator_id'] != user_id:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Только создатель может удалить группу")
            return
        
        members = self.server.storage.get_group_member_names(group['id'])
        
        if self.server.storage.delete_group(group['id']):
            for sock, data in self.server.client_data.items():
                if data.get('nickname') in members:
                    self.server.network.send_to_client(sock, "JSON_PAYLOAD:" + json.dumps({
                        "type": "group_deleted",
                        "group": group_name
                    }, ensure_ascii=False))
            
            logger.admin(f"Group deleted: {group_name} by {sender}")
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ✅ Группа {group_name} удалена")
        else:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Ошибка удаления группы")
    
    def handle_leave_group(self, group_name: str, client: socket.socket, sender: str, user_id: int):
        """Выход из группы"""
        group = self.server.storage.get_group_by_name(group_name)
        if not group:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Группа не найдена")
            return
        
        if self.server.storage.remove_group_member(group['id'], user_id):
            members = self.server.storage.get_group_member_names(group['id'])
            
            for sock, data in self.server.client_data.items():
                if data.get('nickname') in members:
                    self.server.network.send_to_client(sock, "JSON_PAYLOAD:" + json.dumps({
                        "type": "group_member_removed",
                        "group": group_name,
                        "member": sender
                    }, ensure_ascii=False))
            
            self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                "type": "left_group",
                "group": group_name
            }, ensure_ascii=False))
            
            logger.info(f"User {sender} left group {group_name}")
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ✅ Вы вышли из группы {group_name}")
        else:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Ошибка выхода из группы")
    
    def handle_group_message(self, parts: List[str], client: socket.socket, sender: str, user_id: int):
        """Отправка сообщения в группу"""
        group_name = parts[1]
        text = "|".join(parts[2:])
        text = SecurityValidator.sanitize_text(text)
        
        if not text:
            return
        
        group = self.server.storage.get_group_by_name(group_name)
        if not group:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Группа не найдена")
            return
        
        members = self.server.storage.get_group_member_names(group['id'])
        if sender not in members:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Вы не участник этой группы")
            return
        
        msg_id = f"group_{int(time.time()*1000)}"
        message = {
            "id": msg_id,
            "sender": sender,
            "text": text,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
        self.server.storage.save_group_message(group['id'], user_id, sender, text)
        
        for sock, data in self.server.client_data.items():
            if data.get('nickname') in members:
                self.server.network.send_to_client(sock, "JSON_PAYLOAD:" + json.dumps({
                    "type": "group_message",
                    "group": group_name,
                    "data": message
                }, ensure_ascii=False))
        
        logger.chat(sender, f"[GROUP {group_name}] {text}")
    
    # ========== АККАУНТ ==========
    
    def handle_change_nickname(self, new_nickname: str, client: socket.socket, sender: str, user_id: int):
        """Смена никнейма"""
        valid, err = SecurityValidator.validate_nickname(new_nickname)
        if not valid:
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ❌ {err}")
            return
        
        if self.server.storage.update_user_nickname(sender, new_nickname):
            old_nickname = sender
            
            for sock, data in self.server.client_data.items():
                if data.get('nickname') == old_nickname:
                    data['nickname'] = new_nickname
                
                self.server.network.send_to_client(sock, "JSON_PAYLOAD:" + json.dumps({
                    "type": "nickname_changed",
                    "old": old_nickname,
                    "new": new_nickname
                }, ensure_ascii=False))
            
            logger.info(f"Nickname changed: {old_nickname} -> {new_nickname}")
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ✅ Никнейм изменён на {new_nickname}")
        else:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Ошибка смены никнейма")
    
    def handle_change_password(self, parts: List[str], client: socket.socket, sender: str, user_id: int):
        """Смена пароля"""
        if len(parts) < 4:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Недостаточно параметров")
            return
        
        username = parts[1]
        old_password_b64 = parts[2]
        new_password_b64 = parts[3]
        
        import base64
        try:
            old_password = base64.b64decode(old_password_b64).decode()
            new_password = base64.b64decode(new_password_b64).decode()
        except:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Ошибка декодирования пароля")
            return
        
        user = self.server.storage.get_user(username)
        if not user or user['id'] != user_id:
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Доступ запрещён")
            return
        
        from security import SimpleHash
        if not SimpleHash.verify_password(old_password, user.get('salt', ''), user.get('password_hash', '')):
            self.server.network.send_to_client(client, "MSG:СЕРВЕР: ❌ Неверный старый пароль")
            return
        
        valid, err = SecurityValidator.validate_password(new_password)
        if not valid:
            self.server.network.send_to_client(client, f"MSG:СЕРВЕР: ❌ {err}")
            return
        
        new_salt = SimpleHash.generate_salt()
        new_hash = SimpleHash.hash_password(new_password, new_salt)
        
        with self.server.storage.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET password_hash = ?, salt = ? WHERE id = ?', 
                          (new_hash, new_salt, user_id))
        
        self.server.network.send_to_client(client, "MSG:СЕРВЕР: ✅ Пароль успешно изменён")
        logger.info(f"Password changed for user {username}")
    
    def handle_typing(self, target: str, client: socket.socket, sender: str):
        """Уведомление о печати"""
        target_socket = None
        for sock, data in self.server.client_data.items():
            if data.get('nickname') == target:
                target_socket = sock
                break
        
        if target_socket:
            self.server.network.send_to_client(target_socket, "JSON_PAYLOAD:" + json.dumps({
                "type": "typing",
                "nick": sender
            }, ensure_ascii=False))
    
    def cleanup_client(self, client: socket.socket, nickname: str):
        """Очистка при отключении клиента"""
        if client in self.server.clients:
            self.server.clients.remove(client)
        if client in self.server.client_data:
            del self.server.client_data[client]
        
        try:
            client.close()
        except:
            pass
        
        self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
            "type": "notification", 
            "text": f"{nickname} покинул чат"
        }, ensure_ascii=False))
        
        # Обновляем список онлайн
        online_users = [data['nickname'] for data in self.server.client_data.values()]
        self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
            "type": "online_users",
            "users": online_users
        }, ensure_ascii=False))
        
        logger.info(f"Client disconnected: {nickname} | Online: {len(self.server.clients)}")
        
        if hasattr(self.server, 'update_online_display'):
            self.server.update_online_display()