#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Полный тестер Messenger Server v2.0
Проверяет все методы API, WebSocket, TCP сокеты, группы, файлы

Запуск: python test_server_function.py [--host localhost] [--verbose]
"""

import sys
import os
import json
import time
import socket
import base64
import struct
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Проверка наличия зависимостей
try:
    import requests
except ImportError:
    print("\n" + "=" * 60)
    print("ОШИБКА: Библиотека 'requests' не установлена!")
    print("Установите: pip install requests")
    print("=" * 60)
    sys.exit(1)

# Пробуем импортировать websocket-client (правильная библиотека)
try:
    import websocket
    # Проверяем, что это правильная библиотека (есть метод create_connection)
    if not hasattr(websocket, 'create_connection'):
        raise ImportError("Wrong websocket library")
except ImportError:
    print("\n" + "=" * 60)
    print("ОШИБКА: Библиотека 'websocket-client' не установлена!")
    print("Установите: pip install websocket-client")
    print("=" * 60)
    sys.exit(1)


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_ok(msg: str):
    print(f"{Colors.GREEN}OK {msg}{Colors.END}")


def print_error(msg: str):
    print(f"{Colors.RED}FAIL {msg}{Colors.END}")


def print_info(msg: str):
    print(f"{Colors.BLUE}INFO {msg}{Colors.END}")


def print_test(title: str):
    print(f"\n{Colors.BOLD}{Colors.HEADER}TEST: {title}{Colors.END}")
    print("-" * 60)


class FullServerTester:
    """Полный тестер сервера"""
    
    def __init__(self, host: str = "localhost", verbose: bool = False):
        self.host = host
        self.api_port = 8000
        self.chat_port = 5555
        self.file_port = 5556
        self.verbose = verbose
        
        # Тестовые пользователи
        self.test_users = [
            {"username": "tester_alice", "password": "alice123", "nickname": "Алиса"},
            {"username": "tester_bob", "password": "bob123", "nickname": "Боб"},
        ]
        
        # Хранилище данных
        self.tokens: Dict[str, str] = {}
        self.test_results: List[Tuple[str, bool, str]] = []
        
        # Счётчики
        self.passed = 0
        self.failed = 0
    
    def log(self, msg: str, level: str = "info"):
        if self.verbose:
            print(f"  {msg}")
    
    def add_result(self, test_name: str, passed: bool, message: str = ""):
        self.test_results.append((test_name, passed, message))
        if passed:
            self.passed += 1
            print_ok(f"{test_name}: {message}" if message else test_name)
        else:
            self.failed += 1
            print_error(f"{test_name}: {message}" if message else test_name)
    
    def register_user(self, user: Dict) -> Optional[str]:
        """Регистрирует одного пользователя и возвращает токен"""
        try:
            resp = requests.post(
                f"http://{self.host}:{self.api_port}/api/auth/register",
                json={"username": user["username"], "password": user["password"], "nickname": user["nickname"]},
                timeout=5
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                self.log(f"Registered: {user['username']}", "ok")
                return token
            elif resp.status_code == 400:
                self.log(f"User exists: {user['username']}", "info")
                # Пробуем логин
                resp = requests.post(
                    f"http://{self.host}:{self.api_port}/api/auth/login",
                    json={"username": user["username"], "password": user["password"]},
                    timeout=5
                )
                if resp.status_code == 200:
                    return resp.json().get("access_token")
            return None
        except Exception as e:
            self.log(f"Failed: {user['username']} - {e}", "warning")
            return None
    
    def run_all_tests(self):
        """Запуск всех тестов"""
        self._print_header()
        
        # Проверка доступности
        if not self._check_server_availability():
            print_error("Сервер недоступен!")
            sys.exit(1)
        
        # Регистрируем пользователей
        print_info("Регистрация тестовых пользователей...")
        for user in self.test_users:
            token = self.register_user(user)
            if token:
                self.tokens[user["username"]] = token
            time.sleep(0.3)
        
        if not self.tokens:
            print_error("Не удалось зарегистрировать пользователей!")
            sys.exit(1)
        
        # ========== ТЕСТЫ ==========
        print_test("FASTAPI")
        self.test_api_root()
        self.test_api_status()
        
        print_test("АУТЕНТИФИКАЦИЯ")
        self.test_login()
        self.test_invalid_login()
        
        print_test("ПОЛЬЗОВАТЕЛИ")
        self.test_get_users()
        self.test_get_online_users()
        
        print_test("СООБЩЕНИЯ")
        self.test_send_message()
        self.test_get_messages()
        
        print_test("ПРИВАТНЫЕ СООБЩЕНИЯ")
        self.test_private_message()
        
        print_test("WEBSOCKET")
        self.test_websocket()
        
        print_test("ГРУППЫ")
        self.test_create_group()
        self.test_add_group_member()
        self.test_group_message()
        self.test_delete_group()
        
        print_test("TCP СОКЕТЫ")
        self.test_socket()
        
        print_test("ФАЙЛЫ")
        self.test_file_upload()
        
        # ИТОГИ
        self._print_summary()
    
    def _print_header(self):
        print(f"\n{Colors.BOLD}{Colors.HEADER}")
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║              SERVER TESTER v2.0 - Messenger Testing              ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(f"{Colors.END}")
        print_info(f"Host: {self.host}")
        print_info(f"API Port: {self.api_port}")
        print()
    
    def _check_server_availability(self) -> bool:
        print_test("Проверка доступности")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((self.host, self.api_port))
            sock.close()
            
            if result == 0:
                print_ok(f"Сервер доступен на порту {self.api_port}")
                return True
            return False
        except Exception as e:
            print_error(f"Ошибка: {e}")
            return False
    
    # ========== FASTAPI ==========
    
    def test_api_root(self):
        try:
            resp = requests.get(f"http://{self.host}:{self.api_port}/", timeout=5)
            self.add_result("GET /", resp.status_code == 200, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("GET /", False, str(e))
    
    def test_api_status(self):
        try:
            resp = requests.get(f"http://{self.host}:{self.api_port}/api/status", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.add_result("GET /api/status", True, f"Users: {data.get('users_count', 0)}")
            else:
                self.add_result("GET /api/status", False, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("GET /api/status", False, str(e))
    
    # ========== АУТЕНТИФИКАЦИЯ ==========
    
    def test_login(self):
        user = self.test_users[0]
        if user["username"] not in self.tokens:
            self.add_result("Логин", False, "Нет токена")
            return
        
        try:
            resp = requests.post(
                f"http://{self.host}:{self.api_port}/api/auth/login",
                json={"username": user["username"], "password": user["password"]},
                timeout=5
            )
            self.add_result("Логин", resp.status_code == 200, f"{user['username']}")
        except Exception as e:
            self.add_result("Логин", False, str(e))
    
    def test_invalid_login(self):
        try:
            resp = requests.post(
                f"http://{self.host}:{self.api_port}/api/auth/login",
                json={"username": "fake_user", "password": "wrong"},
                timeout=5
            )
            self.add_result("Неверный логин", resp.status_code == 401, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("Неверный логин", False, str(e))
    
    # ========== ПОЛЬЗОВАТЕЛИ ==========
    
    def test_get_users(self):
        if "tester_alice" not in self.tokens:
            self.add_result("GET /api/users", False, "Нет токена")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens['tester_alice']}"}
            resp = requests.get(f"http://{self.host}:{self.api_port}/api/users", headers=headers, timeout=5)
            if resp.status_code == 200:
                users = resp.json()
                self.add_result("GET /api/users", True, f"{len(users)} users")
            else:
                self.add_result("GET /api/users", False, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("GET /api/users", False, str(e))
    
    def test_get_online_users(self):
        try:
            resp = requests.get(f"http://{self.host}:{self.api_port}/api/users/online", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                self.add_result("GET /api/users/online", True, f"Online: {data.get('count', 0)}")
            else:
                self.add_result("GET /api/users/online", False, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("GET /api/users/online", False, str(e))
    
    # ========== СООБЩЕНИЯ ==========
    
    def test_send_message(self):
        if "tester_alice" not in self.tokens:
            self.add_result("POST /api/messages", False, "Нет токена")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens['tester_alice']}"}
            resp = requests.post(
                f"http://{self.host}:{self.api_port}/api/messages",
                headers=headers,
                json={"message": f"Test {int(time.time())}"},
                timeout=5
            )
            self.add_result("POST /api/messages", resp.status_code == 200, "Sent")
        except Exception as e:
            self.add_result("POST /api/messages", False, str(e))
    
    def test_get_messages(self):
        if "tester_alice" not in self.tokens:
            self.add_result("GET /api/messages", False, "Нет токена")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens['tester_alice']}"}
            resp = requests.get(
                f"http://{self.host}:{self.api_port}/api/messages?limit=10",
                headers=headers,
                timeout=5
            )
            if resp.status_code == 200:
                messages = resp.json()
                self.add_result("GET /api/messages", True, f"{len(messages)} messages")
            else:
                self.add_result("GET /api/messages", False, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("GET /api/messages", False, str(e))
    
    # ========== ПРИВАТНЫЕ СООБЩЕНИЯ ==========
    
    def test_private_message(self):
        if "tester_alice" not in self.tokens:
            self.add_result("Приватное сообщение", False, "Нет токена")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens['tester_alice']}"}
            resp = requests.post(
                f"http://{self.host}:{self.api_port}/api/messages",
                headers=headers,
                json={"message": "Private", "recipient": "tester_bob"},
                timeout=5
            )
            self.add_result("Приватное сообщение", resp.status_code == 200, "Sent")
        except Exception as e:
            self.add_result("Приватное сообщение", False, str(e))
    
    # ========== WEBSOCKET ==========
    
    def test_websocket(self):
        """Тест WebSocket с использованием create_connection"""
        if "tester_alice" not in self.tokens:
            self.add_result("WebSocket", False, "Нет токена")
            return
        
        try:
            # Используем правильный метод create_connection из websocket-client
            ws = websocket.create_connection(
                f"ws://{self.host}:{self.api_port}/ws",
                timeout=5
            )
            ws.send(json.dumps({"token": self.tokens["tester_alice"]}))
            ws.settimeout(3)
            response = json.loads(ws.recv())
            ws.close()
            
            if response.get("type") == "connected":
                self.add_result("WebSocket", True, "Connected")
            else:
                self.add_result("WebSocket", False, f"Response: {response}")
        except Exception as e:
            self.add_result("WebSocket", False, str(e)[:80])
    
    # ========== ГРУППЫ ==========
    
    def test_create_group(self):
        if "tester_alice" not in self.tokens:
            self.add_result("Создание группы", False, "Нет токена")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens['tester_alice']}"}
            resp = requests.post(
                f"http://{self.host}:{self.api_port}/api/groups",
                headers=headers,
                json={"name": "TestGroup"},
                timeout=5
            )
            if resp.status_code in [200, 400]:
                self.add_result("POST /api/groups", True, "OK")
            else:
                self.add_result("POST /api/groups", False, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("POST /api/groups", False, str(e))
    
    def test_add_group_member(self):
        if "tester_alice" not in self.tokens:
            self.add_result("Добавление в группу", False, "Нет токена")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens['tester_alice']}"}
            resp = requests.post(
                f"http://{self.host}:{self.api_port}/api/groups/add",
                headers=headers,
                json={"group_name": "TestGroup", "member_nickname": "tester_bob"},
                timeout=5
            )
            self.add_result("POST /api/groups/add", resp.status_code == 200, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("POST /api/groups/add", False, str(e))
    
    def test_group_message(self):
        if "tester_alice" not in self.tokens:
            self.add_result("Сообщение в группу", False, "Нет токена")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens['tester_alice']}"}
            resp = requests.post(
                f"http://{self.host}:{self.api_port}/api/groups/message",
                headers=headers,
                json={"group_name": "TestGroup", "message": "Hello!"},
                timeout=5
            )
            self.add_result("POST /api/groups/message", resp.status_code == 200, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("POST /api/groups/message", False, str(e))
    
    def test_delete_group(self):
        if "tester_alice" not in self.tokens:
            self.add_result("Удаление группы", False, "Нет токена")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens['tester_alice']}"}
            resp = requests.delete(
                f"http://{self.host}:{self.api_port}/api/groups/TestGroup",
                headers=headers,
                timeout=5
            )
            self.add_result("DELETE /api/groups", resp.status_code == 200, f"Status {resp.status_code}")
        except Exception as e:
            self.add_result("DELETE /api/groups", False, str(e))
    
    # ========== TCP СОКЕТЫ ==========
    
    def test_socket(self):
        """Тест TCP сокета"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.host, self.chat_port))
            response = sock.recv(1024).decode('utf-8').strip()
            
            if response == "AUTH_REQUIRED":
                # Пробуем авторизоваться
                password_b64 = base64.b64encode("alice123".encode()).decode()
                sock.send(f"LOGIN|tester_alice|{password_b64}\n".encode())
                auth_resp = sock.recv(1024).decode('utf-8').strip()
                
                if auth_resp.startswith("AUTH_SUCCESS"):
                    sock.send("Test message\n".encode())
                    self.add_result("TCP сокет", True, "Connected and auth OK")
                else:
                    self.add_result("TCP сокет", False, f"Auth failed: {auth_resp}")
            else:
                self.add_result("TCP сокет", False, f"Unexpected: {response}")
            
            sock.close()
        except Exception as e:
            self.add_result("TCP сокет", False, str(e))
    
    # ========== ФАЙЛЫ ==========
    
    def test_file_upload(self):
        """Тест загрузки файла"""
        # Создаём временный файл
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="test_")
        with os.fdopen(fd, 'w') as f:
            f.write("Test content\n" * 10)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.host, self.file_port))
            
            sock.send(b'U')
            
            filename = os.path.basename(path)
            filesize = os.path.getsize(path)
            
            name_bytes = filename.encode('utf-8')
            sock.send(struct.pack('>I', len(name_bytes)))
            sock.send(name_bytes)
            sock.send(struct.pack('>Q', filesize))
            
            sender = "Алиса".encode('utf-8')
            sock.send(struct.pack('>I', len(sender)))
            sock.send(sender)
            
            response = sock.recv(1)
            if response == b'K':
                with open(path, 'rb') as f:
                    while True:
                        data = f.read(8192)
                        if not data:
                            break
                        sock.send(data)
                self.add_result("Загрузка файла", True, filename)
            else:
                self.add_result("Загрузка файла", False, "Server rejected")
            
            sock.close()
        except Exception as e:
            self.add_result("Загрузка файла", False, str(e))
        finally:
            try:
                os.remove(path)
            except:
                pass
    
    def _print_summary(self):
        total = self.passed + self.failed
        percent = (self.passed / total * 100) if total > 0 else 0
        
        print(f"\n{Colors.BOLD}{Colors.HEADER}")
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║                         РЕЗУЛЬТАТЫ ТЕСТОВ                        ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(f"{Colors.END}")
        
        print(f"{Colors.GREEN}Пройдено: {self.passed}{Colors.END}")
        print(f"{Colors.RED}Провалено: {self.failed}{Colors.END}")
        print(f"{Colors.BLUE}Всего: {total}{Colors.END}")
        print(f"{Colors.YELLOW}Процент: {percent:.1f}%{Colors.END}")
        
        if self.failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}ВСЕ ТЕСТЫ ПРОЙДЕНЫ!{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}ЕСТЬ ОШИБКИ!{Colors.END}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Тестер сервера Messenger')
    parser.add_argument('--host', default='localhost', help='Хост сервера')
    parser.add_argument('--verbose', '-v', action='store_true', help='Подробный вывод')
    args = parser.parse_args()
    
    tester = FullServerTester(host=args.host, verbose=args.verbose)
    tester.run_all_tests()


if __name__ == "__main__":
    main()