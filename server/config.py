# server/config.py
import os
import sys
import socket

class ChatConfig:
    VERSION = "1.2.0"
    
    def __init__(self):
        self.HOST = '0.0.0.0'
        self.PORT = 5555
        self.FILE_PORT = 5556
        
        if getattr(sys, 'frozen', False):
            self.BASE_DIR = os.path.dirname(sys.executable)
        else:
            self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        
        self.DATA_DIR = os.path.join(self.BASE_DIR, "data")
        
        self.USERS_FILE = os.path.join(self.DATA_DIR, "users.json")
        self.CHAT_HISTORY_FILE = os.path.join(self.DATA_DIR, "chat_history.json")
        self.PRIVATE_MESSAGES_FILE = os.path.join(self.DATA_DIR, "private_messages.json")
        self.BANNED_IPS_FILE = os.path.join(self.DATA_DIR, "banned_ips.json")
        self.RECEIVED_FILES_DIR = os.path.join(self.DATA_DIR, "received_files")
    
    def ensure_dirs(self):
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.RECEIVED_FILES_DIR, exist_ok=True)
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"