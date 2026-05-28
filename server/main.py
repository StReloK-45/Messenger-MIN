# server/main.py
import sys
import os
import json
import threading
import time
import signal
import socket
from datetime import datetime
from typing import Optional, Dict, Any, List

from logger import logger

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ChatConfig
from storage import Storage
from api import ApiServer

# Импорты для сокет-сервера (для совместимости с Desktop)
from network import NetworkManager
from auth import AuthManager
from chat import ChatManager
from files import FileManager
from admin import AdminManager


class ConsoleMenu:
    """Консольное меню с рамками и автовыравниванием"""
    
    def __init__(self, server):
        self.server = server
        self.running = True
        self.log_lines: List[str] = []
        self.log_lock = threading.Lock()
        self.width = 60
    
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _line(self, text: str = "", center: bool = False):
        """Печать строки внутри рамки"""
        content_width = self.width - 4
        if len(text) > content_width:
            text = text[:content_width - 3] + "..."
        
        if center:
            text = text.center(content_width)
        else:
            text = text.ljust(content_width)
        
        print("| " + text + " |")
    
    def _border(self, title: str = ""):
        """Печать границы"""
        print("+" + "-" * (self.width - 2) + "+")
        if title:
            self._line(title, center=True)
            print("+" + "-" * (self.width - 2) + "+")
    
    def print_menu(self):
        self.clear_screen()
        self._border("MESSENGER SERVER v2.0")
        self._line("")
        self._line("1. Просмотр логов сервера")
        self._line("2. Администрирование")
        self._line("3. Информация о сервере")
        self._line("4. Статистика сервера")
        self._line("5. Завершение работы сервера")
        self._line("")
        self._border()
        self._line("Выберите опцию (1-5):", center=True)
        self._border()
    
    def add_log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        level_config = {
            "error": {"color": "\033[91m", "prefix": "ERROR"},
            "warning": {"color": "\033[93m", "prefix": "WARN"},
            "success": {"color": "\033[92m", "prefix": "OK"},
            "admin": {"color": "\033[95m", "prefix": "ADMIN"},
            "system": {"color": "\033[96m", "prefix": "SYS"},
            "online": {"color": "\033[94m", "prefix": "ONLINE"},
            "info": {"color": "\033[0m", "prefix": "INFO"}
        }
        
        cfg = level_config.get(level, level_config["info"])
        formatted = f"[{timestamp}] {cfg['prefix']}: {message}"
        
        with self.log_lock:
            self.log_lines.append(formatted)
            if len(self.log_lines) > 1000:
                self.log_lines = self.log_lines[-1000:]
        
        print(f"{cfg['color']}{formatted}\033[0m")
    
    def view_logs(self):
        self.clear_screen()
        width_log = 80
        
        print("+" + "-" * (width_log - 2) + "+")
        print("|" + " ЛОГИ СЕРВЕРА ".center(width_log - 2) + "|")
        print("+" + "-" * (width_log - 2) + "+")
        
        with self.log_lock:
            start_idx = max(0, len(self.log_lines) - 25)
            for line in self.log_lines[start_idx:]:
                display_line = line[:width_log - 6] if len(line) > width_log - 6 else line
                print("| " + display_line.ljust(width_log - 4) + " |")
        
        print("+" + "-" * (width_log - 2) + "+")
        print("| Нажмите Enter для обновления, 'q' для выхода".ljust(width_log - 4) + " |")
        print("+" + "-" * (width_log - 2) + "+")
        
        last_count = len(self.log_lines)
        
        while True:
            # Простой способ обновления
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
            
            time.sleep(0.5)
    
    def _admin_login(self):
        """Вход в админ-панель"""
        self.clear_screen()
        self._border("АДМИН ВХОД")
        self._line("")
        
        username = input("|   Логин: ").strip()
        password = input("|   Пароль: ").strip()
        
        self._line("")
        self._border()
        
        # Проверка через БД
        user = self.server.storage.get_user(username)
        if user and user.get('is_admin'):
            from security import SimpleHash
            if SimpleHash.verify_password(password, user.get('salt', ''), user.get('password_hash', '')):
                print("\n[OK] Авторизация успешна!")
                time.sleep(1)
                self._admin_panel(username)
                return True
        
        # Fallback для главного админа
        if username == "adminSK" and password == "SK45-US45":
            print("\n[OK] Авторизация успешна!")
            time.sleep(1)
            self._admin_panel(username)
            return True
        
        print("\n[ERROR] Неверный логин или пароль!")
        time.sleep(2)
        return False
    
    def _admin_panel(self, admin_name: str):
        """Панель администратора"""
        while True:
            self.clear_screen()
            self._border(f"ПАНЕЛЬ АДМИНИСТРАТОРА ({admin_name})")
            self._line("")
            self._line("1. Просмотр онлайн пользователей")
            self._line("2. Кикнуть пользователя")
            self._line("3. Забанить пользователя")
            self._line("4. Разбанить IP")
            self._line("5. Список забаненных IP")
            self._line("6. Показать историю сообщений")
            self._line("7. Создать администратора")
            self._line("8. Отправить сообщение от сервера")
            self._line("9. Статистика сервера")
            self._line("10. Забрать права администратора")
            self._line("0. Назад")
            self._line("")
            self._border()
            
            choice = input("Выберите опцию: ").strip()
            
            if choice == "0":
                break
            elif choice == "1":
                self._show_online_users()
            elif choice == "2":
                self._kick_user()
            elif choice == "3":
                self._ban_user()
            elif choice == "4":
                self._unban_ip()
            elif choice == "5":
                self._show_banned()
            elif choice == "6":
                self._show_history()
            elif choice == "7":
                self._create_admin()
            elif choice == "8":
                self._send_system_message()
            elif choice == "9":
                self._show_stats()
            elif choice == "10":
                self._demote_admin()
            else:
                print("[ERROR] Неверный выбор!")
                time.sleep(1)
    
    def _show_online_users(self):
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
                admin = "👑 " if data.get('is_admin') else ""
                self._line(f"{admin}{nickname} (@{username}) - {addr}")
        
        self._line("")
        self._border()
        input("\nНажмите Enter для продолжения...")
    
    def _kick_user(self):
        nickname = input("Введите никнейм пользователя: ").strip()
        
        for client, data in list(self.server.client_data.items()):
            if data.get('nickname') == nickname:
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                    "type": "kicked",
                    "reason": "Кикнут администратором"
                }, ensure_ascii=False))
                time.sleep(0.1)
                self.server.network.remove_client(client)
                self.add_log(f"Пользователь {nickname} кикнут", "admin")
                print(f"[OK] Пользователь {nickname} кикнут")
                time.sleep(1)
                return
        
        print(f"[ERROR] Пользователь {nickname} не найден")
        time.sleep(1)
    
    def _ban_user(self):
        nickname = input("Введите никнейм пользователя: ").strip()
        
        for client, data in list(self.server.client_data.items()):
            if data.get('nickname') == nickname:
                ip = data.get('addr')
                self.server.storage.ban_ip(ip, f"Забанен администратором: {nickname}")
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                    "type": "banned",
                    "reason": "Забанен администратором"
                }, ensure_ascii=False))
                time.sleep(0.1)
                self.server.network.remove_client(client)
                self.add_log(f"Пользователь {nickname} забанен (IP: {ip})", "admin")
                print(f"[OK] Пользователь {nickname} забанен")
                time.sleep(1)
                return
        
        print(f"[ERROR] Пользователь {nickname} не найден")
        time.sleep(1)
    
    def _unban_ip(self):
        ip = input("Введите IP для разбана: ").strip()
        
        if self.server.storage.unban_ip(ip):
            print(f"[OK] IP {ip} разбанен")
            self.add_log(f"IP {ip} разбанен", "admin")
        else:
            print(f"[ERROR] IP {ip} не найден")
        time.sleep(1)
    
    def _show_banned(self):
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
    
    def _show_history(self):
        self.clear_screen()
        count_input = input("Сколько последних сообщений? (по умолчанию 50): ").strip()
        count = int(count_input) if count_input.isdigit() else 50
        
        messages = self.server.storage.get_chat_history(count)
        self._border(f"ПОСЛЕДНИЕ {len(messages)} СООБЩЕНИЙ")
        self._line("")
        
        if not messages:
            self._line("Нет сообщений")
        else:
            for msg in messages:
                sender = msg.get('sender', 'Unknown')
                text = msg.get('message', '')[:60]
                timestamp = msg.get('timestamp', '')
                if len(timestamp) > 16:
                    timestamp = timestamp[11:16]
                self._line(f"[{timestamp}] {sender}: {text}")
        
        self._line("")
        self._border()
        input("\nНажмите Enter для продолжения...")
    
    def _create_admin(self):
        self.clear_screen()
        self._border("СОЗДАНИЕ АДМИНИСТРАТОРА")
        self._line("")
        
        username = input("|   Логин: ").strip()
        password = input("|   Пароль: ").strip()
        nickname = input("|   Никнейм (Enter = логин): ").strip()
        
        if not nickname:
            nickname = username
        
        existing = self.server.storage.get_user(username)
        if existing:
            print("\n[ERROR] Пользователь уже существует!")
        else:
            from security import SimpleHash
            salt = SimpleHash.generate_salt()
            password_hash = SimpleHash.hash_password(password, salt)
            user_id = self.server.storage.create_user(username, password_hash, salt, is_admin=True)
            
            if user_id:
                self.server.storage.update_user_nickname(username, nickname)
                print("\n[OK] Администратор создан!")
                self.add_log(f"Создан администратор: {username}", "admin")
            else:
                print("\n[ERROR] Ошибка при создании!")
        time.sleep(2)
    
    def _send_system_message(self):
        message = input("Введите сообщение для всех: ").strip()
        
        if message:
            self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
                "type": "notification",
                "text": f"СЕРВЕР: {message}"
            }, ensure_ascii=False))
            self.add_log(f"Системное сообщение: {message}", "admin")
            print("[OK] Сообщение отправлено")
        else:
            print("[ERROR] Сообщение не может быть пустым")
        time.sleep(1)
    
    def _show_stats(self):
        self.clear_screen()
        stats = self.server.storage.get_stats()
        self._border("СТАТИСТИКА СЕРВЕРА")
        self._line("")
        self._line(f"Пользователей:           {stats.get('users', 0)}")
        self._line(f"Сообщений в чате:        {stats.get('messages', 0)}")
        self._line(f"Приватных сообщений:     {stats.get('private_messages', 0)}")
        self._line(f"Оффлайн сообщений:       {stats.get('offline_messages', 0)}")
        self._line(f"Групп:                   {stats.get('groups', 0)}")
        self._line(f"Файлов:                  {stats.get('files', 0)}")
        self._line("")
        self._line(f"Онлайн (TCP):            {len(self.server.clients)}")
        if hasattr(self.server, 'api_server'):
            self._line(f"WebSocket:               {len(self.server.api_server.active_websockets)}")
        self._line("")
        self._border()
        input("\nНажмите Enter для продолжения...")
    
    def _demote_admin(self):
        username = input("Введите логин администратора: ").strip()
        
        if username == "adminSK":
            print("[ERROR] Нельзя лишить прав главного администратора!")
            time.sleep(2)
            return
        
        if self.server.storage.demote_admin(username):
            print(f"[OK] Права администратора у {username} отозваны")
            self.add_log(f"Лишены прав администратора: {username}", "admin")
        else:
            print(f"[ERROR] Пользователь {username} не найден")
        time.sleep(2)
    
    def _show_info(self):
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
        self._line("Аутентификация:  JWT")
        self._line("Desktop клиент:  TCP сокеты (порт 5555)")
        self._line("Web клиент:      REST API + WS (порт 8000)")
        self._line("Файловый сервер: Порт 5556")
        self._line("Режим работы:    Dual-Mode")
        self._line("Оффлайн-сообщения: Да")
        self._line("Групповые файлы:   Да")
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
                self._admin_login()
            elif choice == "3":
                self._show_info()
            elif choice == "4":
                self._show_stats()
            elif choice == "5":
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
                    self.server.stop()
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
        self.api_server = ApiServer(
            self.storage, self.config,
            host=self.config.HOST,
            port=8000
        )
        
        # Компоненты для Desktop-клиентов
        self.network = NetworkManager(self)
        self.auth = AuthManager(self)
        self.chat = ChatManager(self)
        self.files = FileManager(self)
        self.admin = AdminManager(self)
        
        # Состояние сервера
        self.running = True
        self.clients: List[socket.socket] = []
        self.client_data: Dict[socket.socket, Dict] = {}
        self.maintenance = False
        
        # Атрибуты для совместимости (могут быть использованы другими модулями)
        self.privacy = None
        self.rate_limiter = None
        
        # Консольное меню
        self.console = ConsoleMenu(self)
        
        # Регистрируем обработчики сигналов
        self._setup_signal_handlers()
        
        print("=" * 50)
        print("Messenger Server v2.0 (Dual-Mode)")
        print("=" * 50)
        print(f"Data directory: {self.config.DATA_DIR}")
        print(f"Database: {self.config.DATABASE_PATH}")
        print(f"Files: {self.config.RECEIVED_FILES_DIR}")
        print("=" * 50)
    
    def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        def signal_handler(signum, frame):
            print("\n\nПолучен сигнал остановки...")
            self.stop()
        
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except Exception as e:
            print(f"Warning: Could not set signal handlers: {e}")
    
    def log(self, message: str, level: str = "info"):
        """Логирование через консольное меню"""
        self.console.add_log(message, level)
    
    def update_online_display(self):
        """Обновление отображения онлайна"""
        pass
    
    def start_legacy_socket_server(self):
        """Запуск сокет-сервера для Desktop клиентов"""
        try:
            self.network.start_servers()
        except Exception as e:
            self.log(f"Failed to start legacy socket server: {e}", "error")
    
    def start_fastapi_server(self):
        def run_api():
            try:
                import uvicorn
                uvicorn.run(
                    self.api_server.app,
                    host=self.config.HOST,
                    port=8000,
                    log_level="warning",
                    ws="websockets",
                    ws_ping_interval=20,
                    ws_ping_timeout=10
                )
            except Exception as e:
                self.log(f"FastAPI server error: {e}", "error")
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        time.sleep(2)  # Увеличил время ожидания
        self.log("FastAPI server started", "success")
    
    def stop(self):
        """Остановка сервера"""
        self.log("Stopping server...", "system")
        self.running = False
        
        # Останавливаем сетевые серверы
        if hasattr(self.network, 'stop_servers'):
            try:
                self.network.stop_servers()
            except Exception as e:
                self.log(f"Error stopping network: {e}", "error")
        
        # Оповещаем клиентов
        try:
            self.network.broadcast("JSON_PAYLOAD:" + json.dumps({
                "type": "notification",
                "text": "Сервер останавливается"
            }, ensure_ascii=False))
        except:
            pass
        
        # Сохраняем данные
        try:
            self.storage.save_history()
            self.storage.save_private_messages()
            self.storage.save_bans()
            self.log("Data saved", "success")
        except Exception as e:
            self.log(f"Error saving data: {e}", "error")
        
        # Закрываем клиентские соединения
        for client in self.clients[:]:
            try:
                client.close()
            except:
                pass
        
        self.log("Server stopped", "success")
    
    def run(self):
        """Запуск сервера"""
        self.log("Starting server...", "system")
        
        # Запуск сокет-сервера
        socket_thread = threading.Thread(target=self.start_legacy_socket_server, daemon=True)
        socket_thread.start()
        
        # Запуск FastAPI
        self.start_fastapi_server()
        
        self.log(f"Chat server: {self.config.HOST}:{self.config.PORT}", "success")
        self.log(f"File server: {self.config.HOST}:{self.config.FILE_PORT}", "success")
        self.log(f"API server: http://{self.config.HOST}:8000", "success")
        self.log(f"WebSocket: ws://{self.config.HOST}:8000/ws", "success")
        self.log("Server ready", "success")
        
        # Запуск консольного меню
        try:
            self.console.run()
        except KeyboardInterrupt:
            self.log("Interrupted", "warning")
            self.stop()
            sys.exit(0)
        except Exception as e:
            self.log(f"Error: {e}", "error")
            self.stop()
            sys.exit(1)


def main():
    server = DualModeServer()
    server.run()


if __name__ == "__main__":
    main()