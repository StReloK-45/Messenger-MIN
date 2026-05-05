# client/ui/main_window/chat_handlers.py
import datetime
from tkinter import messagebox

class ChatHandlers:
    def __init__(self, ui):
        self.ui = ui
    
    def handle_server_message(self, msg):
        msg_type = msg.get("type")
        
        # ОБЩИЙ ЧАТ - ИСТОРИЯ
        if msg_type == "history":
            messages = msg.get("messages", [])
            files = msg.get("files", [])
            
            print(f"[DEBUG] Получена история: {len(messages)} сообщений")
            
            self.ui.message_history = messages
            self.ui.files_list = files
            self.ui.right_panel.files_list = files
            
            for widget in self.ui.ui_components.messages_frame.winfo_children():
                widget.destroy()
            
            for i, m in enumerate(messages):
                try:
                    sender = m.get('sender', '')
                    text = m.get('text', '')
                    msg_time = m.get('time', '')
                    is_my = (sender == self.ui.app.settings.nickname)
                    self.ui.display_bubble_message(sender, text, msg_time, is_my)
                except Exception as e:
                    print(f"[DEBUG] Ошибка при отображении сообщения {i}: {e}")
            
            self.ui.right_panel.update_files_list()
            self.ui.scroll_manager.force_scroll_to_bottom()
            self.ui.left_panel.update_chats_list()
        
        # ОБЩИЙ ЧАТ - НОВОЕ СООБЩЕНИЕ
        elif msg_type == "message":
            data = msg.get("data", {})
            sender = data.get('sender', '')
            text = data.get('text', '')
            msg_time = data.get('time', '')
            is_my = (sender == self.ui.app.settings.nickname)
            
            self.ui.message_history.append(data)
            
            if self.ui.current_chat_type == "general":
                self.ui.display_bubble_message(sender, text, msg_time, is_my)
        
        # ЛИЧНОЕ СООБЩЕНИЕ - ПОЛУЧЕНО
        elif msg_type == "private_message":
            sender = msg.get("from", "")
            text = msg.get("text", "")
            time_str = datetime.datetime.now().strftime("%H:%M:%S")
            
            if sender not in self.ui.private_chats_list:
                self.ui.private_chats_list.add(sender)
                self.ui.left_panel.update_chats_list()
            
            if sender not in self.ui.private_messages:
                self.ui.private_messages[sender] = []
            self.ui.private_messages[sender].append({
                'sender': sender, 'text': text, 'time': time_str
            })
            
            if self.ui.current_chat == sender and self.ui.current_chat_type == "private":
                self.ui.display_bubble_message(sender, text, time_str, is_my=False)
            else:
                self.ui.add_system_message(f"💬 Новое сообщение от {sender}")
                self.ui.app.notifications.notify_new_message(sender, "private")
        
        # ЛИЧНОЕ СООБЩЕНИЕ - ОТПРАВЛЕНО
        elif msg_type == "private_sent":
            target = msg.get("to", "")
            text = msg.get("text", "")
            time_str = datetime.datetime.now().strftime("%H:%M:%S")
            
            if target not in self.ui.private_chats_list:
                self.ui.private_chats_list.add(target)
                self.ui.left_panel.update_chats_list()
            
            if target not in self.ui.private_messages:
                self.ui.private_messages[target] = []
            self.ui.private_messages[target].append({
                'sender': self.ui.app.settings.nickname, 'text': text, 'time': time_str
            })
            
            if self.ui.current_chat == target and self.ui.current_chat_type == "private":
                self.ui.display_bubble_message(self.ui.app.settings.nickname, text, time_str, is_my=True)
        
        # ЛИЧНЫЙ ЧАТ - ИСТОРИЯ
        elif msg_type == "private_history":
            target = msg.get("target", "")
            messages = msg.get("messages", [])
            
            print(f"[DEBUG] Получена история ЛС с {target}: {len(messages)} сообщений")
            
            if target not in self.ui.private_chats_list:
                self.ui.private_chats_list.add(target)
                self.ui.left_panel.update_chats_list()
            
            self.ui.private_messages[target] = messages
            
            if self.ui.current_chat == target and self.ui.current_chat_type == "private":
                for widget in self.ui.ui_components.messages_frame.winfo_children():
                    widget.destroy()
                
                for m in messages:
                    sender = m.get('sender', '')
                    text = m.get('text', '')
                    msg_time = m.get('time', '')
                    is_my = (sender == self.ui.app.settings.nickname)
                    self.ui.display_bubble_message(sender, text, msg_time, is_my)
                
                self.ui.scroll_manager.force_scroll_to_bottom()
        
        # ПОЛУЧЕНИЕ СПИСКА ДРУЗЕЙ
        elif msg_type == "friends_list":
            friends = msg.get("friends", [])
            print(f"[DEBUG] Получен список друзей: {friends}")
            self.ui.friends_list = set(friends)
            self.ui.save_friends()
            if friends:
                self.ui.add_system_message(f"👥 В вашем списке {len(friends)} друзей")
        
        # ЗАПРОС В ДРУЗЬЯ
        elif msg_type == "friend_request":
            from_user = msg.get("from", "")
            result = messagebox.askyesno("Запрос в друзья", f"Пользователь {from_user} хочет добавить вас в друзья. Согласны?")
            if result:
                self.ui.app.network.send_raw(f"CMD:ACCEPT_FRIEND|{from_user}")
            else:
                self.ui.app.network.send_raw(f"CMD:DECLINE_FRIEND|{from_user}")
        
        # ПОЛУЧЕНИЕ СПИСКА ГРУПП
        elif msg_type == "user_groups":
            groups = msg.get("groups", [])
            for group_name in groups:
                if group_name not in self.ui.group_chats:
                    self.ui.group_chats[group_name] = {"members": set(), "messages": [], "files": []}
            self.ui.left_panel.update_chats_list()
        
        # ИСТОРИЯ ГРУППЫ
        elif msg_type == "group_history":
            group_name = msg.get("group", "")
            messages = msg.get("messages", [])
            files = msg.get("files", [])
            
            if group_name not in self.ui.group_chats:
                self.ui.group_chats[group_name] = {"members": set(), "messages": [], "files": []}
            
            self.ui.group_chats[group_name]["messages"] = messages
            self.ui.group_chats[group_name]["files"] = files
            
            if self.ui.current_chat == group_name and self.ui.current_chat_type == "group":
                for widget in self.ui.ui_components.messages_frame.winfo_children():
                    widget.destroy()
                for m in messages:
                    sender = m.get('sender', '')
                    text = m.get('text', '')
                    msg_time = m.get('time', '')
                    is_my = (sender == self.ui.app.settings.nickname)
                    self.ui.display_bubble_message(sender, text, msg_time, is_my)
                self.ui.scroll_manager.force_scroll_to_bottom()
        
        # СПИСОК УЧАСТНИКОВ ГРУППЫ
        elif msg_type == "group_members":
            group_name = msg.get("group", "")
            members = msg.get("members", [])
            if group_name in self.ui.group_chats:
                old_count = len(self.ui.group_chats[group_name].get("members", set()))
                self.ui.group_chats[group_name]["members"] = set(members)
                new_count = len(members)
                if new_count > old_count:
                    self.ui.add_system_message(f"👥 В группу '{group_name}' добавлен новый участник")
                print(f"[DEBUG] Обновлён список участников группы {group_name}: {members}")
        
        # НОВОЕ СООБЩЕНИЕ В ГРУППЕ
        elif msg_type == "group_message":
            group_name = msg.get("group", "")
            data = msg.get("data", {})
        
        # УВЕДОМЛЕНИЕ
        elif msg_type == "notification":
            self.ui.add_system_message(msg.get("text", ""))
        
        # ОНЛАЙН ПОЛЬЗОВАТЕЛИ
        elif msg_type == "online_users":
            users = msg.get("users", [])
            users_count = len(users)
            self.ui.top_bar.set_status(f"🟢 онлайн ({users_count})")
        
        # ОБНОВЛЕНИЕ ЦВЕТА НИКА
        elif msg_type == "color_update":
            nick = msg.get("nick", "")
            color = msg.get("color", "")
            if nick and color:
                self.ui.color_manager.nick_colors[nick] = color
        
        # СМЕНА НИКА
        elif msg_type == "nickname_changed":
            old = msg.get("old", "")
            new = msg.get("new", "")
            self.ui.add_system_message(f"✏️ {old} сменил ник на {new}")
        
        # ФАЙЛ В ОБЩЕМ ЧАТЕ
        elif msg_type == "file":
            file_data = msg.get("data", {})
            self.ui.files_list.append(file_data)
            self.ui.right_panel.update_files_list()
            self.ui.add_system_message(f"📁 {file_data.get('sender', '')} отправил файл: {file_data.get('name', '')}")
        
        # ФАЙЛ В ЛИЧНОМ ЧАТЕ
        elif msg_type == "private_file":
            file_data = msg.get("data", {})
            target = msg.get("target", "")
            if target not in self.ui.private_files:
                self.ui.private_files[target] = []
            self.ui.private_files[target].append(file_data)
            if self.ui.current_chat == target and self.ui.current_chat_type == "private":
                self.ui.right_panel.update_files_list()
        
        elif msg_type == "message_deleted":
            msg_id = msg.get("id", "")
            self.ui.add_system_message(f"🗑️ Сообщение {msg_id} удалено")
        
        elif msg_type == "file_deleted":
            file_id = msg.get("id", "")
            self.ui.add_system_message(f"🗑️ Файл {file_id} удалён")
        
        elif msg_type == "message_edited":
            msg_id = msg.get("id", "")
            new_text = msg.get("text", "")
            self.ui.add_system_message(f"✏️ Сообщение {msg_id} отредактировано")
        
        elif msg_type == "typing":
            nick = msg.get("nick", "")
            self.ui.typing_users[nick] = datetime.datetime.now()