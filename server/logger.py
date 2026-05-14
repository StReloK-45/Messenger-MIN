# server/logger.py
import os
import json
from datetime import datetime
from threading import Lock

class Logger:
    """Ебаный логгер для сервера - пишет в файл и в консоль"""
    
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        self.lock = Lock()
        self.console_enabled = True
        self.file_enabled = True
        
        os.makedirs(log_dir, exist_ok=True)
        
        # Создаём файлы логов
        self.chat_log = os.path.join(log_dir, "chat.log")
        self.error_log = os.path.join(log_dir, "error.log")
        self.access_log = os.path.join(log_dir, "access.log")
        self.debug_log = os.path.join(log_dir, "debug.log")
        
        # Инициализируем файлы
        for f in [self.chat_log, self.error_log, self.access_log, self.debug_log]:
            if not os.path.exists(f):
                with open(f, 'w', encoding='utf-8') as fp:
                    fp.write(f"# Лог начат: {datetime.now()}\n")
    
    def _write(self, filepath, message):
        """Пишет в файл"""
        if not self.file_enabled:
            return
        try:
            with self.lock:
                with open(filepath, 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {message}\n")
        except:
            pass
    
    def _print(self, level, message):
        """Печатает в консоль с цветом"""
        if not self.console_enabled:
            return
        
        colors = {
            'ERROR': '\033[91m',
            'WARNING': '\033[93m',
            'SUCCESS': '\033[92m',
            'INFO': '\033[94m',
            'ADMIN': '\033[95m',
            'SYSTEM': '\033[96m'
        }
        
        color = colors.get(level, '\033[0m')
        reset = '\033[0m'
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{color}[{timestamp}] {level}: {message}{reset}")
    
    def error(self, message):
        self._write(self.error_log, f"ERROR | {message}")
        self._print("ERROR", message)
    
    def warning(self, message):
        self._write(self.error_log, f"WARNING | {message}")
        self._print("WARNING", message)
    
    def info(self, message):
        self._write(self.access_log, f"INFO | {message}")
        self._print("INFO", message)
    
    def success(self, message):
        self._write(self.chat_log, f"SUCCESS | {message}")
        self._print("SUCCESS", message)
    
    def debug(self, message):
        self._write(self.debug_log, f"DEBUG | {message}")
        # debug не печатаем в консоль, только в файл
    
    def admin(self, message):
        self._write(self.access_log, f"ADMIN | {message}")
        self._print("ADMIN", message)
    
    def system(self, message):
        self._write(self.chat_log, f"SYSTEM | {message}")
        self._print("SYSTEM", message)
    
    def chat(self, sender, message):
        self._write(self.chat_log, f"CHAT | {sender}: {message}")
    
    def connection(self, ip, status):
        self._write(self.access_log, f"CONNECTION | {ip} | {status}")
    
    def save_event(self, event_type, data):
        """Сохраняет событие в JSON"""
        try:
            json_file = os.path.join(self.log_dir, "events.json")
            event = {
                "timestamp": datetime.now().isoformat(),
                "type": event_type,
                "data": data
            }
            
            with self.lock:
                events = []
                if os.path.exists(json_file):
                    with open(json_file, 'r', encoding='utf-8') as f:
                        try:
                            events = json.load(f)
                        except:
                            events = []
                
                events.append(event)
                
                # Ограничиваем размер
                if len(events) > 10000:
                    events = events[-10000:]
                
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(events, f, indent=2, ensure_ascii=False)
        except:
            pass

# Глобальный экземпляр
logger = Logger()