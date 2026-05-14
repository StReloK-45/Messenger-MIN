# server/main.py
import sys
import os
import json
import threading
import time
from datetime import datetime
import socket

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ChatConfig
from storage import Storage
from api import ApiServer

# Импорты для старого сокет-сервера (для совместимости с Desktop)
from network import NetworkManager
from auth import AuthManager
from chat import ChatManager
from files import FileManager
from admin import AdminManager

class ConsoleMenu:
    """Консольное меню с рамками (автовыравнивание)"""
    
    def __init__(self, server):
        self.server = server
        self.running = True
        self.log_lines = []
        self.log_lock = threading.Lock()
        self.width = 56  # Ширина рамки
    
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _line(self, text="", center=False):
        """Универсальная печать строки внутри рамки"""
        content_width = self.width - 4
        if len(text) > content_width:
            text = text[:content_width - 3] + "..."
        
        if center:
            text = text.center(content_width)
        else:
            text = text.ljust(content_width)
        
        print("| " + text + " |")
    
    def _border(self, title=""):
        """Печать границы"""
        print("+" + "-" * (self.width - 2) + "+")
        if title:
            self._line(title, center=True)
            print("+" + "-" * (self.width - 2) + "+")
    
    def print_menu(self):
        self.clear_screen()
        self._border("MESSENGER SERVER v2.0")
        self._line("")
        self._line("1. Просмотр логов сервера (режим реального времени)")
        self._line("2. Администрирование")
        self._line("3. Информация о сервере")
        self._line("4. Завершение работы сервера")
        self._line("")
        self._border()
        self._line("Выберите опцию (1-4):", center=True)
        self._border()
    
    def add_log(self, message, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        levels = {
            "error": f"[{timestamp}] ERROR: {message}",
            "admin": f"[{timestamp}] ADMIN: {message}",
            "system": f"[{timestamp}] SYSTEM: {message}",
            "server": f"[{timestamp}] SERVER: {message}",
            "online": f"[{timestamp}] ONLINE: {message}",
        }
        formatted = levels.get(level, f"[{timestamp}] INFO: {message}")
        
        with self.log_lock:
            self.log_lines.append(formatted)
            if len(self.log_lines) > 1000:
                self.log_lines = self.log_lines[-1000:]
        print(formatted)
    
    def view_logs(self):
        self.clear_screen()
        width_log = 70
        last_count = len(self.log_lines)
        
        print("+" + "-" * (width_log - 2) + "+")
        print("|" + " ЛОГИ СЕРВЕРА (режим реального времени) ".center(width_log - 2) + "|")
        print("+" + "-" * (width_log - 2) + "+")
        
        with self.log_lock:
            for line in self.log_lines[-20:]:
                print("| " + line.ljust(width_log - 4) + " |")
        
        print("+" + "-" * (width_log - 2) + "+")
        print("| " + "Нажмите Enter для обновления, 'q' для выхода".ljust(width_log - 4) + " |")
        print("+" + "-" * (width_log - 2) + "+")
        
        import sys
        while True:
            if sys.platform == 'win32':
                import msvcrt
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('ascii', errors='ignore').lower()
                    if key == 'q':
                        break
                    elif key == '\r':
                        with self.log_lock:
                            if len(self.log_lines) != last_count:
                                self.view_logs()
                                return
            else:
                import select
                if sys.stdin in select.select([sys.stdin], [], [], 0.5)[0]:
                    key = sys.stdin.read(1).lower()
                    if key == 'q':
                        break
            
            with self.log_lock:
                if len(self.log_lines) != last_count:
                    self.view_logs()
                    return
            time.sleep(0.5)
    
    def admin_login(self):
        self.clear_screen()
        self._border("АДМИН ВХОД")
        self._line("")
        
        username = input("|   Логин: ").strip()
        password = input("|   Пароль: ").strip()
        
        self._line("")
        self._border()
        
        if username == "adminSK" and password == "SK45-US45":
            print("\n[OK] Авторизация успешна!")
            time.sleep(1)
            self.admin_panel()
            return True
        else:
            print("\n[ERROR] Неверный логин или пароль!")
            time.sleep(2)
            return False
    
    def admin_panel(self):
        while True:
            self.clear_screen()
            self._border("ПАНЕЛЬ АДМИНИСТРАТОРА")
            self._line("")
            self._line("1. Просмотр онлайн пользователей")
            self._line("2. Кикнуть пользователя")
            self._line("3. Забанить пользователя")
            self._line("4. Разбанить IP")
            self._line("5. Список забаненных IP")
            self._line("6. Показать историю сообщений")
            self._line("7. Создать нового администратора")
            self._line("8. Отправить сообщение от сервера")
            self._line("9. Статистика сервера")
            self._line("10. Забрать права у администратора")
            self._line("0. Назад в главное меню")
            self._line("")
            self._border()
            
            choice = input("Выберите опцию: ").strip()
            
            actions = {
                "1": self.show_online_users,
                "2": self.kick_user,
                "3": self.ban_user,
                "4": self.unban_ip,
                "5": self.show_banned,
                "6": self.show_history,
                "7": self.create_admin,
                "8": self.send_system_message,
                "9": self.show_stats,
                "10": self.demote_admin,
                "0": lambda: None
            }
            
            if choice in actions:
                if choice == "0":
                    break
                actions[choice]()
            else:
                print("[ERROR] Неверный выбор!")
                time.sleep(1)
    
    def show_online_users(self):
        self.clear_screen()
        self._border("ОНЛАЙН ПОЛЬЗОВАТЕЛИ")
        self._line("")
        
        if not self.server.clients:
            self._line("Нет пользователей онлайн")
        else:
            for client in self.server.clients:
                data = self.server.client_data.get(client, {})
                nickname = data.get('nickname', 'Unknown')
                username = data.get('username', 'Unknown')
                addr = data.get('addr', 'Unknown')
                self._line(f"{nickname} (@{username}) - {addr}")
        
        self._line("")
        self._border()
        input("\nНажмите Enter для продолжения...")
    
    def kick_user(self):
        nickname = input("Введите никнейм пользователя: ").strip()
        
        for client, data in list(self.server.client_data.items()):
            if data.get('nickname') == nickname:
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(
                    {"type": "kicked", "reason": "Кикнут администратором"}, ensure_ascii=False))
                time.sleep(0.1)
                self.server.network.remove_client(client)
                self.add_log(f"Пользователь {nickname} кикнут", "admin")
                print(f"[OK] Пользователь {nickname} кикнут")
                time.sleep(1)
                return
        
        print(f"[ERROR] Пользователь {nickname} не найден в онлайне")
        time.sleep(1)
    
    def ban_user(self):
        nickname = input("Введите никнейм пользователя: ").strip()
        
        for client, data in list(self.server.client_data.items()):
            if data.get('nickname') == nickname:
                ip = data.get('addr')
                self.server.storage.ban_ip(ip, f"Забанен администратором: {nickname}")
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(
                    {"type": "banned", "reason": "Забанен администратором"}, ensure_ascii=False))
                time.sleep(0.1)
                self.server.network.remove_client(client)
                self.add_log(f"Пользователь {nickname} забанен (IP: {ip})", "admin")
                print(f"[OK] Пользователь {nickname} забанен (IP: {ip})")
                time.sleep(1)
                return
        
        print(f"[ERROR] Пользователь {nickname} не найден в онлайне")
        time.sleep(1)
    
    def unban_ip(self):
        ip = input("Введите IP для разбана: ").strip()
        
        if self.server.storage.unban_ip(ip):
            print(f"[OK] IP {ip} разбанен")
            self.add_log(f"IP {ip} разбанен", "admin")
        else:
            print(f"[ERROR] IP {ip} не найден в списке банов")
        time.sleep(1)
    
    def show_banned(self):
        self.clear_screen()
        self._border("ЗАБАНЕННЫЕ IP")
        self._line("")
        
        banned = self.server.storage.get_banned_ips()
        if not banned:
            self._line("Нет забаненных IP")
        else:
            for ip in banned:
                self._line(f"[BANNED] {ip}")
        
        self._line("")
        self._border()
        input("\nНажмите Enter для продолжения...")
    
    def show_history(self):
        self.clear_screen()
        count = input("Сколько последних сообщений показать? (по умолчанию 50): ").strip()
        count = int(count) if count.isdigit() else 50
        
        messages = self.server.storage.get_chat_history(count)
        self._border(f"ПОСЛЕДНИЕ {len(messages)} СООБЩЕНИЙ")
        self._line("")
        
        if not messages:
            self._line("Нет сообщений")
        else:
            for msg in messages:
                sender = msg.get('sender', 'Unknown')
                text = msg.get('message', '')[:50]
                timestamp = msg.get('timestamp', '')
                if len(timestamp) > 16:
                    timestamp = timestamp[11:16]
                self._line(f"[{timestamp}] {sender}: {text}")
        
        self._line("")
        self._border()
        input("\nНажмите Enter для продолжения...")
    
    def create_admin(self):
        self.clear_screen()
        self._border("СОЗДАНИЕ АДМИНИСТРАТОРА")
        self._line("")
        
        username = input("|   Логин: ").strip()
        password = input("|   Пароль: ").strip()
        
        existing = self.server.storage.get_user(username)
        if existing:
            print("\n[ERROR] Пользователь уже существует!")
        else:
            from security import SimpleHash
            salt = SimpleHash.generate_salt()
            password_hash = SimpleHash.hash_password(password, salt)
            user_id = self.server.storage.create_user(username, password_hash, salt, is_admin=True)
            
            if user_id:
                print("\n[OK] Администратор создан!")
                self.add_log(f"Создан новый администратор: {username}", "admin")
            else:
                print("\n[ERROR] Ошибка при создании!")
        time.sleep(2)
    
    def send_system_message(self):
        message = input("Введите сообщение для отправки всем пользователям: ").strip()
        
        if message:
            self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps(
                {"type": "notification", "text": f"СЕРВЕР: {message}"}, ensure_ascii=False))
            self.add_log(f"Отправлено системное сообщение: {message}", "admin")
            print("[OK] Сообщение отправлено всем пользователям")
        else:
            print("[ERROR] Сообщение не может быть пустым")
        time.sleep(1)
    
    def show_stats(self):
        self.clear_screen()
        stats = self.server.storage.get_stats()
        self._border("СТАТИСТИКА СЕРВЕРА")
        self._line("")
        self._line(f"Всего пользователей:   {stats.get('users', 0)}")
        self._line(f"Сообщений в чате:      {stats.get('messages', 0)}")
        self._line(f"Приватных сообщений:   {stats.get('private_messages', 0)}")
        self._line(f"Групп:                 {stats.get('groups', 0)}")
        self._line(f"Файлов:                {stats.get('files', 0)}")
        self._line("")
        self._line(f"Онлайн (TCP):          {len(self.server.clients)}")
        self._line(f"WebSocket (Web):       {len(self.server.api_server.active_websockets)}")
        self._line("")
        self._border()
        input("\nНажмите Enter для продолжения...")
    
    def demote_admin(self):
        username = input("Введите логин администратора для лишения прав: ").strip()
        
        if username == "adminSK":
            print("[ERROR] Нельзя лишить прав главного администратора!")
            time.sleep(2)
            return
        
        if self.server.storage.demote_admin(username):
            print(f"[OK] Права администратора у {username} отозваны")
            self.add_log(f"Лишены прав администратора: {username}", "admin")
        else:
            print(f"[ERROR] Пользователь {username} не найден или не является администратором")
        time.sleep(2)
    
    def show_info(self):
        self.clear_screen()
        self._border("ИНФОРМАЦИЯ О СЕРВЕРЕ")
        self._line("")
        self._line("Название:        Messenger Server")
        self._line("Версия:          2.0.0")
        self._line("Создатель:       StreloK_45")
        self._line("Язык:            Python 3.12+")
        self._line("Веб-фреймворк:   FastAPI + Uvicorn")
        self._line("База данных:     SQLite 3")
        self._line("WebSocket:       Поддерживается")
        self._line("Аутентификация:  JWT (SimpleJWT)")
        self._line("Desktop клиент:  TCP сокеты (порт 5555)")
        self._line("Web клиент:      REST API + WS (порт 8000)")
        self._line("Файловый сервер: Порт 5556")
        self._line("Режим работы:    Dual-Mode")
        self._line("")
        self._border()
        input("\nНажмите Enter для продолжения...")
    
    def run(self):
        while self.running:
            self.print_menu()
            choice = input("> ").strip()
            
            if choice == "1":
                self.view_logs()
            elif choice == "2":
                self.admin_login()
            elif choice == "3":
                self.show_info()
            elif choice == "4":
                self.clear_screen()
                self._border("ЗАВЕРШЕНИЕ РАБОТЫ")
                self._line("")
                self._line("Вы уверены, что хотите остановить сервер?")
                self._line("")
                self._border()
                confirm = input("(y/n): ").strip().lower()
                if confirm == 'y':
                    print("\n[STOP] Остановка сервера...")
                    self.running = False
                    self.server.running = False
                    time.sleep(1)
                    os._exit(0)
            else:
                print("[ERROR] Неверный выбор!")
                time.sleep(1)
class DualModeServer:
    """Сервер, работающий одновременно в двух режимах"""
    
    def __init__(self):
        self.config = ChatConfig()
        self.config.ensure_dirs()
        
        # Общее хранилище (SQLite)
        self.storage = Storage(self.config)
        
        # FastAPI сервер
        self.api_server = ApiServer(self.storage, self.config, 
                                     host=self.config.HOST, 
                                     port=8000)
        
        # Старые компоненты для Desktop-клиентов
        self.network = NetworkManager(self)
        self.auth = AuthManager(self)
        self.chat = ChatManager(self)
        self.files = FileManager(self)
        self.admin = AdminManager(self)
        
        # Состояние сервера
        self.running = True
        self.clients = []
        self.client_data = {}
        self.root = None
        
        # Консольное меню
        self.console = ConsoleMenu(self)
        
        print("=" * 50)
        print("🚀 Messenger Server v2.0 (Dual-Mode)")
        print("=" * 50)
        print(f"📁 Data directory: {self.config.DATA_DIR}")
        print(f"🗄️  Database: {self.config.DATABASE_PATH}")
        print(f"📂 Files: {self.config.RECEIVED_FILES_DIR}")
        print("=" * 50)
    
    def log(self, message: str, level: str = "info"):
        """Метод логгирования"""
        self.console.add_log(message, level)
    
    def update_online_display(self):
        """Обновляет отображение онлайна"""
        pass
    
    def start_legacy_socket_server(self):
        """Запускает старый TCP сокет-сервер"""
        print("\n🔌 Legacy Socket Server (for Desktop clients):")
        self.network.start_servers()
        print(f"   - Chat socket: {self.config.HOST}:{self.config.PORT}")
        print(f"   - File socket: {self.config.HOST}:{self.config.FILE_PORT}")
    
    def start_fastapi_server(self):
        """Запускает FastAPI сервер"""
        print("\n🌐 FastAPI Server (for Web clients):")
        print(f"   - API: http://{self.config.HOST}:8000")
        print(f"   - WebSocket: ws://{self.config.HOST}:8000/ws")
        print(f"   - Docs: http://{self.config.HOST}:8000/docs")
        
        # Запускаем в отдельном потоке
        def run_api():
            self.api_server.run()
        
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        time.sleep(1)  # Даём время на запуск
    
    def run(self):
        """Запускает сервер"""
        # Запускаем старый сокет-сервер
        socket_thread = threading.Thread(target=self.start_legacy_socket_server, daemon=True)
        socket_thread.start()
        
        # Запускаем FastAPI
        self.start_fastapi_server()
        
        # Запускаем консольное меню
        self.console.run()


def main():
    server = DualModeServer()
    
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n\n🛑 Сервер остановлен")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()