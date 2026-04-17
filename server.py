import socket
import threading
import os
import sys
import tkinter as tk
from tkinter import scrolledtext, messagebox, Listbox
from datetime import datetime, timedelta
import hashlib
import json
import base64
import time
import struct
import re
import random
from collections import defaultdict

# ========== ОПРЕДЕЛЕНИЕ ПУТИ ДЛЯ .EXE ==========
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
CHAT_HISTORY_FILE = os.path.join(DATA_DIR, "chat_history.json")
PRIVATE_MESSAGES_FILE = os.path.join(DATA_DIR, "private_messages.json")
BANNED_IPS_FILE = os.path.join(DATA_DIR, "banned_ips.json")
RECEIVED_FILES_DIR = os.path.join(DATA_DIR, "received_files")
# =============================================

class ChatServer:
    VERSION = "1.1.0"
    
    def __init__(self, host='0.0.0.0', port=5555, file_port=5556):
        self.host = host
        self.port = port
        self.file_port = file_port
        self.clients = []
        self.client_data = {}
        self.messages_history = []
        self.private_messages = {}
        self.files_list = []
        self.message_counter = 0
        self.lock = threading.Lock()
        self.users_db = {}
        self.banned_ips = set()
        self.muted_users = {}
        self.running = True
        self.recovery_codes = {}
        
        # Антиспам
        self.message_timestamps = defaultdict(list)
        self.spam_mute_minutes = 15
        self.spam_threshold = 5
        self.spam_interval = 1.5
        
        if not os.path.exists(RECEIVED_FILES_DIR):
            os.makedirs(RECEIVED_FILES_DIR)
        
        # === СНАЧАЛА СОЗДАЁМ GUI ===
        self.setup_gui()
        
        # === ПОТОМ ЗАГРУЖАЕМ ДАННЫЕ (лог уже работает) ===
        self.load_data()
        self.load_bans()
        
        self.start_chat_server()
        self.start_file_server()
        
        self.log("="*60, "system")
        self.log(f"🚀 СЕРВЕР ЧАТА ЗАПУЩЕН (v{self.VERSION})", "system")
        self.log(f"📂 Папка данных: {DATA_DIR}", "system")
        self.log(f"📍 IP адрес сервера: {self.get_local_ip()}", "system")
        self.log(f"💬 Чат сервер: {self.port}", "system")
        self.log(f"📁 Файловый сервер: {self.file_port}", "system")
        self.log("="*60, "system")
        self.log("💡 Введите /help для списка команд", "system")
        self.log("Ожидание подключений...", "system")
        
        self.update_online_display()
        self.root.after(5000, self.periodic_update)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()
    
    def periodic_update(self):
        """Периодическое обновление онлайн-списка"""
        if self.running:
            self.update_online_display()
            self.root.after(5000, self.periodic_update)
    
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title(f"💬 Чат Сервер v{self.VERSION}")
        self.root.geometry("950x600")
        self.root.configure(bg='#1e1e1e')
        
        self.colors = {
            'bg': '#1e1e1e', 'sidebar': '#252525', 'chat_bg': '#2d2d2d',
            'input_bg': '#3c3c3c', 'text': '#d4d4d4', 'time': '#6a9955',
            'server': '#dcdcaa', 'system': '#c586c0', 'error': '#f48771',
            'button': '#0e639c', 'online': '#4ec9b0'
        }
        
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ========== ЦЕНТРАЛЬНАЯ ПАНЕЛЬ (ЛОГИ) ==========
        center_panel = tk.Frame(main_frame, bg=self.colors['bg'])
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        header = tk.Label(center_panel, text="📋 ЛОГИ СЕРВЕРА", font=("Segoe UI", 12, "bold"),
                          bg=self.colors['chat_bg'], fg='#4ec9b0', height=2)
        header.pack(fill=tk.X, pady=(0, 5))
        
        self.log_area = scrolledtext.ScrolledText(center_panel, wrap=tk.WORD, state='normal',
                                                   bg=self.colors['chat_bg'], fg=self.colors['text'],
                                                   font=("Consolas", 10), relief=tk.FLAT, borderwidth=0)
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # Теги для форматирования
        self.log_area.tag_config("time", foreground=self.colors['time'])
        self.log_area.tag_config("system", foreground=self.colors['system'])
        self.log_area.tag_config("server", foreground=self.colors['server'])
        self.log_area.tag_config("error", foreground=self.colors['error'])
        self.log_area.tag_config("online", foreground=self.colors['online'])
        self.log_area.tag_config("admin", foreground="#f48771", font=("Consolas", 10, "bold"))
        
        # ========== НИЖНЯЯ ПАНЕЛЬ (ВВОД КОМАНД) ==========
        input_frame = tk.Frame(center_panel, bg=self.colors['bg'])
        input_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.cmd_entry = tk.Entry(input_frame, font=("Consolas", 10), bg=self.colors['input_bg'],
                                   fg=self.colors['text'], relief=tk.FLAT, insertbackground=self.colors['text'])
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.cmd_entry.bind("<Return>", self.execute_command)
        
        send_btn = tk.Button(input_frame, text="▶ Выполнить", command=self.execute_command,
                             bg=self.colors['button'], fg="white", font=("Segoe UI", 9, "bold"),
                             relief=tk.FLAT, cursor="hand2")
        send_btn.pack(side=tk.RIGHT)
        
        # Кнопки под вводом
        btn_frame = tk.Frame(center_panel, bg=self.colors['bg'])
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        tk.Button(btn_frame, text="📢 Отправить в чат", command=self.send_system_message,
                  bg='#6a9955', fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(btn_frame, text="🔄 Обновить онлайн", command=self.update_online_display,
                  bg=self.colors['button'], fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT)
        
        # ========== ПРАВАЯ ПАНЕЛЬ (ОНЛАЙН И КОМАНДЫ) ==========
        right_panel = tk.Frame(main_frame, bg=self.colors['sidebar'], width=280)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        tk.Label(right_panel, text="🟢 ОНЛАЙН", font=("Segoe UI", 11, "bold"),
                 bg=self.colors['sidebar'], fg='#4ec9b0').pack(pady=(10, 5))
        
        self.online_label = tk.Label(right_panel, text="Пользователей: 0", font=("Segoe UI", 9),
                                      bg=self.colors['sidebar'], fg='#6a9955')
        self.online_label.pack(pady=(0, 5))
        
        self.online_listbox = Listbox(right_panel, bg=self.colors['chat_bg'], fg=self.colors['text'],
                                       font=("Segoe UI", 9), relief=tk.FLAT, selectbackground='#264f78',
                                       selectforeground='white', height=12)
        self.online_listbox.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(right_panel, text="🛡️ АДМИН КОМАНДЫ", font=("Segoe UI", 11, "bold"),
                 bg=self.colors['sidebar'], fg='#f48771').pack(pady=(10, 5))
        
        commands_text = tk.Text(right_panel, bg=self.colors['sidebar'], fg=self.colors['text'],
                                 font=("Segoe UI", 9), relief=tk.FLAT, borderwidth=0, height=15,
                                 cursor="arrow", wrap=tk.WORD)
        commands_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        commands_text.insert(tk.END, "/kick <ник> - кикнуть\n")
        commands_text.insert(tk.END, "/ban <ник> - забанить\n")
        commands_text.insert(tk.END, "/unban <IP> - разбанить\n")
        commands_text.insert(tk.END, "/mute <ник> <мин> - мут\n")
        commands_text.insert(tk.END, "/unmute <ник> - снять мут\n")
        commands_text.insert(tk.END, "/delmsg <id> - удалить сообщ.\n")
        commands_text.insert(tk.END, "/delfile <id> - удалить файл\n")
        commands_text.insert(tk.END, "/users - онлайн\n")
        commands_text.insert(tk.END, "/banned - список банов\n")
        commands_text.insert(tk.END, "/history - последние 10\n")
        commands_text.insert(tk.END, "/clearusers - очистить БД\n")
        commands_text.insert(tk.END, "/clearhistory - очистить\n")
        commands_text.insert(tk.END, "/stop - остановить\n")
        commands_text.insert(tk.END, "/help - помощь")
        commands_text.config(state='disabled')
    
    def log(self, text, tag="system"):
        """Добавляет сообщение в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{timestamp}] ", "time")
        self.log_area.insert(tk.END, f"{text}\n", tag)
        self.log_area.see(tk.END)
    
    def update_online_display(self):
        """Обновляет список онлайн пользователей"""
        self.online_listbox.delete(0, tk.END)
        self.online_label.config(text=f"Пользователей: {len(self.clients)}")
        
        for client, data in self.client_data.items():
            nickname = data.get('nickname', 'Unknown')
            username = data.get('username', 'Unknown')
            addr = data.get('addr', 'Unknown')
            muted = "🔇" if nickname in self.muted_users else ""
            display = f"{muted} {nickname} (@{username})"
            self.online_listbox.insert(tk.END, display)
    
    def send_system_message(self):
        """Отправляет системное сообщение в общий чат"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Системное сообщение")
        dialog.geometry("400x200")
        dialog.configure(bg='#1e1e1e')
        
        x = (dialog.winfo_screenwidth() // 2) - 200
        y = (dialog.winfo_screenheight() // 2) - 100
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="Введите сообщение:", bg='#1e1e1e', fg='white', font=("Segoe UI", 10)).pack(pady=10)
        
        entry = tk.Entry(dialog, bg='#3c3c3c', fg='white', font=("Segoe UI", 10), width=40)
        entry.pack(pady=5)
        entry.focus()
        
        def send():
            text = entry.get().strip()
            if text:
                self.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "notification", "text": text}, ensure_ascii=False))
                self.log(f"📢 Системное сообщение: {text}", "admin")
            dialog.destroy()
        
        entry.bind("<Return>", lambda e: send())
        tk.Button(dialog, text="Отправить", command=send, bg='#0e639c', fg='white').pack(pady=10)
    
    def execute_command(self, event=None):
        cmd = self.cmd_entry.get().strip()
        if not cmd:
            return
        
        self.log(f"> {cmd}", "system")
        self.cmd_entry.delete(0, tk.END)
        
        parts = cmd.split()
        if not parts:
            return
        
        command = parts[0].lower()
        
        if command == "/kick" and len(parts) >= 2:
            nickname = parts[1]
            reason = " ".join(parts[2:]) if len(parts) > 2 else "Кикнут администратором"
            self.kick_user(nickname, reason)
            
        elif command == "/ban" and len(parts) >= 2:
            nickname = parts[1]
            reason = " ".join(parts[2:]) if len(parts) > 2 else "Забанен администратором"
            self.ban_user(nickname, reason)
            
        elif command == "/unban" and len(parts) >= 2:
            ip = parts[1]
            self.unban_ip(ip)
            
        elif command == "/mute" and len(parts) >= 3:
            nickname = parts[1]
            try:
                minutes = int(parts[2])
                self.mute_user(nickname, minutes)
            except:
                self.log("❌ Укажите количество минут числом!", "error")
                
        elif command == "/unmute" and len(parts) >= 2:
            nickname = parts[1]
            self.unmute_user(nickname)
            
        elif command == "/delmsg" and len(parts) >= 2:
            msg_id = parts[1]
            self.delete_message(msg_id)
            
        elif command == "/delfile" and len(parts) >= 2:
            file_id = parts[1]
            self.delete_file(file_id)
            
        elif command == "/users":
            self.show_online_users()
            
        elif command == "/banned":
            self.show_banned_ips()
            
        elif command == "/history":
            count = int(parts[1]) if len(parts) > 1 else 10
            self.show_recent_history(count)
            
        elif command == "/clearusers":
            self.users_db = {}
            self.save_users()
            self.log("✅ База пользователей очищена", "system")
            
        elif command == "/clearhistory":
            self.messages_history = []
            self.files_list = []
            self.private_messages = {}
            self.message_counter = 0
            self.save_history()
            self.save_private_messages()
            self.log("✅ История чата очищена", "system")
            
        elif command == "/help":
            self.show_help()
            
        elif command == "/stop":
            self.log("🛑 Остановка сервера...", "error")
            self.running = False
            self.root.after(1000, self.on_close)
            
        else:
            self.log(f"❌ Неизвестная команда: {command}", "error")
        
        self.update_online_display()
    
    def show_help(self):
        self.log("="*50, "system")
        self.log("💡 ДОСТУПНЫЕ КОМАНДЫ:", "system")
        self.log("   /kick <ник> [причина]", "system")
        self.log("   /ban <ник> [причина]", "system")
        self.log("   /unban <IP>", "system")
        self.log("   /mute <ник> <минуты>", "system")
        self.log("   /unmute <ник>", "system")
        self.log("   /delmsg <id>", "system")
        self.log("   /delfile <id>", "system")
        self.log("   /users", "system")
        self.log("   /banned", "system")
        self.log("   /history [количество]", "system")
        self.log("   /clearusers", "system")
        self.log("   /clearhistory", "system")
        self.log("   /stop", "system")
        self.log("="*50, "system")
    
    # ========== АНТИСПАМ ==========
    def check_spam(self, nickname):
        """Проверяет на спам и мутит при нарушении"""
        now = time.time()
        self.message_timestamps[nickname].append(now)
        
        # Оставляем только сообщения за последние spam_interval секунд
        cutoff = now - self.spam_interval
        self.message_timestamps[nickname] = [t for t in self.message_timestamps[nickname] if t > cutoff]
        
        if len(self.message_timestamps[nickname]) >= self.spam_threshold:
            self.mute_user(nickname, self.spam_mute_minutes)
            self.message_timestamps[nickname] = []
            
            # Отправляем сообщение нарушителю
            for client, data in self.client_data.items():
                if data['nickname'] == nickname:
                    self.send_to_client(client, "MSG:СЕРВЕР: 🔇 Вы замучены на 15 минут за спам!")
                    break
            
            self.log(f"🔇 {nickname} замучен на 15 минут за спам", "admin")
            return True
        return False
    
    # ========== СЕТЕВЫЕ ФУНКЦИИ ==========
    def get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def get_chat_id(self, user1, user2):
        return "|".join(sorted([user1, user2]))
    
    def load_data(self):
        old_users_file = os.path.join(BASE_DIR, "users.json")
        if os.path.exists(old_users_file) and not os.path.exists(USERS_FILE):
            try:
                import shutil
                shutil.move(old_users_file, USERS_FILE)
                self.log(f"📦 Старый users.json перемещён в data/", "system")
            except:
                pass
        
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    self.users_db = json.load(f)
                self.log(f"✅ Загружено {len(self.users_db)} пользователей", "system")
            except Exception as e:
                self.log(f"❌ Ошибка загрузки пользователей: {e}", "error")
        else:
            self.users_db = {}
            self.save_users()
        
        if os.path.exists(CHAT_HISTORY_FILE):
            try:
                with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.messages_history = data.get('messages', [])
                    self.files_list = data.get('files', [])
                    self.message_counter = data.get('counter', 0)
                self.log(f"✅ Загружено {len(self.messages_history)} сообщений", "system")
                self.log(f"✅ Загружено {len(self.files_list)} файлов", "system")
            except Exception as e:
                self.log(f"❌ Ошибка загрузки истории: {e}", "error")
                self.messages_history = []
                self.files_list = []
                self.message_counter = 0
        
        if os.path.exists(PRIVATE_MESSAGES_FILE):
            try:
                with open(PRIVATE_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                    self.private_messages = json.load(f)
                total_pm = sum(len(msgs) for msgs in self.private_messages.values())
                self.log(f"✅ Загружено {total_pm} личных сообщений", "system")
            except Exception as e:
                self.log(f"❌ Ошибка загрузки личных сообщений: {e}", "error")
                self.private_messages = {}
                
    def load_bans(self):
        if os.path.exists(BANNED_IPS_FILE):
            try:
                with open(BANNED_IPS_FILE, 'r') as f:
                    self.banned_ips = set(json.load(f))
                self.log(f"✅ Загружено {len(self.banned_ips)} забаненных IP", "system")
            except Exception as e:
                self.log(f"❌ Ошибка загрузки банов: {e}", "error")

    def save_bans(self):
        try:
            with open(BANNED_IPS_FILE, 'w') as f:
                json.dump(list(self.banned_ips), f)
        except Exception as e:
            self.log(f"❌ Ошибка сохранения банов: {e}", "error")

    def save_users(self):
        try:
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.users_db, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"❌ Ошибка сохранения пользователей: {e}", "error")
    
    def save_history(self):
        try:
            clean_files = []
            for f in self.files_list:
                clean_files.append({
                    'id': str(f.get('id', '')),
                    'name': str(f.get('name', '')),
                    'path': str(f.get('path', '')),
                    'size': int(f.get('size', 0)),
                    'sender': str(f.get('sender', '')),
                    'date': str(f.get('date', '')),
                    'chat': str(f.get('chat', 'general'))
                })
            
            clean_messages = []
            for m in self.messages_history:
                clean_messages.append({
                    'id': str(m.get('id', '')),
                    'sender': str(m.get('sender', '')),
                    'text': str(m.get('text', '')),
                    'time': str(m.get('time', '')),
                    'edited': bool(m.get('edited', False))
                })
            
            data = {
                'messages': clean_messages,
                'files': clean_files,
                'counter': int(self.message_counter)
            }
            
            json_str = json.dumps(data, ensure_ascii=True, indent=2)
            
            with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
                f.write(json_str)
        except Exception as e:
            self.log(f"❌ Ошибка сохранения истории: {e}", "error")
    
    def save_private_messages(self):
        try:
            json_str = json.dumps(self.private_messages, ensure_ascii=True, indent=2)
            with open(PRIVATE_MESSAGES_FILE, 'w', encoding='utf-8') as f:
                f.write(json_str)
        except Exception as e:
            self.log(f"❌ Ошибка сохранения личных сообщений: {e}", "error")
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()[:32]
    
    def decode_base64(self, encoded):
        return base64.b64decode(encoded.encode()).decode()
    
    def register_user(self, username, password, nickname):
        if username in self.users_db:
            return False, "❌ Логин уже занят! Выберите другой."
        if len(username) < 3:
            return False, "❌ Логин должен быть не менее 3 символов!"
        if len(username) > 20:
            return False, "❌ Логин должен быть не более 20 символов!"
        if len(password) < 4:
            return False, "❌ Пароль должен быть не менее 4 символов!"
        if not nickname or nickname.strip() == "":
            nickname = username
        
        self.users_db[username] = {
            "password": self.hash_password(password),
            "nickname": nickname
        }
        self.save_users()
        return True, "✅ Регистрация успешна!"
    
    def login_user(self, username, password):
        if username not in self.users_db:
            return False, "❌ Пользователь с таким логином не найден!"
        if self.users_db[username]["password"] != self.hash_password(password):
            return False, "❌ Неверный пароль!"
        return True, self.users_db[username]["nickname"]
    
    def broadcast(self, message, exclude_socket=None):
        with self.lock:
            message_bytes = (message + "\n").encode('utf-8')
            for client in self.clients[:]:
                if client != exclude_socket:
                    try:
                        client.send(message_bytes)
                    except:
                        self.remove_client(client)
    
    def send_to_client(self, client, data):
        try:
            client.send((data + "\n").encode('utf-8'))
        except:
            self.remove_client(client)

    def remove_client(self, client):
        if client in self.clients:
            data = self.client_data.get(client, {})
            name = data.get('nickname', 'Unknown')
            self.clients.remove(client)
            if client in self.client_data:
                del self.client_data[client]
            try:
                client.close()
            except:
                pass
            self.broadcast(json.dumps({"type": "notification", "text": f"{name} покинул чат"}, ensure_ascii=False))
            self.log(f"👤 {name} отключился | Онлайн: {len(self.clients)}", "server")
            self.root.after(0, self.update_online_display)
    
    def kick_user(self, nickname, reason="Кикнут администратором"):
        for client, data in list(self.client_data.items()):
            if data['nickname'] == nickname:
                self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "kicked", "reason": reason}, ensure_ascii=False))
                time.sleep(0.1)
                self.remove_client(client)
                self.log(f"🛡️ Пользователь {nickname} кикнут. Причина: {reason}", "admin")
                return True
        self.log(f"❌ Пользователь {nickname} не найден в онлайне", "error")
        return False
    
    def ban_user(self, nickname, reason="Забанен администратором"):
        for client, data in list(self.client_data.items()):
            if data['nickname'] == nickname:
                ip = data['addr']
                self.banned_ips.add(ip)
                self.save_bans()
                self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "banned", "reason": reason}, ensure_ascii=False))
                time.sleep(0.1)
                self.remove_client(client)
                self.log(f"🛡️ Пользователь {nickname} забанен (IP: {ip})", "admin")
                return True
        self.log(f"❌ Пользователь {nickname} не найден в онлайне", "error")
        return False
    
    def unban_ip(self, ip):
        if ip in self.banned_ips:
            self.banned_ips.remove(ip)
            self.save_bans()
            self.log(f"✅ IP {ip} разбанен", "system")
            return True
        self.log(f"❌ IP {ip} не найден в списке банов", "error")
        return False
    
    def mute_user(self, nickname, minutes):
        until = datetime.now() + timedelta(minutes=minutes)
        self.muted_users[nickname] = until
        self.broadcast(json.dumps({"type": "notification", "text": f"🔇 {nickname} получил мут на {minutes} мин."}, ensure_ascii=False))
        self.log(f"🛡️ Пользователь {nickname} замучен на {minutes} минут", "admin")
        self.root.after(0, self.update_online_display)
    
    def unmute_user(self, nickname):
        if nickname in self.muted_users:
            del self.muted_users[nickname]
            self.broadcast(json.dumps({"type": "notification", "text": f"🔈 Мут с {nickname} снят."}, ensure_ascii=False))
            self.log(f"🛡️ Мут с пользователя {nickname} снят", "admin")
            self.root.after(0, self.update_online_display)
            return True
        self.log(f"❌ Пользователь {nickname} не в муте", "error")
        return False
    
    def delete_message(self, msg_id):
        for i, msg in enumerate(self.messages_history):
            if msg.get('id') == msg_id:
                deleted_msg = self.messages_history.pop(i)
                self.save_history()
                self.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "message_deleted", "id": msg_id}, ensure_ascii=False))
                self.log(f"🛡️ Сообщение {msg_id} удалено (автор: {deleted_msg.get('sender')})", "admin")
                return True
        self.log(f"❌ Сообщение с ID {msg_id} не найдено", "error")
        return False
    
    def delete_file(self, file_id):
        for i, f in enumerate(self.files_list):
            if f['id'] == file_id:
                try:
                    os.remove(f['path'])
                except:
                    pass
                deleted_file = self.files_list.pop(i)
                self.save_history()
                self.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "file_deleted", "id": file_id}, ensure_ascii=False))
                self.log(f"🛡️ Файл {file_id} удалён (название: {deleted_file.get('name')})", "admin")
                return True
        self.log(f"❌ Файл с ID {file_id} не найден", "error")
        return False
    
    def show_online_users(self):
        self.log("="*50, "system")
        self.log(f"👥 ОНЛАЙН ПОЛЬЗОВАТЕЛИ ({len(self.clients)}):", "system")
        for client, data in self.client_data.items():
            nickname = data.get('nickname', 'Unknown')
            username = data.get('username', 'Unknown')
            addr = data.get('addr', 'Unknown')
            muted = "🔇" if nickname in self.muted_users else ""
            self.log(f"   {muted} {nickname} (@{username}) - {addr}", "online")
        self.log("="*50, "system")
    
    def show_banned_ips(self):
        self.log("="*50, "system")
        self.log(f"🚫 ЗАБАНЕННЫЕ IP ({len(self.banned_ips)}):", "system")
        for ip in self.banned_ips:
            self.log(f"   ❌ {ip}", "error")
        self.log("="*50, "system")
    
    def show_recent_history(self, count=10):
        self.log("="*50, "system")
        self.log(f"📜 ПОСЛЕДНИЕ {min(count, len(self.messages_history))} СООБЩЕНИЙ:", "system")
        for msg in self.messages_history[-count:]:
            sender = msg.get('sender', 'Unknown')
            text = msg.get('text', '')[:50]
            msg_id = msg.get('id', '')
            self.log(f"   [{msg_id}] {sender}: {text}...", "system")
        self.log("="*50, "system")
    
    def start_chat_server(self):
        chat_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        chat_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        chat_server.bind((self.host, self.port))
        chat_server.listen(100)
        
        def accept_clients():
            while self.running:
                try:
                    chat_server.settimeout(1)
                    client, addr = chat_server.accept()
                    ip = addr[0]
                    
                    if ip in self.banned_ips:
                        client.send("BANNED\n".encode('utf-8'))
                        client.close()
                        self.log(f"🚫 Забаненный IP: {ip}", "error")
                        continue
                        
                    self.log(f"[+] Новое подключение: {addr}", "system")
                    client.send("AUTH_REQUIRED\n".encode('utf-8'))
                    threading.Thread(target=self.handle_auth_loop, args=(client, addr), daemon=True).start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.log(f"Ошибка accept: {e}", "error")
        
        threading.Thread(target=accept_clients, daemon=True).start()
        self.log(f"💬 Чат сервер запущен на порту {self.port}", "system")
    
    def handle_auth_loop(self, client, addr):
        auth_attempts = 0
        max_attempts = 5
        
        while auth_attempts < max_attempts and self.running:
            try:
                client.settimeout(60)
                auth_data = client.recv(4096).decode('utf-8').strip()
                
                if not auth_data:
                    break
                
                # Скрываем пароль в логах
                parts = auth_data.split('|')
                action = parts[0]
                if action == "LOGIN" and len(parts) >= 2:
                    self.log(f"🔑 Попытка входа: {parts[1]}", "system")
                elif action == "REGISTER" and len(parts) >= 2:
                    self.log(f"📝 Попытка регистрации: {parts[1]}", "system")
                
                if action == "LOGIN":
                    if len(parts) != 3:
                        self.send_to_client(client, "AUTH_FAIL|❌ Неверный формат запроса!")
                        auth_attempts += 1
                        continue
                    
                    username = parts[1]
                    password = self.decode_base64(parts[2])
                    success, result = self.login_user(username, password)
                    
                    if success:
                        nickname = result
                        self.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                        
                        self.clients.append(client)
                        self.client_data[client] = {"nickname": nickname, "username": username, "addr": addr[0]}
                        
                        history_payload = "JSON_PAYLOAD:" + json.dumps({
                            "type": "history",
                            "messages": self.messages_history[-100:],
                            "files": [f for f in self.files_list if f.get('chat', 'general') == 'general']
                        }, ensure_ascii=True)
                        self.send_to_client(client, history_payload)
                        time.sleep(0.1)
                        
                        client.settimeout(None)
                        self.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "notification", "text": f"{nickname} присоединился к чату!"}, ensure_ascii=False), exclude_socket=client)
                        self.log(f"👤 {nickname} (@{username}) вошёл | Онлайн: {len(self.clients)}", "online")
                        self.root.after(0, self.update_online_display)
                        
                        self.handle_chat(client, nickname)
                        return
                    else:
                        self.send_to_client(client, f"AUTH_FAIL|{result}")
                        auth_attempts += 1
                        
                elif action == "REGISTER":
                    if len(parts) != 4:
                        self.send_to_client(client, "AUTH_FAIL|❌ Неверный формат запроса!")
                        auth_attempts += 1
                        continue
                    
                    username = parts[1]
                    password = self.decode_base64(parts[2])
                    nickname = parts[3]
                    
                    success, result = self.register_user(username, password, nickname)
                    
                    if success:
                        self.send_to_client(client, f"AUTH_SUCCESS|{nickname}|{username}")
                        
                        self.clients.append(client)
                        self.client_data[client] = {"nickname": nickname, "username": username, "addr": addr[0]}
                        
                        history_payload = "JSON_PAYLOAD:" + json.dumps({
                            "type": "history",
                            "messages": [],
                            "files": []
                        }, ensure_ascii=True)
                        self.send_to_client(client, history_payload)
                        time.sleep(0.1)
                        
                        client.settimeout(None)
                        self.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "notification", "text": f"{nickname} присоединился к чату!"}, ensure_ascii=False), exclude_socket=client)
                        self.log(f"👤 {nickname} (@{username}) зарегистрировался | Онлайн: {len(self.clients)}", "online")
                        self.root.after(0, self.update_online_display)
                        
                        self.handle_chat(client, nickname)
                        return
                    else:
                        self.send_to_client(client, f"AUTH_FAIL|{result}")
                        auth_attempts += 1
                        
                else:
                    self.send_to_client(client, "AUTH_FAIL|❌ Неизвестная команда!")
                    auth_attempts += 1
                    
            except socket.timeout:
                self.log(f"⏰ Таймаут авторизации для {addr}", "error")
                break
            except Exception as e:
                self.log(f"❌ Ошибка авторизации: {e}", "error")
                break
        
        try:
            client.close()
        except:
            pass
    
    def handle_chat(self, client, name):
        buffer = ""
        while self.running:
            try:
                data = client.recv(4096).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue
                    
                    if name in self.muted_users:
                        if datetime.now() < self.muted_users[name]:
                            self.send_to_client(client, "MSG:СЕРВЕР: 🔇 Вы в муте!")
                            continue
                        else:
                            del self.muted_users[name]
                            self.root.after(0, self.update_online_display)
                    
                    if line.startswith("CMD:"):
                        parts = line[4:].split('|')
                        cmd = parts[0]
                        
                        if cmd == "PM" and len(parts) >= 3:
                            target = parts[1]
                            msg = "|".join(parts[2:])
                            
                            chat_id = self.get_chat_id(name, target)
                            if chat_id not in self.private_messages:
                                self.private_messages[chat_id] = []
                            
                            pm = {
                                'id': f"pm_{int(time.time()*1000)}",
                                'sender': name,
                                'text': msg,
                                'time': datetime.now().strftime("%H:%M:%S")
                            }
                            self.private_messages[chat_id].append(pm)
                            self.save_private_messages()
                            
                            target_socket = None
                            for s, data in self.client_data.items():
                                if data['nickname'] == target:
                                    target_socket = s
                                    break
                            
                            if target_socket:
                                payload = json.dumps({"type": "private_message", "from": name, "text": msg}, ensure_ascii=False)
                                self.send_to_client(target_socket, "JSON_PAYLOAD:" + payload)
                            
                            self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "private_sent", "to": target, "text": msg}, ensure_ascii=False))
                            self.log(f"💬 ЛС от {name} для {target}", "system")
                            
                        elif cmd == "GET_PM_HISTORY" and len(parts) >= 2:
                            target = parts[1]
                            chat_id = self.get_chat_id(name, target)
                            history = self.private_messages.get(chat_id, [])
                            self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                                "type": "private_history",
                                "target": target,
                                "messages": history
                            }, ensure_ascii=True))
                            
                        elif cmd == "EDIT" and len(parts) >= 4:
                            chat_type = parts[1]
                            msg_id = parts[2]
                            new_text = "|".join(parts[3:])
                            
                            if chat_type == "general":
                                for msg in self.messages_history:
                                    if msg.get('id') == msg_id and msg.get('sender') == name:
                                        msg['text'] = new_text
                                        msg['edited'] = True
                                        self.save_history()
                                        edit_msg = "JSON_PAYLOAD:" + json.dumps({"type": "message_edited", "id": msg_id, "text": new_text}, ensure_ascii=False)
                                        self.broadcast(edit_msg)
                                        self.log(f"✏️ {name} отредактировал сообщение {msg_id}", "system")
                                        break
                            else:
                                target = chat_type
                                chat_id = self.get_chat_id(name, target)
                                if chat_id in self.private_messages:
                                    for msg in self.private_messages[chat_id]:
                                        if msg.get('id') == msg_id and msg.get('sender') == name:
                                            msg['text'] = new_text
                                            msg['edited'] = True
                                            self.save_private_messages()
                                            
                                            edit_msg = "JSON_PAYLOAD:" + json.dumps({
                                                "type": "private_message_edited",
                                                "target": target,
                                                "id": msg_id,
                                                "text": new_text
                                            }, ensure_ascii=False)
                                            
                                            self.send_to_client(client, edit_msg)
                                            
                                            target_socket = None
                                            for s, data in self.client_data.items():
                                                if data['nickname'] == target:
                                                    target_socket = s
                                                    break
                                            if target_socket:
                                                self.send_to_client(target_socket, edit_msg)
                                            
                                            self.log(f"✏️ {name} отредактировал личное сообщение {msg_id} для {target}", "system")
                                            break
                            
                        elif cmd == "COLOR" and len(parts) >= 2:
                            color = parts[1]
                            color_msg = "JSON_PAYLOAD:" + json.dumps({"type": "color_update", "nick": name, "color": color}, ensure_ascii=False)
                            self.broadcast(color_msg)
                            self.log(f"🎨 {name} изменил цвет на {color}", "system")
                            
                        elif cmd == "ONLINE":
                            online_users = [data['nickname'] for data in self.client_data.values()]
                            self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({"type": "online_users", "users": online_users}, ensure_ascii=False))
                            
                        elif cmd == "FORGOT" and len(parts) >= 2:
                            username = parts[1]
                            if username in self.users_db:
                                code = str(random.randint(100000, 999999))
                                self.recovery_codes[username] = code
                                self.log("="*50, "admin")
                                self.log(f"🔐 ЗАПРОС ВОССТАНОВЛЕНИЯ", "admin")
                                self.log(f"👤 Логин: {username}", "admin")
                                self.log(f"🔑 Код: {code}", "admin")
                                self.log("="*50, "admin")
                                self.send_to_client(client, f"RECOVERY_CODE:{code}")
                            else:
                                self.send_to_client(client, "USER_NOT_FOUND")
                        continue
                    
                    # Проверка на спам перед отправкой обычного сообщения
                    if self.check_spam(name):
                        continue
                    
                    self.message_counter += 1
                    msg_id = f"msg_{self.message_counter}"
                    message = {
                        "id": msg_id,
                        "sender": name,
                        "text": line,
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "edited": False
                    }
                    self.messages_history.append(message)
                    self.save_history()
                    
                    broadcast_msg = "JSON_PAYLOAD:" + json.dumps({"type": "message", "data": message}, ensure_ascii=False)
                    self.broadcast(broadcast_msg)
                    self.log(f"📝 {name}: {line[:50]}... [ID: {msg_id}]", "system")
                    
            except Exception as e:
                self.log(f"Ошибка handle_chat для {name}: {e}", "error")
                break
        self.remove_client(client)
    
    def start_file_server(self):
        file_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        file_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        file_server.bind((self.host, self.file_port))
        file_server.listen(100)
        
        def handle_file_connections():
            while self.running:
                try:
                    file_server.settimeout(1)
                    file_socket, addr = file_server.accept()
                    self.log(f"[+] Файловое подключение: {addr}", "system")
                    threading.Thread(target=self.handle_file, args=(file_socket, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.log(f"Ошибка файлового сервера: {e}", "error")
        
        threading.Thread(target=handle_file_connections, daemon=True).start()
        self.log(f"📁 Файловый сервер запущен на порту {self.file_port}", "system")
    
    def recv_exact(self, sock, size):
        data = b''
        while len(data) < size:
            packet = sock.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data
    
    def handle_file(self, file_socket, addr):
        try:
            file_socket.settimeout(60)
            
            cmd_byte = file_socket.recv(1)
            if not cmd_byte:
                file_socket.close()
                return
            
            cmd = cmd_byte.decode('utf-8', errors='ignore')
            
            if cmd == 'L':
                general_files = [f for f in self.files_list if f.get('chat', 'general') == 'general']
                files_json = json.dumps(general_files, ensure_ascii=True).encode('utf-8')
                file_socket.send(struct.pack('>I', len(files_json)))
                file_socket.send(files_json)
                self.log(f"📋 Список общих файлов: {len(general_files)}", "system")
                
            elif cmd == 'P':
                nick_len_data = self.recv_exact(file_socket, 4)
                if not nick_len_data:
                    file_socket.close()
                    return
                nick_len = struct.unpack('>I', nick_len_data)[0]
                nick = self.recv_exact(file_socket, nick_len).decode('utf-8')
                
                private_files = [f for f in self.files_list if f.get('chat') == nick]
                files_json = json.dumps(private_files, ensure_ascii=True).encode('utf-8')
                file_socket.send(struct.pack('>I', len(files_json)))
                file_socket.send(files_json)
                self.log(f"📋 Личные файлы для {nick}: {len(private_files)}", "system")
                
            elif cmd == 'D':
                id_len_data = self.recv_exact(file_socket, 4)
                if not id_len_data:
                    file_socket.close()
                    return
                id_len = struct.unpack('>I', id_len_data)[0]
                file_id = self.recv_exact(file_socket, id_len).decode('utf-8')
                
                found = False
                for f in self.files_list:
                    if f['id'] == file_id:
                        file_socket.send(b'K')
                        file_socket.send(struct.pack('>Q', f['size']))
                        name_bytes = f['name'].encode('utf-8')
                        file_socket.send(struct.pack('>I', len(name_bytes)))
                        file_socket.send(name_bytes)
                        
                        with open(f['path'], 'rb') as file:
                            while True:
                                data = file.read(8192)
                                if not data:
                                    break
                                file_socket.send(data)
                        self.log(f"📤 Файл {f['name']} отправлен", "system")
                        found = True
                        break
                
                if not found:
                    file_socket.send(b'E')
                    
            elif cmd == 'U':
                name_len_data = self.recv_exact(file_socket, 4)
                if not name_len_data:
                    file_socket.close()
                    return
                name_len = struct.unpack('>I', name_len_data)[0]
                filename = self.recv_exact(file_socket, name_len).decode('utf-8')
                
                size_data = self.recv_exact(file_socket, 8)
                filesize = struct.unpack('>Q', size_data)[0]
                
                sender_len_data = self.recv_exact(file_socket, 4)
                if not sender_len_data:
                    file_socket.close()
                    return
                sender_len = struct.unpack('>I', sender_len_data)[0]
                sender = self.recv_exact(file_socket, sender_len).decode('utf-8')
                
                self.log(f"📥 Общий файл от {sender}: {filename} ({filesize/1024:.1f} KB)", "system")
                
                file_socket.send(b'K')
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
                base, ext = os.path.splitext(safe_filename)
                save_path = os.path.join(RECEIVED_FILES_DIR, f"{base}_{timestamp}{ext}")
                
                received = 0
                with open(save_path, 'wb') as f:
                    while received < filesize:
                        data = file_socket.recv(min(8192, filesize - received))
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                
                file_id = hashlib.md5(f"{filename}{timestamp}{sender}".encode()).hexdigest()[:8]
                file_info = {
                    'id': file_id,
                    'name': filename,
                    'path': save_path,
                    'size': filesize,
                    'sender': sender,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'chat': 'general'
                }
                self.files_list.append(file_info)
                self.save_history()
                
                self.log(f"✅ Файл сохранён: {save_path}", "system")
                
                self.broadcast("JSON_PAYLOAD:" + json.dumps({
                    "type": "file",
                    "data": {"sender": sender, "name": filename, "size": filesize, "id": file_id}
                }, ensure_ascii=True))
                
            elif cmd == 'V':
                target_len_data = self.recv_exact(file_socket, 4)
                if not target_len_data:
                    file_socket.close()
                    return
                target_len = struct.unpack('>I', target_len_data)[0]
                target = self.recv_exact(file_socket, target_len).decode('utf-8')
                
                name_len_data = self.recv_exact(file_socket, 4)
                if not name_len_data:
                    file_socket.close()
                    return
                name_len = struct.unpack('>I', name_len_data)[0]
                filename = self.recv_exact(file_socket, name_len).decode('utf-8')
                
                size_data = self.recv_exact(file_socket, 8)
                filesize = struct.unpack('>Q', size_data)[0]
                
                sender_len_data = self.recv_exact(file_socket, 4)
                if not sender_len_data:
                    file_socket.close()
                    return
                sender_len = struct.unpack('>I', sender_len_data)[0]
                sender = self.recv_exact(file_socket, sender_len).decode('utf-8')
                
                self.log(f"📥 Личный файл от {sender} для {target}: {filename} ({filesize/1024:.1f} KB)", "system")
                
                file_socket.send(b'K')
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
                base, ext = os.path.splitext(safe_filename)
                save_path = os.path.join(RECEIVED_FILES_DIR, f"{base}_{timestamp}{ext}")
                
                received = 0
                with open(save_path, 'wb') as f:
                    while received < filesize:
                        data = file_socket.recv(min(8192, filesize - received))
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                
                file_id = hashlib.md5(f"{filename}{timestamp}{sender}{target}".encode()).hexdigest()[:8]
                file_info = {
                    'id': file_id,
                    'name': filename,
                    'path': save_path,
                    'size': filesize,
                    'sender': sender,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'chat': target
                }
                self.files_list.append(file_info)
                self.save_history()
                
                self.log(f"✅ Личный файл сохранён: {save_path}", "system")
                
                target_socket = None
                for s, data in self.client_data.items():
                    if data['nickname'] == target:
                        target_socket = s
                        break
                
                payload = json.dumps({
                    "type": "private_file",
                    "target": target,
                    "data": {"sender": sender, "name": filename, "size": filesize, "id": file_id}
                }, ensure_ascii=True)
                
                if target_socket:
                    self.send_to_client(target_socket, "JSON_PAYLOAD:" + payload)
                self.send_to_client(client, "JSON_PAYLOAD:" + payload)
                
            file_socket.close()
                
        except Exception as e:
            self.log(f"❌ Ошибка файла от {addr}: {e}", "error")
            try:
                file_socket.close()
            except:
                pass
    
    def on_close(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    print(f"🚀 Запуск сервера v{ChatServer.VERSION}...")
    server = ChatServer()
    try:
        while server.running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Сервер остановлен")
        server.running = False