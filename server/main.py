# server/main.py
import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import json
from config import ChatConfig
from storage import Storage
from network import NetworkManager
from auth import AuthManager
from chat import ChatManager
from files import FileManager
from admin import AdminManager

class ChatServer:
    def __init__(self):
        self.config = ChatConfig()
        self.storage = Storage(self.config)
        self.network = NetworkManager(self)
        self.auth = AuthManager(self)
        self.chat = ChatManager(self)
        self.files = FileManager(self)
        self.admin = AdminManager(self)
        
        self.clients = []
        self.client_data = {}
        self.running = True
        
        # Создаём папки
        self.config.ensure_dirs()
        
        # Загружаем данные
        self.storage.load_all()
        
        # Запускаем GUI
        self.setup_gui()
        
        # Запускаем серверы
        self.network.start_servers()
        
        # Логируем запуск
        self.log("="*60, "system")
        self.log(f"🚀 СЕРВЕР ЧАТА ЗАПУЩЕН (v{self.config.VERSION})", "system")
        self.log(f"📂 Папка данных: {self.config.DATA_DIR}", "system")
        self.log(f"📍 IP адрес сервера: {self.config.get_local_ip()}", "system")
        self.log(f"💬 Чат сервер: {self.config.PORT}", "system")
        self.log(f"📁 Файловый сервер: {self.config.FILE_PORT}", "system")
        self.log("="*60, "system")
        self.log("💡 Введите /help для списка команд", "system")
        
        self.update_online_display()
        self.root.after(5000, self.periodic_update)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()
    
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title(f"💬 Чат Сервер v{self.config.VERSION}")
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
        
        # Центральная панель (логи)
        center_panel = tk.Frame(main_frame, bg=self.colors['bg'])
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        header = tk.Label(center_panel, text="📋 ЛОГИ СЕРВЕРА", font=("Segoe UI", 12, "bold"),
                          bg=self.colors['chat_bg'], fg='#4ec9b0', height=2)
        header.pack(fill=tk.X, pady=(0, 5))
        
        self.log_area = scrolledtext.ScrolledText(center_panel, wrap=tk.WORD, state='normal',
                                                   bg=self.colors['chat_bg'], fg=self.colors['text'],
                                                   font=("Consolas", 10), relief=tk.FLAT, borderwidth=0)
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        self.log_area.tag_config("time", foreground=self.colors['time'])
        self.log_area.tag_config("system", foreground=self.colors['system'])
        self.log_area.tag_config("server", foreground=self.colors['server'])
        self.log_area.tag_config("error", foreground=self.colors['error'])
        self.log_area.tag_config("online", foreground=self.colors['online'])
        self.log_area.tag_config("admin", foreground="#f48771", font=("Consolas", 10, "bold"))
        
        # Поле ввода команд
        input_frame = tk.Frame(center_panel, bg=self.colors['bg'])
        input_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.cmd_entry = tk.Entry(input_frame, font=("Consolas", 10), bg=self.colors['input_bg'],
                                   fg=self.colors['text'], relief=tk.FLAT, insertbackground=self.colors['text'])
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.cmd_entry.bind("<Return>", self.execute_command)
        
        tk.Button(input_frame, text="▶ Выполнить", command=self.execute_command,
                  bg=self.colors['button'], fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)
        
        btn_frame = tk.Frame(center_panel, bg=self.colors['bg'])
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        tk.Button(btn_frame, text="📢 Отправить в чат", command=self.send_system_message,
                  bg='#6a9955', fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(btn_frame, text="🔄 Обновить онлайн", command=self.update_online_display,
                  bg=self.colors['button'], fg="white", font=("Segoe UI", 9, "bold"),
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT)
        
        # Правая панель
        right_panel = tk.Frame(main_frame, bg=self.colors['sidebar'], width=280)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        tk.Label(right_panel, text="🟢 ОНЛАЙН", font=("Segoe UI", 11, "bold"),
                 bg=self.colors['sidebar'], fg='#4ec9b0').pack(pady=(10, 5))
        
        self.online_label = tk.Label(right_panel, text="Пользователей: 0", font=("Segoe UI", 9),
                                      bg=self.colors['sidebar'], fg='#6a9955')
        self.online_label.pack(pady=(0, 5))
        
        self.online_listbox = tk.Listbox(right_panel, bg=self.colors['chat_bg'], fg=self.colors['text'],
                                          font=("Segoe UI", 9), relief=tk.FLAT, selectbackground='#264f78',
                                          selectforeground='white', height=12)
        self.online_listbox.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(right_panel, text="🛡️ АДМИН КОМАНДЫ", font=("Segoe UI", 11, "bold"),
                 bg=self.colors['sidebar'], fg='#f48771').pack(pady=(10, 5))
        
        commands_text = tk.Text(right_panel, bg=self.colors['sidebar'], fg=self.colors['text'],
                                 font=("Segoe UI", 9), relief=tk.FLAT, borderwidth=0, height=15,
                                 cursor="arrow", wrap=tk.WORD)
        commands_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        commands_text.insert(tk.END, self.admin.get_help_text())
        commands_text.config(state='disabled')
    
    def log(self, text, tag="system"):
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{timestamp}] ", "time")
        self.log_area.insert(tk.END, f"{text}\n", tag)
        self.log_area.see(tk.END)
    
    def update_online_display(self):
        self.online_listbox.delete(0, tk.END)
        self.online_label.config(text=f"Пользователей: {len(self.clients)}")
        
        for client, data in self.client_data.items():
            nickname = data.get('nickname', 'Unknown')
            username = data.get('username', 'Unknown')
            muted = "🔇" if nickname in self.chat.muted_users else ""
            display = f"{muted} {nickname} (@{username})"
            self.online_listbox.insert(tk.END, display)
    
    def periodic_update(self):
        if self.running:
            self.update_online_display()
            self.root.after(5000, self.periodic_update)
    
    def send_system_message(self):
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
                self.network.broadcast("JSON_PAYLOAD:" + json.dumps({"type": "notification", "text": text}, ensure_ascii=False))
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
        
        command = parts[0]
        self.admin.execute(command, parts[1:] if len(parts) > 1 else [])
        self.root.after(0, self.update_online_display)
    
    def on_close(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    server = ChatServer()