# client/ui/main_window/base/data_manager.py
import json
import os

class DataManager:
    def __init__(self, app):
        self.app = app
        
        # Данные чатов
        self.message_history = []
        self.private_messages = {}
        self.private_files = {}
        self.group_chats = {}
        self.files_list = []
        self.current_chat = "general"
        self.current_chat_type = "general"
        self.private_chats_list = set()
        self.friends_list = set()
        
        # Временные данные
        self._images = []
        self._avatar_cache = {}
        self._last_msg_text = None
        self._last_msg_time = 0
        self.file_port = 5556
        
        # Переменные для прокрутки
        self.auto_scroll = True
        self.user_scrolled_up = False
    
    def update_chats_list(self):
        return sorted(self.private_chats_list)
    
    def update_files_list(self, files):
        self.files_list = files
    
    def save_friends(self):
        friends_file = os.path.join(self.app.settings.app_dir, "friends.json")
        try:
            with open(friends_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.friends_list), f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def load_friends(self):
        friends_file = os.path.join(self.app.settings.app_dir, "friends.json")
        try:
            if os.path.exists(friends_file):
                with open(friends_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.friends_list = set(data)
        except:
            pass