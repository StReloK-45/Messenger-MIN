# client/ui/main_window/chat_handlers.py
import datetime
import time
from tkinter import messagebox
from typing import Dict, Any, List, Optional


class ChatHandlers:
    """Обработчик всех серверных сообщений"""
    
    def __init__(self, ui):
        self.ui = ui
        self._last_notification_time = 0
        self._notification_cooldown = 2  # секунды
    
    def handle_server_message(self, msg: Dict[str, Any]):
        """Главный обработчик сообщений от сервера"""
        msg_type = msg.get("type")
        
        # ========== ИСТОРИЯ И СООБЩЕНИЯ ==========
        if msg_type == "history":
            self._handle_history(msg)
        
        elif msg_type == "message":
            self._handle_message(msg)
        
        elif msg_type == "message_deleted":
            self._handle_message_deleted(msg)
        
        elif msg_type == "message_edited":
            self._handle_message_edited(msg)
        
        # ========== ПРИВАТНЫЕ СООБЩЕНИЯ ==========
        elif msg_type == "private_message":
            self._handle_private_message(msg)
        
        elif msg_type == "private_sent":
            self._handle_private_sent(msg)
        
        elif msg_type == "private_sent_offline":
            self._handle_private_sent_offline(msg)
        
        elif msg_type == "private_history":
            self._handle_private_history(msg)
        
        elif msg_type == "offline_message":
            self._handle_offline_message(msg)
        
        # ========== ГРУППЫ ==========
        elif msg_type == "user_groups":
            self._handle_user_groups(msg)
        
        elif msg_type == "group_created":
            self._handle_group_created(msg)
        
        elif msg_type == "group_renamed":
            self._handle_group_renamed(msg)
        
        elif msg_type == "group_deleted":
            self._handle_group_deleted(msg)
        
        elif msg_type == "left_group":
            self._handle_left_group(msg)
        
        elif msg_type == "group_message":
            self._handle_group_message(msg)
        
        elif msg_type == "group_history":
            self._handle_group_history(msg)
        
        elif msg_type == "group_members":
            self._handle_group_members(msg)
        
        elif msg_type == "group_member_added":
            self._handle_group_member_added(msg)
        
        elif msg_type == "group_member_removed":
            self._handle_group_member_removed(msg)
        
        elif msg_type == "group_notification":
            self._handle_group_notification(msg)
        
        # ========== ФАЙЛЫ ==========
        elif msg_type == "file":
            self._handle_file(msg)
        
        elif msg_type == "private_file":
            self._handle_private_file(msg)
        
        elif msg_type == "group_file":
            self._handle_group_file(msg)
        
        elif msg_type == "file_deleted":
            self._handle_file_deleted(msg)
        
        # ========== ПОЛЬЗОВАТЕЛИ И СТАТУСЫ ==========
        elif msg_type == "online_users":
            self._handle_online_users(msg)
        
        elif msg_type == "user_online":
            self._handle_user_online(msg)
        
        elif msg_type == "user_offline":
            self._handle_user_offline(msg)
        
        elif msg_type == "users_list":
            self._handle_users_list(msg)
        
        elif msg_type == "nickname_changed":
            self._handle_nickname_changed(msg)
        
        elif msg_type == "color_update":
            self._handle_color_update(msg)
        
        # ========== ДРУЗЬЯ ==========
        elif msg_type == "friends_list":
            self._handle_friends_list(msg)
        
        elif msg_type == "friend_request":
            self._handle_friend_request(msg)
        
        elif msg_type == "friend_accepted":
            self._handle_friend_accepted(msg)
        
        # ========== УВЕДОМЛЕНИЯ ==========
        elif msg_type == "notification":
            self._handle_notification(msg)
        
        elif msg_type == "announcement":
            self._handle_announcement(msg)
        
        elif msg_type == "kicked":
            self._handle_kicked(msg)
        
        elif msg_type == "banned":
            self._handle_banned(msg)
        
        elif msg_type == "maintenance":
            self._handle_maintenance(msg)
        
        # ========== СТАТУС ПЕЧАТИ ==========
        elif msg_type == "typing":
            self._handle_typing(msg)
        
        # ========== ПОДКЛЮЧЕНИЕ ==========
        elif msg_type == "connected":
            self._handle_connected(msg)
        
        elif msg_type == "ping":
            self._handle_ping(msg)
        
        elif msg_type == "pong":
            pass  # игнорируем
        
        else:
            # Неизвестный тип сообщения
            print(f"[DEBUG] Unknown message type: {msg_type}")
    
    # ========== ИСТОРИЯ И СООБЩЕНИЯ ==========
    
    def _handle_history(self, msg: Dict[str, Any]):
        """Обработка истории сообщений"""
        messages = msg.get("messages", [])
        files = msg.get("files", [])
        
        print(f"[DEBUG] Received history: {len(messages)} messages, {len(files)} files")
        
        self.ui.message_history = messages
        self.ui.files_list = files
        
        # Очищаем поле сообщений
        for widget in self.ui.ui_components.messages_frame.winfo_children():
            widget.destroy()
        
        # Отображаем сообщения
        for m in messages:
            try:
                sender = m.get('sender', '')
                text = m.get('text', '')
                msg_time = m.get('time', '')
                is_my = (sender == self.ui.app.settings.nickname)
                self.ui.display_bubble_message(sender, text, msg_time, is_my)
            except Exception as e:
                print(f"[DEBUG] Error displaying message: {e}")
        
        # Обновляем список файлов
        if hasattr(self.ui.right_panel, 'update_files_list'):
            self.ui.right_panel.update_files_list()
        
        self.ui.scroll_manager.force_scroll_to_bottom()
        self.ui.left_panel.update_chats_list()
    
    def _handle_message(self, msg: Dict[str, Any]):
        """Обработка нового сообщения в общем чате"""
        data = msg.get("data", {})
        sender = data.get('sender', '')
        text = data.get('text', '')
        msg_time = data.get('time', '')
        is_my = (sender == self.ui.app.settings.nickname)
        
        self.ui.message_history.append(data)
        
        if self.ui.current_chat_type == "general":
            self.ui.display_bubble_message(sender, text, msg_time, is_my)
            self._notify_new_message(sender, "general")
    
    def _handle_message_deleted(self, msg: Dict[str, Any]):
        """Обработка удаления сообщения"""
        msg_id = msg.get("id", "")
        self.ui.add_system_message(f"Сообщение {msg_id} удалено администратором")
    
    def _handle_message_edited(self, msg: Dict[str, Any]):
        """Обработка редактирования сообщения"""
        msg_id = msg.get("id", "")
        new_text = msg.get("text", "")
        self.ui.add_system_message(f"Сообщение {msg_id} отредактировано: {new_text[:50]}...")
    
    # ========== ПРИВАТНЫЕ СООБЩЕНИЯ ==========
    
    def _handle_private_message(self, msg: Dict[str, Any]):
        """Обработка полученного приватного сообщения"""
        sender = msg.get("from", "")
        text = msg.get("text", "")
        time_str = msg.get("time", datetime.datetime.now().strftime("%H:%M:%S"))
        
        # Добавляем в список чатов
        if sender not in self.ui.private_chats_list:
            self.ui.private_chats_list.add(sender)
            self.ui.left_panel.update_chats_list()
        
        # Сохраняем сообщение
        if sender not in self.ui.private_messages:
            self.ui.private_messages[sender] = []
        
        self.ui.private_messages[sender].append({
            'sender': sender,
            'text': text,
            'time': time_str
        })
        
        # Отображаем если активен этот чат
        if self.ui.current_chat == sender and self.ui.current_chat_type == "private":
            self.ui.display_bubble_message(sender, text, time_str, is_my=False)
        else:
            self._show_notification(f"Новое сообщение от {sender}", "private")
            self._notify_new_message(sender, "private")
    
    def _handle_private_sent(self, msg: Dict[str, Any]):
        """Обработка отправленного приватного сообщения"""
        target = msg.get("to", "")
        text = msg.get("text", "")
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        
        if target not in self.ui.private_chats_list:
            self.ui.private_chats_list.add(target)
            self.ui.left_panel.update_chats_list()
        
        if target not in self.ui.private_messages:
            self.ui.private_messages[target] = []
        
        self.ui.private_messages[target].append({
            'sender': self.ui.app.settings.nickname,
            'text': text,
            'time': time_str
        })
        
        if self.ui.current_chat == target and self.ui.current_chat_type == "private":
            self.ui.display_bubble_message(
                self.ui.app.settings.nickname, text, time_str, is_my=True
            )
    
    def _handle_private_sent_offline(self, msg: Dict[str, Any]):
        """Обработка отправки оффлайн-сообщения"""
        target = msg.get("to", "")
        text = msg.get("text", "")
        self.ui.add_system_message(f"Сообщение сохранено для {target} (пользователь оффлайн)")
    
    def _handle_private_history(self, msg: Dict[str, Any]):
        """Обработка истории приватных сообщений"""
        target = msg.get("target", "")
        messages = msg.get("messages", [])
        
        print(f"[DEBUG] Received private history with {target}: {len(messages)} messages")
        
        if target not in self.ui.private_chats_list:
            self.ui.private_chats_list.add(target)
            self.ui.left_panel.update_chats_list()
        
        self.ui.private_messages[target] = messages
        
        if self.ui.current_chat == target and self.ui.current_chat_type == "private":
            # Очищаем и отображаем
            for widget in self.ui.ui_components.messages_frame.winfo_children():
                widget.destroy()
            
            for m in messages:
                sender = m.get('sender', '')
                text = m.get('text', '')
                msg_time = m.get('time', '')
                is_my = (sender == self.ui.app.settings.nickname)
                self.ui.display_bubble_message(sender, text, msg_time, is_my)
            
            self.ui.scroll_manager.force_scroll_to_bottom()
    
    def _handle_offline_message(self, msg: Dict[str, Any]):
        """Обработка оффлайн-сообщения при подключении"""
        sender = msg.get("from", "")
        text = msg.get("message", "")
        timestamp = msg.get("timestamp", "")
        
        time_str = timestamp[11:16] if len(timestamp) > 16 else datetime.datetime.now().strftime("%H:%M:%S")
        
        self.ui.add_system_message(f"📬 Оффлайн сообщение от {sender}: {text[:50]}...")
        
        # Сохраняем в приватные сообщения
        if sender not in self.ui.private_chats_list:
            self.ui.private_chats_list.add(sender)
        
        if sender not in self.ui.private_messages:
            self.ui.private_messages[sender] = []
        
        self.ui.private_messages[sender].append({
            'sender': sender,
            'text': text,
            'time': time_str
        })
    
    # ========== ГРУППЫ ==========
    
    def _handle_user_groups(self, msg: Dict[str, Any]):
        """Обработка списка групп пользователя"""
        groups = msg.get("groups", [])
        
        for group_name in groups:
            if group_name not in self.ui.group_chats:
                self.ui.group_chats[group_name] = {
                    "members": set(),
                    "messages": [],
                    "files": []
                }
        
        self.ui.left_panel.update_chats_list()
        print(f"[DEBUG] User groups: {groups}")
    
    def _handle_group_created(self, msg: Dict[str, Any]):
        """Обработка создания группы"""
        group_name = msg.get("group", "")
        self.ui.add_system_message(f"Группа '{group_name}' создана!")
    
    def _handle_group_renamed(self, msg: Dict[str, Any]):
        """Обработка переименования группы"""
        old_name = msg.get("old_name", "")
        new_name = msg.get("new_name", "")
        
        # Обновляем локальные данные
        if old_name in self.ui.group_chats:
            self.ui.group_chats[new_name] = self.ui.group_chats.pop(old_name)
        
        # Обновляем текущий чат если нужно
        if self.ui.current_chat == old_name:
            self.ui.current_chat = new_name
            self.ui.ui_components.chat_header.config(text=f"👥 {new_name}")
        
        self.ui.left_panel.update_chats_list()
        self.ui.add_system_message(f"Группа переименована: {old_name} -> {new_name}")
    
    def _handle_group_deleted(self, msg: Dict[str, Any]):
        """Обработка удаления группы"""
        group_name = msg.get("group", "")
        
        if group_name in self.ui.group_chats:
            del self.ui.group_chats[group_name]
        
        if self.ui.current_chat == group_name:
            self.ui.current_chat = "general"
            self.ui.current_chat_type = "general"
            self.ui.ui_components.chat_header.config(text="💬 Общий чат")
            # Очищаем поле сообщений
            for widget in self.ui.ui_components.messages_frame.winfo_children():
                widget.destroy()
            # Загружаем общий чат
            for m in self.ui.message_history:
                sender = m.get('sender', '')
                text = m.get('text', '')
                msg_time = m.get('time', '')
                is_my = (sender == self.ui.app.settings.nickname)
                self.ui.display_bubble_message(sender, text, msg_time, is_my)
        
        self.ui.left_panel.update_chats_list()
        self.ui.add_system_message(f"Группа '{group_name}' удалена")
    
    def _handle_left_group(self, msg: Dict[str, Any]):
        """Обработка выхода из группы"""
        group_name = msg.get("group", "")
        
        if group_name in self.ui.group_chats:
            del self.ui.group_chats[group_name]
        
        if self.ui.current_chat == group_name:
            self.ui.current_chat = "general"
            self.ui.current_chat_type = "general"
            self.ui.ui_components.chat_header.config(text="💬 Общий чат")
            # Очищаем и загружаем общий чат
            for widget in self.ui.ui_components.messages_frame.winfo_children():
                widget.destroy()
            for m in self.ui.message_history:
                sender = m.get('sender', '')
                text = m.get('text', '')
                msg_time = m.get('time', '')
                is_my = (sender == self.ui.app.settings.nickname)
                self.ui.display_bubble_message(sender, text, msg_time, is_my)
        
        self.ui.left_panel.update_chats_list()
        self.ui.add_system_message(f"Вы вышли из группы '{group_name}'")
    
    def _handle_group_message(self, msg: Dict[str, Any]):
        """Обработка сообщения в группе"""
        group_name = msg.get("group", "")
        data = msg.get("data", {})
        
        sender = data.get('sender', '')
        text = data.get('text', '')
        msg_time = data.get('time', '')
        is_my = (sender == self.ui.app.settings.nickname)
        
        # Сохраняем в историю группы
        if group_name in self.ui.group_chats:
            self.ui.group_chats[group_name]["messages"].append(data)
        
        # Отображаем если активна эта группа
        if self.ui.current_chat == group_name and self.ui.current_chat_type == "group":
            self.ui.display_bubble_message(sender, text, msg_time, is_my)
            self._notify_new_message(f"{group_name} от {sender}", "group")
    
    def _handle_group_history(self, msg: Dict[str, Any]):
        """Обработка истории группы"""
        group_name = msg.get("group", "")
        messages = msg.get("messages", [])
        files = msg.get("files", [])
        
        if group_name not in self.ui.group_chats:
            self.ui.group_chats[group_name] = {"members": set(), "messages": [], "files": []}
        
        self.ui.group_chats[group_name]["messages"] = messages
        self.ui.group_chats[group_name]["files"] = files
        
        if self.ui.current_chat == group_name and self.ui.current_chat_type == "group":
            # Очищаем и отображаем
            for widget in self.ui.ui_components.messages_frame.winfo_children():
                widget.destroy()
            
            for m in messages:
                sender = m.get('sender', '')
                text = m.get('text', '')
                msg_time = m.get('time', '')
                is_my = (sender == self.ui.app.settings.nickname)
                self.ui.display_bubble_message(sender, text, msg_time, is_my)
            
            self.ui.scroll_manager.force_scroll_to_bottom()
    
    def _handle_group_members(self, msg: Dict[str, Any]):
        """Обработка списка участников группы"""
        group_name = msg.get("group", "")
        members = msg.get("members", [])
        
        if group_name in self.ui.group_chats:
            old_count = len(self.ui.group_chats[group_name].get("members", set()))
            self.ui.group_chats[group_name]["members"] = set(members)
            new_count = len(members)
            
            if new_count > old_count:
                self.ui.add_system_message(f"В группу '{group_name}' добавлен новый участник")
            elif new_count < old_count:
                self.ui.add_system_message(f"Из группы '{group_name}' вышел участник")
    
    def _handle_group_member_added(self, msg: Dict[str, Any]):
        """Обработка добавления участника в группу"""
        group_name = msg.get("group", "")
        member = msg.get("member", "")
        
        if group_name in self.ui.group_chats:
            self.ui.group_chats[group_name]["members"].add(member)
        
        if self.ui.current_chat == group_name:
            self.ui.add_system_message(f"👥 {member} присоединился к группе")
    
    def _handle_group_member_removed(self, msg: Dict[str, Any]):
        """Обработка удаления участника из группы"""
        group_name = msg.get("group", "")
        member = msg.get("member", "")
        reason = msg.get("reason", "")
        
        if group_name in self.ui.group_chats and member in self.ui.group_chats[group_name]["members"]:
            self.ui.group_chats[group_name]["members"].discard(member)
        
        if self.ui.current_chat == group_name:
            if reason:
                self.ui.add_system_message(f"{member} покинул группу ({reason})")
            else:
                self.ui.add_system_message(f"{member} покинул группу")
        
        # Если удалили нас
        if member == self.ui.app.settings.nickname:
            if group_name in self.ui.group_chats:
                del self.ui.group_chats[group_name]
            
            if self.ui.current_chat == group_name:
                self.ui.current_chat = "general"
                self.ui.current_chat_type = "general"
                self.ui.ui_components.chat_header.config(text="💬 Общий чат")
                # Очищаем и загружаем общий чат
                for widget in self.ui.ui_components.messages_frame.winfo_children():
                    widget.destroy()
                for m in self.ui.message_history:
                    sender = m.get('sender', '')
                    text = m.get('text', '')
                    msg_time = m.get('time', '')
                    is_my = (sender == self.ui.app.settings.nickname)
                    self.ui.display_bubble_message(sender, text, msg_time, is_my)
            
            self.ui.left_panel.update_chats_list()
            self.ui.add_system_message(f"Вы были удалены из группы '{group_name}'")
    
    def _handle_group_notification(self, msg: Dict[str, Any]):
        """Обработка уведомления в группе"""
        text = msg.get("text", "")
        self.ui.add_system_message(text)
    
    # ========== ФАЙЛЫ ==========
    
    def _handle_file(self, msg: Dict[str, Any]):
        """Обработка файла в общем чате"""
        file_data = msg.get("data", {})
        
        self.ui.files_list.append(file_data)
        
        if hasattr(self.ui.right_panel, 'update_files_list'):
            self.ui.right_panel.update_files_list()
        
        self.ui.add_system_message(
            f"📁 {file_data.get('sender', '')} отправил файл: {file_data.get('name', '')}"
        )
    
    def _handle_private_file(self, msg: Dict[str, Any]):
        """Обработка файла в приватном чате"""
        file_data = msg.get("data", {})
        target = msg.get("target", "")
        
        if target not in self.ui.private_files:
            self.ui.private_files[target] = []
        
        self.ui.private_files[target].append(file_data)
        
        if self.ui.current_chat == target and self.ui.current_chat_type == "private":
            if hasattr(self.ui.right_panel, 'update_files_list'):
                self.ui.right_panel.update_files_list()
        
        self.ui.add_system_message(
            f"📁 {file_data.get('sender', '')} отправил файл: {file_data.get('name', '')}"
        )
    
    def _handle_group_file(self, msg: Dict[str, Any]):
        """Обработка файла в группе"""
        file_data = msg.get("data", {})
        group_name = msg.get("group", "")
        
        if group_name in self.ui.group_chats:
            if "files" not in self.ui.group_chats[group_name]:
                self.ui.group_chats[group_name]["files"] = []
            self.ui.group_chats[group_name]["files"].append(file_data)
        
        if self.ui.current_chat == group_name and self.ui.current_chat_type == "group":
            if hasattr(self.ui.right_panel, 'update_files_list'):
                self.ui.right_panel.update_files_list()
        
        self.ui.add_system_message(
            f"📁 {file_data.get('sender', '')} отправил файл в группу '{group_name}': {file_data.get('name', '')}"
        )
    
    def _handle_file_deleted(self, msg: Dict[str, Any]):
        """Обработка удаления файла"""
        file_id = msg.get("id", "")
        name = msg.get("name", "")
        self.ui.add_system_message(f"Файл '{name}' удалён")
        
        # Обновляем списки файлов
        if hasattr(self.ui.right_panel, 'update_files_list'):
            self.ui.right_panel.update_files_list()
    
    # ========== ПОЛЬЗОВАТЕЛИ И СТАТУСЫ ==========
    
    def _handle_online_users(self, msg: Dict[str, Any]):
        """Обработка списка онлайн пользователей"""
        users = msg.get("users", [])
        users_count = len(users)
        self.ui.top_bar.set_status(f"онлайн ({users_count})")
    
    def _handle_user_online(self, msg: Dict[str, Any]):
        """Обработка события входа пользователя"""
        username = msg.get("username", "")
        self.ui.add_system_message(f"🟢 {username} вошёл в чат")
    
    def _handle_user_offline(self, msg: Dict[str, Any]):
        """Обработка события выхода пользователя"""
        username = msg.get("username", "")
        self.ui.add_system_message(f"⚫ {username} вышел из чата")
    
    def _handle_users_list(self, msg: Dict[str, Any]):
        """Обработка списка пользователей"""
        users = msg.get("users", [])
        # Можно использовать для обновления списка друзей
        pass
    
    def _handle_nickname_changed(self, msg: Dict[str, Any]):
        """Обработка смены никнейма"""
        old = msg.get("old", "")
        new = msg.get("new", "")
        
        # Обновляем локальные данные
        if old in self.ui.private_chats_list:
            self.ui.private_chats_list.remove(old)
            self.ui.private_chats_list.add(new)
        
        if old in self.ui.friends_list:
            self.ui.friends_list.remove(old)
            self.ui.friends_list.add(new)
        
        # Обновляем текущий чат
        if self.ui.current_chat == old:
            self.ui.current_chat = new
        
        # Обновляем группы
        for group_name, group_data in self.ui.group_chats.items():
            if old in group_data.get("members", set()):
                group_data["members"].remove(old)
                group_data["members"].add(new)
        
        self.ui.left_panel.update_chats_list()
        self.ui.add_system_message(f"✏️ {old} сменил ник на {new}")
    
    def _handle_color_update(self, msg: Dict[str, Any]):
        """Обработка обновления цвета ника"""
        nick = msg.get("nick", "")
        color = msg.get("color", "")
        
        if nick and color:
            self.ui.color_manager.nick_colors[nick] = color
    
    # ========== ДРУЗЬЯ ==========
    
    def _handle_friends_list(self, msg: Dict[str, Any]):
        """Обработка списка друзей"""
        friends = msg.get("friends", [])
        print(f"[DEBUG] Friends list received: {friends}")
        
        self.ui.friends_list = set(friends)
        self.ui.save_friends()
        
        if friends:
            self.ui.add_system_message(f"👥 В вашем списке {len(friends)} друзей")
    
    def _handle_friend_request(self, msg: Dict[str, Any]):
        """Обработка запроса в друзья"""
        from_user = msg.get("from", "")
        
        result = messagebox.askyesno(
            "Запрос в друзья",
            f"Пользователь {from_user} хочет добавить вас в друзья. Согласны?",
            parent=self.ui.app.root
        )
        
        if result:
            self.ui.app.network.send_raw(f"CMD:ACCEPT_FRIEND|{from_user}")
            self.ui.add_system_message(f"✅ Вы добавили {from_user} в друзья")
        else:
            self.ui.app.network.send_raw(f"CMD:DECLINE_FRIEND|{from_user}")
    
    def _handle_friend_accepted(self, msg: Dict[str, Any]):
        """Обработка принятия запроса в друзья"""
        from_user = msg.get("from", "")
        self.ui.add_system_message(f"🎉 {from_user} принял(а) ваш запрос в друзья!")
        
        self.ui.friends_list.add(from_user)
        self.ui.save_friends()
    
    # ========== УВЕДОМЛЕНИЯ ==========
    
    def _handle_notification(self, msg: Dict[str, Any]):
        """Обработка обычного уведомления"""
        text = msg.get("text", "")
        self.ui.add_system_message(text)
    
    def _handle_announcement(self, msg: Dict[str, Any]):
        """Обработка объявления от администратора"""
        text = msg.get("text", "")
        from_user = msg.get("from", "ADMIN")
        
        self.ui.add_system_message(f"📢 ОБЪЯВЛЕНИЕ от {from_user}: {text}")
        
        # Мигаем окном при важном объявлении
        if hasattr(self.ui.app, 'notifications'):
            self.ui.app.notifications.flash_taskbar()
    
    def _handle_kicked(self, msg: Dict[str, Any]):
        """Обработка кика"""
        reason = msg.get("reason", "Кикнут администратором")
        messagebox.showwarning("Кик", f"Вы были кикнуты с сервера!\nПричина: {reason}")
        self.ui.app.network.disconnect()
        self.ui.app.root.quit()
    
    def _handle_banned(self, msg: Dict[str, Any]):
        """Обработка бана"""
        reason = msg.get("reason", "Забанен администратором")
        messagebox.showerror("Бан", f"Вы были забанены на сервере!\nПричина: {reason}")
        self.ui.app.network.disconnect()
        self.ui.app.root.quit()
    
    def _handle_maintenance(self, msg: Dict[str, Any]):
        """Обработка режима обслуживания"""
        enabled = msg.get("enabled", False)
        message = msg.get("message", "")
        
        if enabled:
            self.ui.add_system_message(f"🔧 Сервер на обслуживании: {message}")
            # Возможно, нужно отключиться
            if "отключиться" in message.lower():
                self.ui.app.network.disconnect()
        else:
            self.ui.add_system_message("✅ Сервер снова доступен")
    
    # ========== СТАТУС ПЕЧАТИ ==========
    
    def _handle_typing(self, msg: Dict[str, Any]):
        """Обработка статуса печати"""
        nick = msg.get("nick", "")
        if hasattr(self.ui, 'user_typing'):
            self.ui.user_typing(nick)
    
    # ========== ПОДКЛЮЧЕНИЕ ==========
    
    def _handle_connected(self, msg: Dict[str, Any]):
        """Обработка успешного подключения"""
        message = msg.get("message", "")
        users_online = msg.get("users_online", 0)
        
        self.ui.add_system_message(f"✅ {message}")
        self.ui.top_bar.set_status(f"онлайн ({users_online})")
    
    def _handle_ping(self, msg: Dict[str, Any]):
        """Обработка ping от сервера"""
        # Отправляем pong через WebSocket или сокет
        pass
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    def _show_notification(self, text: str, msg_type: str = "info"):
        """Показывает уведомление с задержкой"""
        current_time = time.time()
        if current_time - self._last_notification_time > self._notification_cooldown:
            self._last_notification_time = current_time
            self.ui.add_system_message(f"💬 {text}")
    
    def _notify_new_message(self, sender: str, chat_type: str):
        """Уведомление о новом сообщении"""
        if hasattr(self.ui.app, 'notifications'):
            self.ui.app.notifications.notify_new_message(sender, chat_type)