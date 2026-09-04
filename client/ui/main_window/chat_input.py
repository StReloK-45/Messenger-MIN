# client/ui/main_window/chat_input.py
import tkinter as tk
import threading
import socket
import struct
import os
from tkinter import filedialog

class ChatInput:
    def __init__(self, ui):
        self.ui = ui
        self.message_entry = None
    
    def setup(self, parent):
        """Создаёт поле ввода (только поле ввода, без кнопки эмодзи)"""
        input_frame = tk.Frame(parent, bg=self.ui.color_manager.get_color('chat_bg'), height=55)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        input_frame.pack_propagate(False)
        
        input_bg = tk.Frame(input_frame, bg=self.ui.color_manager.get_color('input_bg'))
        input_bg.pack(fill=tk.X, padx=15, pady=8)
        
        self.message_entry = tk.Entry(input_bg,
                                      font=("Segoe UI", self.ui.app.settings.font_size),
                                      bg=self.ui.color_manager.get_color('input_bg'),
                                      fg=self.ui.color_manager.get_color('text'),
                                      relief=tk.FLAT, bd=0,
                                      insertbackground=self.ui.color_manager.get_color('text'))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=2)
        self.message_entry.bind("<Return>", self.send_message)
        
        # Добавляем поддержку вставки через ПКМ
        self.message_entry.bind("<Button-3>", self.show_context_menu)
        
        tk.Button(input_bg, text="📎", font=("Segoe UI", 14),
                  bg=self.ui.color_manager.get_color('input_bg'), fg=self.ui.color_manager.get_color('text'),
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self.send_file).pack(side=tk.RIGHT, padx=(0, 5), pady=2)
        
        tk.Button(input_bg, text="📤", font=("Segoe UI", 14),
                  bg=self.ui.color_manager.get_color('accent'), fg='white',
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self.send_message).pack(side=tk.RIGHT, padx=(0, 5), pady=2)
    
    def show_context_menu(self, event):
        """Показывает контекстное меню для поля ввода"""
        menu = tk.Menu(self.ui.app.root, tearoff=0, bg='#3c3c3c', fg='white')
        menu.add_command(label="Вырезать", command=self.cut_text)
        menu.add_command(label="Копировать", command=self.copy_text)
        menu.add_command(label="Вставить", command=self.paste_text)
        menu.add_separator()
        menu.add_command(label="Выделить всё", command=self.select_all)
        menu.tk_popup(event.x_root, event.y_root)
    
    def cut_text(self):
        try:
            self.message_entry.event_generate("<<Cut>>")
        except:
            pass
    
    def copy_text(self):
        try:
            self.message_entry.event_generate("<<Copy>>")
        except:
            pass
    
    def paste_text(self):
        try:
            self.message_entry.event_generate("<<Paste>>")
        except:
            # Если не сработало, используем альтернативный метод
            try:
                text = self.ui.app.root.clipboard_get()
                self.message_entry.insert(tk.INSERT, text)
            except:
                pass
    
    def select_all(self):
        self.message_entry.select_range(0, tk.END)
        self.message_entry.focus()
    
    def add_emoji(self):
        """Открывает окно с выбором смайликов"""
        print("[DEBUG] add_emoji вызван в chat_input")
        
        if self.message_entry is None:
            print("[DEBUG] message_entry is None!")
            return
        
        emoji_window = tk.Toplevel(self.ui.app.root)
        emoji_window.title("Выберите смайлик")
        emoji_window.geometry("400x300")
        emoji_window.configure(bg=self.ui.color_manager.get_color('bg'))
        emoji_window.transient(self.ui.app.root)
        emoji_window.grab_set()
        
        emoji_window.update_idletasks()
        x = (emoji_window.winfo_screenwidth() // 2) - 200
        y = (emoji_window.winfo_screenheight() // 2) - 150
        emoji_window.geometry(f"+{x}+{y}")
        
        canvas = tk.Canvas(emoji_window, bg=self.ui.color_manager.get_color('bg'), highlightthickness=0)
        scrollbar = tk.Scrollbar(emoji_window, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.ui.color_manager.get_color('bg'))
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        emojis = [
            "😊", "😂", "❤️", "😍", "👍", "🔥", "🥲", "😭", "😎", "🤔",
            "😡", "🥺", "😱", "🎉", "✨", "💀", "🤣", "💯", "👀", "💔",
            "😈", "👋", "🤝", "🙏", "💪", "🍺", "🍻", "🎮", "💻", "🚀"
        ]
        
        row = 0
        col = 0
        entry = self.message_entry
        
        def insert(e):
            print(f"[DEBUG] Вставка смайлика: {e}")
            entry.insert(tk.INSERT, e)
            emoji_window.destroy()
        
        for emoji in emojis:
            btn = tk.Button(scrollable_frame, text=emoji, font=("Segoe UI Emoji", 16),
                           bg=self.ui.color_manager.get_color('bg'),
                           fg=self.ui.color_manager.get_color('text'),
                           relief=tk.FLAT, cursor="hand2",
                           command=lambda e=emoji: insert(e))
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            col += 1
            if col >= 8:
                col = 0
                row += 1
        
        for i in range(8):
            scrollable_frame.columnconfigure(i, weight=1)

    def send_message(self, event=None):
        text = self.message_entry.get().strip()
        if not text:
            return
        
        import time
        
        self.ui._last_msg_text = text
        self.ui._last_msg_time = time.time()
        
        if self.ui.current_chat == "general":
            self.ui.app.network.send(text)
        elif self.ui.current_chat_type == "private":
            self.ui.app.network.send_raw(f"CMD:PM|{self.ui.current_chat}|{text}")
        elif self.ui.current_chat_type == "group":
            self.ui.app.network.send_raw(f"CMD:GROUP_MSG|{self.ui.current_chat}|{text}")
        
        self.message_entry.delete(0, tk.END)
    
    def send_file(self):
        file_path = filedialog.askopenfilename(title="Выберите файл")
        if not file_path:
            return
        
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        
        if filesize > 250 * 1024 * 1024:
            self.ui.chat_display.add_system_message("❌ Файл слишком большой (макс 250MB)")
            return
        
        self.ui.chat_display.add_system_message(f"⏳ Отправка файла '{filename}'...")
        threading.Thread(target=self._upload_file, args=(file_path, filename, filesize), daemon=True).start()
    
    def _upload_file(self, file_path, filename, filesize):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(60)
            sock.connect((self.ui.app.settings.server_ip, self.ui.file_port))
            
            if self.ui.current_chat_type == "general":
                sock.send(b'U')
            elif self.ui.current_chat_type == "private":
                sock.send(b'V')
                target_bytes = self.ui.current_chat.encode('utf-8')
                sock.send(struct.pack('>I', len(target_bytes)))
                sock.send(target_bytes)
            elif self.ui.current_chat_type == "group":
                sock.send(b'G')
                group_bytes = self.ui.current_chat.encode('utf-8')
                sock.send(struct.pack('>I', len(group_bytes)))
                sock.send(group_bytes)
            
            name_bytes = filename.encode('utf-8')
            sock.send(struct.pack('>I', len(name_bytes)))
            sock.send(name_bytes)
            sock.send(struct.pack('>Q', filesize))
            sock.send(struct.pack('>I', len(self.ui.app.settings.nickname.encode('utf-8'))))
            sock.send(self.ui.app.settings.nickname.encode('utf-8'))
            
            response = sock.recv(1)
            if response != b'K':
                self.ui.app.root.after(0, lambda: self.ui.chat_display.add_system_message("❌ Сервер не принял файл"))
                sock.close()
                return
            
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(8192)
                    if not data:
                        break
                    sock.send(data)
            
            sock.close()
            self.ui.app.root.after(0, lambda: self.ui.chat_display.add_system_message(f"📤 Файл '{filename}' отправлен ({filesize/1024:.1f} KB)"))
        except Exception as e:
            self.ui.app.root.after(0, lambda: self.ui.chat_display.add_system_message(f"❌ Ошибка отправки: {e}"))