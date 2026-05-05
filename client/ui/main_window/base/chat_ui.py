# client/ui/main_window/base/chat_ui.py
import tkinter as tk
from tkinter import colorchooser, simpledialog, messagebox, filedialog
import base64
import threading
import socket
import struct
import json
import os

from ..scroll_manager import ScrollManager
from ..chat_handlers import ChatHandlers
from ..left_panel import LeftPanel
from ..right_panel import RightPanel
from ..top_bar import TopBar
from ..theme_manager import ThemeManager
from ..friends_manager import FriendsManager
from .color_manager import ColorManager
from .data_manager import DataManager
from .ui_components import UIComponents
from .message_handlers import MessageHandlers
from .event_handlers import EventHandlers

class ChatUI:
    def __init__(self, app):
        self.app = app
        
        # Менеджеры
        self.color_manager = ColorManager(app)
        self.data_manager = DataManager(app)
        self.ui_components = UIComponents(self)
        self.message_handlers = MessageHandlers(self)
        self.event_handlers = EventHandlers(self)
        
        # Внешние компоненты
        self.scroll_manager = ScrollManager(self)
        self.chat_handlers = ChatHandlers(self)
        self.left_panel = LeftPanel(self)
        self.right_panel = RightPanel(self)
        self.top_bar = TopBar(self)
        self.theme_manager = ThemeManager(self)
        self.friends_manager = FriendsManager(self)
        
        # Компоненты UI
        self._chat_canvas = None
        self._messages_frame = None
        self._canvas_window = None
        self.menu_window = None
    
    def setup_ui(self):
        """Создаёт весь интерфейс через UIComponents"""
        self.ui_components.setup_ui(self.app.root)
        self.data_manager.load_friends()
        self.left_panel.update_chats_list()
    
    def open_menu(self):
        from ..sidebar_menu import SidebarMenu
        menu = SidebarMenu(self)
        menu.open()
    
    def open_search(self):
        if hasattr(self.app, 'search') and self.app.search:
            self.app.search.open_panel()
    
    def change_nick_color(self):
        color = colorchooser.askcolor(title="Выберите цвет ника")
        if color and color[1]:
            self.app.network.send_raw(f"CMD:COLOR|{color[1]}")
            self.message_handlers.add_system_message(f"🎨 Цвет ника изменён")
    
    def create_group_dialog(self):
        group_name = simpledialog.askstring("Создать группу", "Введите название группы:")
        if group_name:
            self.create_group(group_name)
    
    def create_group(self, group_name):
        if group_name in self.data_manager.group_chats:
            self.message_handlers.add_system_message("❌ Группа с таким названием уже существует!")
            return
        if len(group_name) > 30:
            self.message_handlers.add_system_message("❌ Название группы не должно превышать 30 символов!")
            return
        
        self.data_manager.group_chats[group_name] = {"members": {self.app.settings.nickname}, "messages": [], "files": []}
        self.message_handlers.add_system_message(f"✅ Группа '{group_name}' создана!")
        self.left_panel.update_chats_list()
    
    def add_emoji(self):
        if self.ui_components.message_entry:
            self.ui_components.message_entry.insert(tk.END, "😊")
    
    def add_log(self, text):
        print(f"[LOG] {text}")
    
    def switch_account(self):
        """Смена аккаунта - возврат к экрану ввода IP"""
        if self.app.network.sock:
            try:
                self.app.network.sock.close()
            except:
                pass
        self.app.network.sock = None
        self.app.network.authenticated = False
        
        self.data_manager.message_history = []
        self.data_manager.private_messages = {}
        self.data_manager.private_files = {}
        self.data_manager.private_chats_list = set()
        self.data_manager.group_chats = {}
        self.data_manager.files_list = []
        
        for widget in self.ui_components.messages_frame.winfo_children():
            widget.destroy()
        
        self.app.root.withdraw()
        self.app.root.after(100, self.app.network.ask_server_ip)
    
    def show_user_profile(self, nick):
        """Показывает профиль пользователя"""
        win = tk.Toplevel(self.app.root)
        win.title(f"Профиль {nick}")
        win.geometry("250x300")
        win.configure(bg=self.color_manager.get_color('sidebar'))
        win.transient(self.app.root)
        
        tk.Label(win, text="👤", font=("Segoe UI", 50),
                 bg=self.color_manager.get_color('sidebar')).pack(pady=(20, 5))
        
        nick_color = self.get_nick_color(nick)
        tk.Label(win, text=nick, font=("Segoe UI", 14, "bold"),
                 fg=nick_color, bg=self.color_manager.get_color('sidebar')).pack()
        tk.Label(win, text=f"@{nick}", font=("Segoe UI", 10),
                 fg='#888', bg=self.color_manager.get_color('sidebar')).pack(pady=(0, 15))
        
        def start_chat():
            win.destroy()
            self.start_private_chat(nick)
        
        tk.Button(win, text="💬 Написать", command=start_chat,
                  bg=self.color_manager.get_color('accent'), fg='white', relief=tk.FLAT,
                  cursor="hand2").pack(fill=tk.X, padx=20, pady=5)
        
        if nick not in self.friends_list and nick != self.app.settings.nickname:
            tk.Button(win, text="👥 Добавить в друзья", 
                      command=lambda: [win.destroy(), self.friends_manager.send_friend_request(nick)],
                      bg='#6a9955', fg='white', relief=tk.FLAT,
                      cursor="hand2").pack(fill=tk.X, padx=20, pady=5)
    
    # Перенаправление методов
    def get_color(self, key):
        return self.color_manager.get_color(key)
    
    def get_nick_color(self, nick):
        return self.color_manager.get_nick_color(nick)
    
    def display_bubble_message(self, sender, text, msg_time, is_my=False):
        self.message_handlers.display_bubble_message(sender, text, msg_time, is_my)
    
    def add_system_message(self, text):
        self.message_handlers.add_system_message(text)
    
    def send_message(self, event=None):
        self.message_handlers.send_message(event)
    
    def on_chat_select(self, event):
        self.event_handlers.on_chat_select(event)
    
    def start_private_chat(self, nick):
        self.event_handlers.start_private_chat(nick)
    
    def show_context_menu(self, event, sender):
        self.event_handlers.show_context_menu(event, sender)
    
    def handle_server_message(self, msg):
        self.chat_handlers.handle_server_message(msg)
    
    def add_friend(self, nick):
        self.friends_manager.send_friend_request(nick)
    
    def save_friends(self):
        self.app.settings.save_friends()
    
    def load_friends(self):
        self.app.settings.load_friends()
    
    def load_files(self):
        self.right_panel.load_files()
    
    def download_file(self, event=None):
        self.right_panel.download_file(event)
    
    def send_file(self):
        self.right_panel.send_file()
    
    def update_files_list(self):
        self.right_panel.update_files_list()
    
    def update_chats_list(self):
        self.left_panel.update_chats_list()
    
    # Свойства
    @property
    def chat_canvas(self):
        return self._chat_canvas
    
    @chat_canvas.setter
    def chat_canvas(self, value):
        self._chat_canvas = value
    
    @property
    def messages_frame(self):
        return self._messages_frame
    
    @messages_frame.setter
    def messages_frame(self, value):
        self._messages_frame = value
    
    @property
    def canvas_window(self):
        return self._canvas_window
    
    @canvas_window.setter
    def canvas_window(self, value):
        self._canvas_window = value
    
    @property
    def message_history(self):
        return self.data_manager.message_history
    
    @message_history.setter
    def message_history(self, value):
        self.data_manager.message_history = value
    
    @property
    def private_messages(self):
        return self.data_manager.private_messages
    
    @private_messages.setter
    def private_messages(self, value):
        self.data_manager.private_messages = value
    
    @property
    def private_files(self):
        return self.data_manager.private_files
    
    @private_files.setter
    def private_files(self, value):
        self.data_manager.private_files = value
    
    @property
    def private_chats_list(self):
        return self.data_manager.private_chats_list
    
    @private_chats_list.setter
    def private_chats_list(self, value):
        self.data_manager.private_chats_list = value
    
    @property
    def files_list(self):
        return self.data_manager.files_list
    
    @files_list.setter
    def files_list(self, value):
        self.data_manager.files_list = value
    
    @property
    def current_chat(self):
        return self.data_manager.current_chat
    
    @current_chat.setter
    def current_chat(self, value):
        self.data_manager.current_chat = value
    
    @property
    def current_chat_type(self):
        return self.data_manager.current_chat_type
    
    @current_chat_type.setter
    def current_chat_type(self, value):
        self.data_manager.current_chat_type = value
    
    @property
    def friends_list(self):
        return self.app.settings.friends_list
    
    @friends_list.setter
    def friends_list(self, value):
        self.app.settings.friends_list = value
    
    @property
    def group_chats(self):
        return self.data_manager.group_chats
    
    @property
    def file_port(self):
        return self.data_manager.file_port
    
    @property
    def _last_msg_text(self):
        return self.data_manager._last_msg_text
    
    @_last_msg_text.setter
    def _last_msg_text(self, value):
        self.data_manager._last_msg_text = value
    
    @property
    def _last_msg_time(self):
        return self.data_manager._last_msg_time
    
    @_last_msg_time.setter
    def _last_msg_time(self, value):
        self.data_manager._last_msg_time = value
    
    @property
    def auto_scroll(self):
        return self.data_manager.auto_scroll
    
    @auto_scroll.setter
    def auto_scroll(self, value):
        self.data_manager.auto_scroll = value