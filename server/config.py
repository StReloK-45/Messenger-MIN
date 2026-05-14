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
        
        # Только SQLite база данных (никаких JSON)
        self.DATABASE_PATH = os.path.join(self.DATA_DIR, "database.db")
        
        # Папка для полученных файлов
        self.RECEIVED_FILES_DIR = os.path.join(self.DATA_DIR, "received_files")
        
        # Настройки сервера
        self.MAX_CONNECTIONS = 100
        self.BUFFER_SIZE = 4096
        self.TIMEOUT = 60
    
    def ensure_dirs(self):
        """Создаёт только папки (без JSON файлов)"""
        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.RECEIVED_FILES_DIR, exist_ok=True)
        print(f"Папка данных: {self.DATA_DIR}")
        print(f"Папка для файлов: {self.RECEIVED_FILES_DIR}")
    
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"