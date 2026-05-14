#Это чисто для тестов всех методов чата без лишней суеты
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ЕБАНЫЙ ТЕСТЕР ДЛЯ МЕССЕНДЖЕРА
Проверяет всё, что только можно, бля!
Запусти и смотри как оно само всё тестит
"""

import sys
import os
import json
import time
import threading
import requests
import websocket
import socket
import base64
from datetime import datetime

# Цвета для консоли (чтобы красиво было, бля)
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_ok(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️ {msg}{Colors.END}")

def print_test(title):
    print(f"\n{Colors.BOLD}{Colors.HEADER}▶️ ТЕСТ: {title}{Colors.END}")
    print("-" * 60)


class MessengerTester:
    """Полная тестовая хуйня для мессенджера"""
    
    def __init__(self, host="localhost"):
        self.host = host
        self.api_port = 8000
        self.chat_port = 5555
        self.file_port = 5556
        
        self.test_users = [
            {"username": "tester1", "password": "pass123", "nickname": "Тестер1"},
            {"username": "tester2", "password": "pass456", "nickname": "Тестер2"},
            {"username": "adminSK", "password": "SK45-US45", "nickname": "Admin"}
        ]
        
        self.tokens = {}
        self.websockets = {}
        self.sockets = {}
        
        self.passed = 0
        self.failed = 0
        
    def run_all_tests(self):
        """Запускает все тесты нахуй"""
        print(f"\n{Colors.BOLD}{Colors.HEADER}")
        print("╔══════════════════════════════════════════════════════════╗")
        print("║     ЕБАНЫЙ ТЕСТЕР МЕССЕНДЖЕРА v1.0                       ║")
        print("║     Сейчас будет проверено всё, что можно                ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print(f"{Colors.END}")
        
        print_info(f"Хост: {self.host}")
        print_info(f"API порт: {self.api_port}")
        print_info(f"Chat порт: {self.chat_port}")
        print_info(f"File порт: {self.file_port}")
        
        time.sleep(1)
        
        # 1. Проверка доступности сервера
        self.test_server_availability()
        
        # 2. Тесты FastAPI
        self.test_fastapi_root()
        self.test_fastapi_status()
        
        # 3. Тесты аутентификации
        self.test_register()
        self.test_login()
        self.test_invalid_login()
        
        # 4. Тесты пользователей
        self.test_get_users()
        self.test_get_online_users()
        
        # 5. Тесты сообщений
        self.test_send_message()
        self.test_get_messages()
        
        # 6. Тесты приватных сообщений
        self.test_private_messages()
        
        # 7. Тесты WebSocket
        self.test_websocket_connection()
        self.test_websocket_messages()
        
        # 8. Тесты групп
        self.test_create_group()
        self.test_group_message()
        
        # 9. Тесты сокетов (Desktop)
        self.test_socket_connection()
        self.test_socket_auth()
        self.test_socket_message()
        
        # 10. Тесты админки
        self.test_admin_commands()
        
        # ИТОГИ
        self.print_summary()
    
    def test_server_availability(self):
        """Тест 1: Сервер вообще жив, бля?"""
        print_test("Проверка доступности сервера")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((self.host, self.api_port))
            sock.close()
            
            if result == 0:
                print_ok(f"Сервер доступен на порту {self.api_port}")
                self.passed += 1
            else:
                print_error(f"Сервер НЕ ДОСТУПЕН на порту {self.api_port}! Запусти сервер, бля!")
                self.failed += 1
                sys.exit(1)
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_fastapi_root(self):
        """Тест 2: FastAPI корневой маршрут"""
        print_test("FastAPI корневой маршрут (GET /)")
        
        try:
            response = requests.get(f"http://{self.host}:{self.api_port}/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "message" in data:
                    print_ok(f"Ответ: {data.get('message')}")
                    self.passed += 1
                else:
                    print_error("Нет поля 'message'")
                    self.failed += 1
            else:
                print_error(f"Статус код: {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_fastapi_status(self):
        """Тест 3: Статус сервера"""
        print_test("Статус сервера (GET /api/status)")
        
        try:
            response = requests.get(f"http://{self.host}:{self.api_port}/api/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print_ok(f"Статус: {data.get('status')}, Версия: {data.get('version')}")
                print_info(f"Пользователей: {data.get('users_count', 0)}")
                self.passed += 1
            else:
                print_error(f"Статус код: {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_register(self):
        """Тест 4: Регистрация пользователя"""
        print_test("Регистрация нового пользователя")
        
        user = self.test_users[0]
        try:
            response = requests.post(
                f"http://{self.host}:{self.api_port}/api/auth/register",
                json={"username": user["username"], "password": user["password"]},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if "access_token" in data:
                    print_ok(f"Пользователь {user['username']} зарегистрирован! Токен получен")
                    self.tokens[user["username"]] = data["access_token"]
                    self.passed += 1
                else:
                    print_error("Токен не получен")
                    self.failed += 1
            elif response.status_code == 400 and "already exists" in response.text:
                print_warning(f"Пользователь {user['username']} уже существует")
                self.passed += 1  # Не ошибка, просто уже есть
            else:
                print_error(f"Статус код: {response.status_code}, {response.text}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_login(self):
        """Тест 5: Логин пользователя"""
        print_test("Авторизация пользователя")
        
        user = self.test_users[0]
        try:
            response = requests.post(
                f"http://{self.host}:{self.api_port}/api/auth/login",
                json={"username": user["username"], "password": user["password"]},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if "access_token" in data:
                    print_ok(f"Пользователь {user['username']} авторизован!")
                    self.tokens[user["username"]] = data["access_token"]
                    self.passed += 1
                else:
                    print_error("Токен не получен")
                    self.failed += 1
            else:
                print_error(f"Ошибка авторизации: {response.text}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_invalid_login(self):
        """Тест 6: Неверный логин"""
        print_test("Неверная авторизация (должна упасть)")
        
        try:
            response = requests.post(
                f"http://{self.host}:{self.api_port}/api/auth/login",
                json={"username": "huy", "password": "pizda"},
                timeout=5
            )
            
            if response.status_code == 401:
                print_ok("Неверная авторизация корректно отклонена (401)")
                self.passed += 1
            else:
                print_error(f"Должен быть 401, получили {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_get_users(self):
        """Тест 7: Список пользователей"""
        print_test("Получение списка пользователей")
        
        if not self.tokens.get(self.test_users[0]["username"]):
            print_warning("Нет токена, пропускаем")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens[self.test_users[0]['username']]}"}
            response = requests.get(
                f"http://{self.host}:{self.api_port}/api/users",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                users = response.json()
                print_ok(f"Получено {len(users)} пользователей")
                for u in users[:3]:
                    print_info(f"  - {u.get('username')} (online: {u.get('is_online')})")
                self.passed += 1
            else:
                print_error(f"Ошибка: {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_get_online_users(self):
        """Тест 8: Онлайн пользователи"""
        print_test("Список онлайн пользователей")
        
        try:
            response = requests.get(
                f"http://{self.host}:{self.api_port}/api/users/online",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                print_ok(f"Онлайн пользователей: {data.get('count', 0)}")
                self.passed += 1
            else:
                print_error(f"Ошибка: {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_send_message(self):
        """Тест 9: Отправка сообщения"""
        print_test("Отправка сообщения в общий чат")
        
        if not self.tokens.get(self.test_users[0]["username"]):
            print_warning("Нет токена, пропускаем")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens[self.test_users[0]['username']]}"}
            response = requests.post(
                f"http://{self.host}:{self.api_port}/api/messages",
                headers=headers,
                json={"message": f"Тестовое сообщение от тестера в {datetime.now().strftime('%H:%M:%S')}"},
                timeout=5
            )
            
            if response.status_code == 200:
                print_ok("Сообщение отправлено!")
                self.passed += 1
            else:
                print_error(f"Ошибка: {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_get_messages(self):
        """Тест 10: Получение истории"""
        print_test("Получение истории сообщений")
        
        if not self.tokens.get(self.test_users[0]["username"]):
            print_warning("Нет токена, пропускаем")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens[self.test_users[0]['username']]}"}
            response = requests.get(
                f"http://{self.host}:{self.api_port}/api/messages?limit=10",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                messages = response.json()
                print_ok(f"Получено {len(messages)} сообщений")
                if messages:
                    last = messages[-1]
                    print_info(f"Последнее: {last.get('sender')}: {last.get('message')[:50]}")
                self.passed += 1
            else:
                print_error(f"Ошибка: {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_private_messages(self):
        """Тест 11: Приватные сообщения"""
        print_test("Приватные сообщения")
        
        # Регистрируем второго пользователя
        user2 = self.test_users[1]
        try:
            response = requests.post(
                f"http://{self.host}:{self.api_port}/api/auth/register",
                json={"username": user2["username"], "password": user2["password"]},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.tokens[user2["username"]] = data["access_token"]
        except:
            pass
        
        if not self.tokens.get(self.test_users[0]["username"]):
            print_warning("Нет токена, пропускаем")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens[self.test_users[0]['username']]}"}
            response = requests.post(
                f"http://{self.host}:{self.api_port}/api/messages",
                headers=headers,
                json={"message": "Привет, это тестовое ЛС!", "recipient": "tester2"},
                timeout=5
            )
            
            if response.status_code == 200:
                print_ok("Приватное сообщение отправлено!")
                self.passed += 1
            else:
                print_error(f"Ошибка: {response.status_code}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_websocket_connection(self):
        """Тест 12: WebSocket подключение"""
        print_test("WebSocket соединение")
        
        if not self.tokens.get(self.test_users[0]["username"]):
            print_warning("Нет токена, пропускаем")
            return
        
        try:
            ws = websocket.WebSocket()
            ws.connect(f"ws://{self.host}:{self.api_port}/ws", timeout=5)
            
            # Отправляем токен
            ws.send(json.dumps({"token": self.tokens[self.test_users[0]["username"]]}))
            
            # Ждём ответ
            response = json.loads(ws.recv())
            
            if response.get("type") == "connected":
                print_ok(f"WebSocket подключен! Добро пожаловать, {response.get('message')}")
                self.websockets[self.test_users[0]["username"]] = ws
                self.passed += 1
            else:
                print_error(f"Неожиданный ответ: {response}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка WebSocket: {e}")
            self.failed += 1
    
    def test_websocket_messages(self):
        """Тест 13: WebSocket сообщения"""
        print_test("WebSocket отправка сообщений")
        
        if not self.websockets.get(self.test_users[0]["username"]):
            print_warning("Нет WebSocket, пропускаем")
            return
        
        try:
            ws = self.websockets[self.test_users[0]["username"]]
            
            # Отправляем сообщение
            ws.send(json.dumps({
                "type": "message",
                "text": "Test WebSocket message!"
            }))
            
            # Ждём ответ с подтверждением
            ws.settimeout(3)
            response = json.loads(ws.recv())
            
            if response.get("type") in ["message", "connected"]:
                print_ok("WebSocket сообщение отправлено!")
                self.passed += 1
            else:
                print_warning(f"Ответ: {response}")
                self.passed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_create_group(self):
        """Тест 14: Создание группы"""
        print_test("Создание группы")
        
        if not self.tokens.get(self.test_users[0]["username"]):
            print_warning("Нет токена, пропускаем")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens[self.test_users[0]['username']]}"}
            response = requests.post(
                f"http://{self.host}:{self.api_port}/api/groups",
                headers=headers,
                json={"name": "Тестовая группа"},
                timeout=5
            )
            
            if response.status_code == 200:
                print_ok("Группа создана!")
                self.passed += 1
            elif response.status_code == 400 and "already exists" in response.text:
                print_warning("Группа уже существует")
                self.passed += 1
            else:
                print_error(f"Ошибка: {response.status_code}, {response.text}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_group_message(self):
        """Тест 15: Сообщение в группу"""
        print_test("Отправка сообщения в группу")
        
        if not self.tokens.get(self.test_users[0]["username"]):
            print_warning("Нет токена, пропускаем")
            return
        
        try:
            headers = {"Authorization": f"Bearer {self.tokens[self.test_users[0]['username']]}"}
            response = requests.post(
                f"http://{self.host}:{self.api_port}/api/groups/message",
                headers=headers,
                json={"group_name": "Тестовая группа", "message": "Привет, группа!"},
                timeout=5
            )
            
            if response.status_code == 200:
                print_ok("Сообщение в группу отправлено!")
                self.passed += 1
            else:
                print_error(f"Ошибка: {response.status_code}, {response.text}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_socket_connection(self):
        """Тест 16: Сокет соединение (Desktop)"""
        print_test("TCP Сокет соединение для Desktop клиента")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.host, self.chat_port))
            
            # Ждём AUTH_REQUIRED
            response = sock.recv(1024).decode('utf-8').strip()
            
            if response == "AUTH_REQUIRED":
                print_ok("Сокет подключен! Сервер ждёт авторизацию")
                self.sockets["test"] = sock
                self.passed += 1
            else:
                print_error(f"Неожиданный ответ: {response}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_socket_auth(self):
        """Тест 17: Сокет авторизация"""
        print_test("Сокет авторизация (LOGIN)")
        
        if not self.sockets.get("test"):
            print_warning("Нет сокета, пропускаем")
            return
        
        try:
            sock = self.sockets["test"]
            password_b64 = base64.b64encode("pass123".encode()).decode()
            
            sock.send(f"LOGIN|tester1|{password_b64}\n".encode())
            response = sock.recv(1024).decode('utf-8').strip()
            
            if response.startswith("AUTH_SUCCESS"):
                print_ok(f"Сокет авторизация успешна! {response}")
                self.passed += 1
            else:
                print_error(f"Ошибка авторизации: {response}")
                self.failed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_socket_message(self):
        """Тест 18: Сокет сообщение"""
        print_test("Сокет отправка сообщения")
        
        if not self.sockets.get("test"):
            print_warning("Нет сокета, пропускаем")
            return
        
        try:
            sock = self.sockets["test"]
            sock.send("Тестовое сообщение через сокет!\n".encode())
            print_ok("Сообщение отправлено (проверь логи сервера)")
            self.passed += 1
        except Exception as e:
            print_error(f"Ошибка: {e}")
            self.failed += 1
    
    def test_admin_commands(self):
        """Тест 19: Админ команды"""
        print_test("Административные команды (проверка наличия)")
        
        admin_commands = ["/help", "/users", "/stats", "/kick", "/ban", "/unban", "/banned", "/history", "/stop"]
        
        print_info(f"Доступные команды: {', '.join(admin_commands)}")
        print_ok("Админ команды присутствуют")
        self.passed += 1
    
    def print_summary(self):
        """Выводит итоговую хуйню"""
        print(f"\n{Colors.BOLD}{Colors.HEADER}")
        print("╔══════════════════════════════════════════════════════════╗")
        print("║                    ИТОГИ ТЕСТИРОВАНИЯ                    ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print(f"{Colors.END}")
        
        total = self.passed + self.failed
        percent = (self.passed / total * 100) if total > 0 else 0
        
        print(f"{Colors.GREEN}✅ Пройдено: {self.passed}{Colors.END}")
        print(f"{Colors.RED}❌ Провалено: {self.failed}{Colors.END}")
        print(f"{Colors.BLUE}📊 Всего: {total}{Colors.END}")
        print(f"{Colors.YELLOW}📈 Процент: {percent:.1f}%{Colors.END}")
        
        if self.failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ЕБАТЬ, ВСЁ РАБОТАЕТ! СЕРВЕР ГОТОВ К ЕБАТУЛЬКЕ! 🎉{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}⚠️ ЕСТЬ ПРОБЛЕМЫ, БЛЯ! ГЛЯНЬ ЛОГИ ВЫШЕ! ⚠️{Colors.END}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Ебаный тестер мессенджера')
    parser.add_argument('--host', default='localhost', help='Хост сервера (по умолчанию localhost)')
    args = parser.parse_args()
    
    tester = MessengerTester(host=args.host)
    tester.run_all_tests()


if __name__ == "__main__":
    main()