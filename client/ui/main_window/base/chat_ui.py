# client/ui/main_window/base/chat_ui.py
import tkinter as tk
from tkinter import colorchooser, simpledialog, messagebox, filedialog
import base64
import threading
import socket
import struct
import json
import os
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Set

from ..scroll_manager import ScrollManager
from ..chat_handlers import ChatHandlers
from ..left_panel import LeftPanel
from ..right_panel import RightPanel
from ..top_bar import TopBar
from ..theme_manager import ThemeManager
from ..friends_manager import FriendsManager
from ..chat_input import ChatInput
from .color_manager import ColorManager
from .data_manager import DataManager
from .ui_components import UIComponents
from .message_handlers import MessageHandlers
from .event_handlers import EventHandlers


class ChatUI:
    """Главный UI класс чата"""
    
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
        self.chat_input = ChatInput(self)
        
        # Состояние UI
        self._chat_canvas = None
        self._messages_frame = None
        self._canvas_window = None
        self.menu_window = None
        self.current_chat = "general"
        self.current_chat_type = "general"
        self.typing_users: Dict[str, float] = {}
        self._typing_timer = None
        
        # Кэш для ускорения
        self._nickname_cache: Dict[str, str] = {}
        
        # Флаги
        self._initialized = False
    
    def setup_ui(self):
        """Создаёт весь интерфейс через UIComponents"""
        self.ui_components.setup_ui(self.app.root)
        self.data_manager.load_friends()
        self.left_panel.update_chats_list()
        self._setup_typing_timer()
        self._initialized = True
        
        # Применяем сохранённые настройки
        self.apply_settings()
    
    def apply_settings(self):
        """Применяет сохранённые настройки"""
        # Применяем размер шрифта
        if self.ui_components.message_entry:
            self.ui_components.message_entry.configure(
                font=("Segoe UI", self.app.settings.font_size)
            )
        
        # Применяем тему
        self.refresh_theme()
    
    def refresh_theme(self):
        """Обновляет тему интерфейса"""
        bg = self.color_manager.get_color('bg')
        sidebar = self.color_manager.get_color('sidebar')
        chat_bg = self.color_manager.get_color('chat_bg')
        text = self.color_manager.get_color('text')
        accent = self.color_manager.get_color('accent')
        top_bar = self.color_manager.get_color('top_bar')
        
        # Обновляем цвета всех компонентов
        self.app.root.configure(bg=bg)
        
        if self.ui_components.main_frame:
            self.ui_components.main_frame.configure(bg=bg)
        
        if self.ui_components.chat_canvas:
            self.ui_components.chat_canvas.configure(bg=chat_bg)
        
        if self.ui_components.messages_frame:
            self.ui_components.messages_frame.configure(bg=chat_bg)
        
        # Обновляем заголовок
        if self.ui_components.chat_header:
            self.ui_components.chat_header.configure(bg=chat_bg, fg=text)
        
        # Обновляем поле ввода
        if self.ui_components.message_entry:
            self.ui_components.message_entry.configure(
                bg=self.color_manager.get_color('input_bg'),
                fg=text,
                insertbackground=text
            )
    
    def _setup_typing_timer(self):
        """Настройка таймера для очистки статусов печати"""
        def check_typing():
            now = time.time()
            to_remove = []
            for user, last_time in self.typing_users.items():
                if now - last_time > 3:  # 3 секунды без обновления
                    to_remove.append(user)
            
            for user in to_remove:
                del self.typing_users[user]
                self.update_typing_indicator()
            
            if self._typing_timer:
                self.app.root.after(1000, check_typing)
        
        self._typing_timer = self.app.root.after(1000, check_typing)
    
    def update_typing_indicator(self):
        """Обновляет индикатор печати"""
        if self.typing_users:
            names = list(self.typing_users.keys())
            if len(names) == 1:
                text = f"{names[0]} печатает..."
            elif len(names) == 2:
                text = f"{names[0]} и {names[1]} печатают..."
            elif len(names) > 2:
                text = f"{len(names)} человек печатают..."
            else:
                text = ""
            
            self.top_bar.set_status(text)
        else:
            online_count = len(self.left_panel.get_online_users()) if hasattr(self.left_panel, 'get_online_users') else 0
            self.top_bar.set_status(f"онлайн ({online_count})")
    
    def user_typing(self, nickname: str):
        """Обновляет статус печати пользователя"""
        self.typing_users[nickname] = time.time()
        self.update_typing_indicator()
    
    def send_typing_notification(self):
        """Отправляет уведомление о печати"""
        if self.current_chat_type == "private":
            self.app.network.send_raw(f"CMD:TYPING|{self.current_chat}")
        elif self.current_chat_type == "group":
            self.app.network.send_raw(f"CMD:TYPING|{self.current_chat}")
        else:
            self.app.network.send_raw("CMD:TYPING|general")
    
    def open_menu(self):
        """Открывает боковое меню"""
        from ..sidebar_menu import SidebarMenu
        menu = SidebarMenu(self)
        menu.open()
    
    def open_search(self):
        """Открывает окно поиска"""
        if hasattr(self.app, 'search') and self.app.search:
            self.app.search.open_panel()
    
    def change_nick_color(self):
        """Смена цвета ника"""
        color = colorchooser.askcolor(title="Выберите цвет ника")
        if color and color[1]:
            self.app.network.send_raw(f"CMD:COLOR|{color[1]}")
            self.message_handlers.add_system_message("Цвет ника изменён")
    
    def create_group_dialog(self):
        """Диалог создания группы"""
        group_name = simpledialog.askstring(
            "Создать группу",
            "Введите название группы:",
            parent=self.app.root
        )
        if group_name:
            self.create_group(group_name)
    
    def create_group(self, group_name: str):
        """Создание группы"""
        # Валидация
        if not group_name or len(group_name) > 30:
            self.message_handlers.add_system_message("Название группы должно быть от 1 до 30 символов")
            return
        
        if group_name in self.data_manager.group_chats:
            self.message_handlers.add_system_message(f"Группа '{group_name}' уже существует")
            return
        
        # Отправляем запрос на сервер
        self.app.network.send_raw(f"CMD:CREATE_GROUP|{group_name}")
        
        # Локально создаём запись
        self.data_manager.group_chats[group_name] = {
            "members": {self.app.settings.nickname},
            "messages": [],
            "files": []
        }
        
        self.left_panel.update_chats_list()
        self.message_handlers.add_system_message(f"Группа '{group_name}' создана!")
        
        # Предлагаем добавить друзей
        if self.data_manager.friends_list:
            self._offer_add_friends_to_group(group_name)
    
    def _offer_add_friends_to_group(self, group_name: str):
        """Предлагает добавить друзей в группу"""
        if messagebox.askyesno(
            "Добавить участников",
            f"Хотите добавить друзей в группу '{group_name}'?",
            parent=self.app.root
        ):
            self.left_panel.add_members_to_group(group_name)
    
    def add_emoji(self):
        """Открывает окно выбора смайликов"""
        if self.chat_input:
            self.chat_input.add_emoji()
    
    def switch_account(self):
        """Смена аккаунта"""
        # Отключаемся от сервера
        self.app.network.disconnect()
        
        # Очищаем данные
        self.data_manager.message_history = []
        self.data_manager.private_messages = {}
        self.data_manager.private_files = {}
        self.data_manager.private_chats_list = set()
        self.data_manager.group_chats = {}
        self.data_manager.files_list = []
        self.data_manager.current_chat = "general"
        self.data_manager.current_chat_type = "general"
        
        # Очищаем UI
        if self.ui_components.messages_frame:
            for widget in self.ui_components.messages_frame.winfo_children():
                widget.destroy()
        
        # Прячем главное окно
        self.app.root.withdraw()
        
        # Запрашиваем новый IP
        self.app.root.after(100, self._reconnect)
    
    def _reconnect(self):
        """Переподключение после смены аккаунта"""
        if self.app.network.connect():
            self.app.root.deiconify()
        else:
            self.app.root.quit()
    
    def show_user_profile(self, nickname: str):
        """Показывает профиль пользователя"""
        win = tk.Toplevel(self.app.root)
        win.title(f"Профиль {nickname}")
        win.geometry("280x320")
        win.configure(bg=self.color_manager.get_color('sidebar'))
        win.transient(self.app.root)
        win.grab_set()
        
        # Центрируем окно
        win.update_idletasks()
        x = (win.winfo_screenwidth() // 2) - 140
        y = (win.winfo_screenheight() // 2) - 160
        win.geometry(f"+{x}+{y}")
        
        tk.Label(win, text="👤", font=("Segoe UI", 48),
                 bg=self.color_manager.get_color('sidebar')).pack(pady=(20, 5))
        
        nick_color = self.color_manager.get_nick_color(nickname)
        tk.Label(win, text=nickname, font=("Segoe UI", 14, "bold"),
                 fg=nick_color, bg=self.color_manager.get_color('sidebar')).pack()
        
        # Проверяем онлайн статус
        is_online = self._is_user_online(nickname)
        status_text = "🟢 онлайн" if is_online else "⚫ оффлайн"
        status_color = "#6a9955" if is_online else "#888888"
        
        tk.Label(win, text=status_text, font=("Segoe UI", 10),
                 fg=status_color, bg=self.color_manager.get_color('sidebar')).pack(pady=(0, 15))
        
        # Кнопки действий
        btn_frame = tk.Frame(win, bg=self.color_manager.get_color('sidebar'))
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(btn_frame, text="💬 Написать", 
                  command=lambda: [win.destroy(), self.start_private_chat(nickname)],
                  bg=self.color_manager.get_color('accent'), fg='white', 
                  relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=3)
        
        if nickname not in self.data_manager.friends_list and nickname != self.app.settings.nickname:
            tk.Button(btn_frame, text="👥 Добавить в друзья", 
                      command=lambda: [win.destroy(), self.friends_manager.send_friend_request(nickname)],
                      bg='#6a9955', fg='white', relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=3)
        
        if nickname != self.app.settings.nickname:
            tk.Button(btn_frame, text="🚫 Заблокировать", 
                      command=lambda: [win.destroy(), self._block_user(nickname)],
                      bg='#f48771', fg='white', relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=3)
    
    def _is_user_online(self, nickname: str) -> bool:
        """Проверяет, онлайн ли пользователь"""
        for data in self.app.network.client_data.values():
            if data.get('nickname') == nickname:
                return True
        return False
    
    def _block_user(self, nickname: str):
        """Блокирует пользователя"""
        if messagebox.askyesno("Блокировка", f"Заблокировать {nickname}?", parent=self.app.root):
            if hasattr(self.app, 'privacy'):
                self.app.privacy.block_user(nickname)
                self.message_handlers.add_system_message(f"Пользователь {nickname} заблокирован")
    
    def start_private_chat(self, nickname: str):
        """Начинает приватный чат с пользователем"""
        if nickname == self.app.settings.nickname:
            return
        
        if nickname not in self.data_manager.private_chats_list:
            self.data_manager.private_chats_list.add(nickname)
            self.left_panel.update_chats_list()
            self.app.network.send_raw(f"CMD:GET_PM_HISTORY|{nickname}")
        
        self.data_manager.current_chat = nickname
        self.data_manager.current_chat_type = "private"
        
        if self.ui_components.chat_header:
            self.ui_components.chat_header.config(text=f"ЛС с {nickname}")
        
        # Очищаем поле сообщений
        if self.ui_components.messages_frame:
            for widget in self.ui_components.messages_frame.winfo_children():
                widget.destroy()
        
        # Загружаем историю
        if nickname in self.data_manager.private_messages:
            for msg in self.data_manager.private_messages[nickname]:
                sender = msg.get('sender', '')
                text = msg.get('text', '')
                msg_time = msg.get('time', '')
                is_my = (sender == self.app.settings.nickname)
                self.message_handlers.display_bubble_message(sender, text, msg_time, is_my)
        
        # Обновляем список файлов
        if hasattr(self.right_panel, 'load_files'):
            self.right_panel.load_files()
        
        self.scroll_manager.force_scroll_to_bottom()
    
    # ========== Перенаправление методов ==========
    
    def get_color(self, key: str) -> str:
        return self.color_manager.get_color(key)
    
    def get_nick_color(self, nick: str) -> str:
        return self.color_manager.get_nick_color(nick)
    
    def display_bubble_message(self, sender: str, text: str, msg_time: str, is_my: bool = False):
        self.message_handlers.display_bubble_message(sender, text, msg_time, is_my)
    
    def add_system_message(self, text: str):
        self.message_handlers.add_system_message(text)
    
    def send_message(self, event=None):
        self.message_handlers.send_message(event)
    
    def on_chat_select(self, event):
        self.event_handlers.on_chat_select(event)
    
    def show_context_menu(self, event, sender: str):
        self.event_handlers.show_context_menu(event, sender)
    
    def handle_server_message(self, msg: Dict[str, Any]):
        self.chat_handlers.handle_server_message(msg)
    
    def add_friend(self, nickname: str):
        self.friends_manager.send_friend_request(nickname)
    
    def save_friends(self):
        self.data_manager.save_friends()
    
    def load_files(self):
        if hasattr(self.right_panel, 'load_files'):
            self.right_panel.load_files()
    
    def download_file(self, event=None):
        if hasattr(self.right_panel, 'download_file'):
            self.right_panel.download_file(event)
    
    def send_file(self):
        if hasattr(self.right_panel, 'send_file'):
            self.right_panel.send_file()
    
    def update_files_list(self):
        if hasattr(self.right_panel, 'update_files_list'):
            self.right_panel.update_files_list()
    
    def update_chats_list(self):
        self.left_panel.update_chats_list()
    
    # ========== Свойства для обратной совместимости ==========
    
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
    def message_history(self) -> List[Dict]:
        return self.data_manager.message_history
    
    @message_history.setter
    def message_history(self, value):
        self.data_manager.message_history = value
    
    @property
    def private_messages(self) -> Dict[str, List[Dict]]:
        return self.data_manager.private_messages
    
    @private_messages.setter
    def private_messages(self, value):
        self.data_manager.private_messages = value
    
    @property
    def private_files(self) -> Dict[str, List[Dict]]:
        return self.data_manager.private_files
    
    @private_files.setter
    def private_files(self, value):
        self.data_manager.private_files = value
    
    @property
    def private_chats_list(self) -> Set[str]:
        return self.data_manager.private_chats_list
    
    @private_chats_list.setter
    def private_chats_list(self, value):
        self.data_manager.private_chats_list = value
    
    @property
    def files_list(self) -> List[Dict]:
        return self.data_manager.files_list
    
    @files_list.setter
    def files_list(self, value):
        self.data_manager.files_list = value
    
    @property
    def friends_list(self) -> Set[str]:
        return self.data_manager.friends_list
    
    @friends_list.setter
    def friends_list(self, value):
        self.data_manager.friends_list = value
    
    @property
    def group_chats(self) -> Dict[str, Dict]:
        return self.data_manager.group_chats
    
    @property
    def file_port(self) -> int:
        return self.data_manager.file_port
    
    @property
    def auto_scroll(self) -> bool:
        return self.data_manager.auto_scroll
    
    @auto_scroll.setter
    def auto_scroll(self, value: bool):
        self.data_manager.auto_scroll = value