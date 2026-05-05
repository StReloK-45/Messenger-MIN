# client/ui/main_window/base/event_handlers.py
import tkinter as tk

class EventHandlers:
    def __init__(self, ui):
        self.ui = ui
    
    def on_chat_select(self, event):
        selection = self.ui.ui_components.chats_listbox.curselection()
        if not selection:
            return
        
        self.ui.data_manager.auto_scroll = True
        self.ui.data_manager.user_scrolled_up = False
        
        if selection[0] == 0:
            self.ui.data_manager.current_chat = "general"
            self.ui.data_manager.current_chat_type = "general"
            self.ui.ui_components.chat_header.config(text="💬 Общий чат")
            for widget in self.ui.ui_components.messages_frame.winfo_children():
                widget.destroy()
            for m in self.ui.data_manager.message_history:
                self.ui.message_handlers.display_bubble_message(
                    m.get('sender'), m.get('text'), m.get('time'),
                    m.get('sender') == self.ui.app.settings.nickname
                )
            self.ui.scroll_manager.force_scroll_to_bottom()
        else:
            chat_text = self.ui.ui_components.chats_listbox.get(selection[0]).strip()
            if chat_text.startswith("👤"):
                nick = chat_text.replace("👤", "").strip()
                self.ui.data_manager.current_chat = nick
                self.ui.data_manager.current_chat_type = "private"
                self.ui.ui_components.chat_header.config(text=f"💬 ЛС с {nick}")
                for widget in self.ui.ui_components.messages_frame.winfo_children():
                    widget.destroy()
                self.ui.app.network.send_raw(f"CMD:GET_PM_HISTORY|{nick}")
            elif chat_text.startswith("👥"):
                group_name = chat_text.replace("👥", "").strip()
                self.ui.data_manager.current_chat = group_name
                self.ui.data_manager.current_chat_type = "group"
                self.ui.ui_components.chat_header.config(text=f"👥 {group_name}")
                for widget in self.ui.ui_components.messages_frame.winfo_children():
                    widget.destroy()
                group = self.ui.data_manager.group_chats.get(group_name, {})
                for m in group.get("messages", []):
                    self.ui.message_handlers.display_bubble_message(
                        m.get('sender'), m.get('text'), m.get('time'),
                        m.get('sender') == self.ui.app.settings.nickname
                    )
                self.ui.scroll_manager.force_scroll_to_bottom()
        
        self.ui.right_panel.load_files()
    
    def start_private_chat(self, nick):
        if nick == self.ui.app.settings.nickname:
            return
        
        if nick not in self.ui.data_manager.private_chats_list:
            self.ui.data_manager.private_chats_list.add(nick)
            self.ui.left_panel.update_chats_list()
            self.ui.app.network.send_raw(f"CMD:GET_PM_HISTORY|{nick}")
        
        self.ui.data_manager.current_chat = nick
        self.ui.data_manager.current_chat_type = "private"
        self.ui.ui_components.chat_header.config(text=f"💬 ЛС с {nick}")
        
        for widget in self.ui.ui_components.messages_frame.winfo_children():
            widget.destroy()
        
        self.ui.right_panel.load_files()
        self.ui.scroll_manager.force_scroll_to_bottom()
    
    def show_context_menu(self, event, sender):
        menu = tk.Menu(self.ui.app.root, tearoff=0, bg='#3c3c3c', fg='white')
        menu.add_command(label="🎨 Скопировать цвет ника", 
                       command=lambda: self.ui.theme_manager.change_nick_color())
        menu.add_separator()
        menu.add_command(label="💬 Написать", 
                       command=lambda: self.start_private_chat(sender))
        menu.add_separator()
        
        # Кнопка добавления в друзья (если ещё не друг)
        if sender not in self.ui.friends_list and sender != self.ui.app.settings.nickname:
            menu.add_command(label="👥 Добавить в друзья", 
                           command=lambda: self.ui.friends_manager.send_friend_request(sender))
        elif sender in self.ui.friends_list:
            menu.add_command(label="👤 Уже в друзьях", state='disabled')
        
        menu.tk_popup(event.x_root, event.y_root)