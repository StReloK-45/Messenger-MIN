# client/settings.py
import json
import os
import sys

class AppSettings:
    def __init__(self):
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.settings_file = os.path.join(self.app_dir, "settings.json")
        self.config_file = os.path.join(self.app_dir, "chat_config.ini")
        
        self.server_ip = "26.66.193.221"
        self.chat_port = 5555
        self.file_port = 5556
        self.running = True
        
        self.nickname = None
        self.username = None
        self.saved_username = ""
        self.saved_password = ""
        self.save_auth = False
        
        self.font_size = 10
        self.theme = "dark"
        self.accent_color = "#0e639c"
        self.message_style = "rounded"
        
        self.custom_colors = {
            'bg': '#1e1e1e',
            'sidebar': '#252525',
            'chat_bg': '#2d2d2d',
            'input_bg': '#3c3c3c',
            'text': '#d4d4d4',
            'accent': '#0e639c',
            'time': '#6a9955',
            'system': '#c586c0',
            'top_bar': '#252525',
            'my_bubble': '#1a3a5c',
            'other_bubble': '#383838',
            'my_text': '#ffffff',
            'other_text': '#d4d4d4'
        }
        
        self.status = "online"
        self.auto_away_minutes = 5
        
        self.privacy_ls = "all"
        self.blocked_users = []
        self.friends_list = set()
        
        self.load()
        self.load_config()
        self.load_friends()

    def load(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(self, key):
                            if key == 'custom_colors' and isinstance(value, dict):
                                for k, v in value.items():
                                    if k in self.custom_colors:
                                        self.custom_colors[k] = v
                            else:
                                setattr(self, key, value)
            except Exception as e:
                print(f"Ошибка загрузки настроек: {e}")
    
    def save(self):
        data = {
            "font_size": self.font_size,
            "theme": self.theme,
            "accent_color": self.accent_color,
            "message_style": self.message_style,
            "status": self.status,
            "auto_away_minutes": self.auto_away_minutes,
            "privacy_ls": self.privacy_ls,
            "blocked_users": self.blocked_users,
            "custom_colors": self.custom_colors
        }
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")
    
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.saved_username = data.get('saved_username', '')
                    self.saved_password = data.get('password', '')
                    self.save_auth = data.get('save_auth', False)
                    if not self.saved_username and data.get('username'):
                        self.saved_username = data.get('username', '')
            except Exception as e:
                print(f"Ошибка загрузки конфига: {e}")
                self.saved_username = ""
                self.saved_password = ""
                self.save_auth = False
    
    def save_config(self):
        if self.save_auth:
            data = {
                'saved_username': self.saved_username,
                'password': self.saved_password,
                'save_auth': True
            }
        else:
            data = {
                'saved_username': '',
                'password': '',
                'save_auth': False
            }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения конфига: {e}")
    
    def get_color(self, key):
        dark_theme = {
            'bg': '#1e1e1e',
            'sidebar': '#252525',
            'chat_bg': '#2d2d2d',
            'input_bg': '#3c3c3c',
            'text': '#d4d4d4',
            'accent': self.accent_color,
            'time': '#6a9955',
            'system': '#c586c0',
            'top_bar': '#252525',
            'my_bubble': '#1a3a5c',
            'other_bubble': '#383838',
            'my_text': '#ffffff',
            'other_text': '#d4d4d4'
        }
        
        light_theme = {
            'bg': '#f5f5f5',
            'sidebar': '#e8e8e8',
            'chat_bg': '#ffffff',
            'input_bg': '#f0f0f0',
            'text': '#000000',
            'accent': self.accent_color,
            'time': '#888888',
            'system': '#007a00',
            'top_bar': '#e8e8e8',
            'my_bubble': '#dcf8c6',
            'other_bubble': '#f0f0f0',
            'my_text': '#000000',
            'other_text': '#000000'
        }
        
        if self.theme == "dark":
            colors = dark_theme
        elif self.theme == "light":
            colors = light_theme
        else:
            colors = self.custom_colors
            if 'accent' not in colors:
                colors['accent'] = self.accent_color
        
        return colors.get(key, '#000000')
    
    def reset_custom_colors(self):
        self.custom_colors = {
            'bg': '#1e1e1e',
            'sidebar': '#252525',
            'chat_bg': '#2d2d2d',
            'input_bg': '#3c3c3c',
            'text': '#d4d4d4',
            'accent': '#0e639c',
            'time': '#6a9955',
            'system': '#c586c0',
            'top_bar': '#252525',
            'my_bubble': '#1a3a5c',
            'other_bubble': '#383838',
            'my_text': '#ffffff',
            'other_text': '#d4d4d4'
        }
        self.save()
    
    def update_custom_color(self, key, value):
        if key in self.custom_colors:
            self.custom_colors[key] = value
            self.save()
            return True
        return False
    
    def get_accent_colors(self):
        return {
            "#0e639c": "Синий",
            "#6a9955": "Зелёный",
            "#9c3e9c": "Пурпурный",
            "#d4a017": "Оранжевый",
            "#e74856": "Красный",
            "#c586c0": "Розовый",
            "#4ec9b0": "Бирюзовый"
        }
    
    def load_friends(self):
        friend_file = os.path.join(self.app_dir, "friends.json")
        try:
            if os.path.exists(friend_file):
                with open(friend_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.friends_list = set(data)
        except:
            pass
    
    def save_friends(self):
        friends_file = os.path.join(self.app_dir, "friends.json")
        try:
            with open(friends_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.friends_list), f, ensure_ascii=False, indent=2)
        except:
            pass