import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog, Toplevel, Listbox, simpledialog, colorchooser
from datetime import datetime
import os
import re
import json
import time
import webbrowser
import base64
import hashlib
import struct

class ChatClient:
    VERSION = "0.43.6"
    
    def __init__(self):
        self.sock = None
        self.nickname = None
        self.username = None
        self.running = True
        self.server_ip = "192.168.0.155"
        self.chat_port = 5555
        self.file_port = 5556
        self.message_history = []
        self.private_messages = {}
        self.private_files = {}
        self.files_list = []
        self.config_file = "chat_config.ini"
        self.saved_username = ""
        self.saved_password = ""
        self.save_auth = False
        self.clicked_index = None
        self.nick_colors = {}
        self.custom_colors_file = "nick_colors.json"
        self.auth_window = None
        self.auth_success = False
        self.current_chat = "general"
        self.private_chats_list = set()
        
        print("=" * 50)
        print(f"🚀 ЗАПУСК КЛИЕНТА ЧАТА v{self.VERSION}")
        print("=" * 50)
        
        self.load_nick_colors()
        self.load_config()
        self.load_chats_list()
        self.ask_server_ip()
        
        if not self.connect_to_server():
            return
        
        if not self.authenticate():
            return
        
        self.setup_gui()
        
        self.root.after(1000, self.load_files_list)
        
        receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receive_thread.start()
        
        self.message_entry.focus()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()
    
    # ========== СОХРАНЕНИЕ ЧАТОВ ==========
    def load_chats_list(self):
        chats_file = "private_chats.json"
        if os.path.exists(chats_file):
            try:
                with open(chats_file, 'r', encoding='utf-8') as f:
                    self.private_chats_list = set(json.load(f))
                print(f"✅ Загружено {len(self.private_chats_list)} личных чатов")
            except:
                pass
    
    def save_chats_list(self):
        chats_file = "private_chats.json"
        try:
            with open(chats_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.private_chats_list), f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def load_private_messages(self, nick):
        pm_file = f"pm_{self.nickname}_{nick}.json"
        if os.path.exists(pm_file):
            try:
                with open(pm_file, 'r', encoding='utf-8') as f:
                    self.private_messages[nick] = json.load(f)
            except:
                self.private_messages[nick] = []
        else:
            self.private_messages[nick] = []
    
    def save_private_messages(self, nick):
        if nick in self.private_messages:
            pm_file = f"pm_{self.nickname}_{nick}.json"
            try:
                with open(pm_file, 'w', encoding='utf-8') as f:
                    json.dump(self.private_messages[nick], f, ensure_ascii=False, indent=2)
            except:
                pass
    
    # ========== ЦВЕТА НИКОВ ==========
    def load_nick_colors(self):
        if os.path.exists(self.custom_colors_file):
            try:
                with open(self.custom_colors_file, 'r', encoding='utf-8') as f:
                    self.nick_colors = json.load(f)
            except:
                pass
    
    def save_nick_colors(self):
        try:
            with open(self.custom_colors_file, 'w', encoding='utf-8') as f:
                json.dump(self.nick_colors, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def get_color_for_nick(self, nick):
        if nick not in self.nick_colors:
            hash_val = int(hashlib.md5(nick.encode()).hexdigest()[:6], 16)
            import colorsys
            hue = hash_val % 360
            r, g, b = colorsys.hls_to_rgb(hue/360.0, 0.5, 0.7)
            color = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
            self.nick_colors[nick] = color
        return self.nick_colors[nick]
    
    def set_nick_color(self, nick, color):
        self.nick_colors[nick] = color
        self.save_nick_colors()
        try:
            color_msg = f"CMD:COLOR|{color}\n"
            self.sock.send(color_msg.encode('utf-8'))
        except:
            pass
        self.root.after(0, self.refresh_chat_display)
    
    def change_my_color(self):
        current_color = self.nick_colors.get(self.nickname, '#4ec9b0')
        color = colorchooser.askcolor(title="Выберите цвет для вашего ника", initialcolor=current_color)
        if color and color[1]:
            self.set_nick_color(self.nickname, color[1])
            self.add_system_message(f"🎨 Цвет вашего ника изменён")
    
    # ========== КОНФИГУРАЦИЯ ==========
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.saved_username = data.get('username', '')
                    self.saved_password = data.get('password', '')
                    self.save_auth = data.get('save_auth', False)
            except:
                pass
    
    def save_config(self):
        if self.save_auth:
            data = {'username': self.username, 'password': self.saved_password, 'save_auth': True}
        else:
            data = {'username': '', 'password': '', 'save_auth': False}
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def encode_base64(self, text):
        return base64.b64encode(text.encode()).decode()
    
    def ask_server_ip(self):
        dialog = tk.Tk()
        dialog.title("Подключение к серверу")
        dialog.geometry("450x250")
        dialog.configure(bg='#1e1e1e')
        x = (dialog.winfo_screenwidth() // 2) - 225
        y = (dialog.winfo_screenheight() // 2) - 125
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="🌐 ПОДКЛЮЧЕНИЕ К СЕРВЕРУ", font=("Segoe UI", 14, "bold"), 
                 bg='#1e1e1e', fg='#4ec9b0').pack(pady=20)
        tk.Label(dialog, text="IP адрес сервера:", font=("Segoe UI", 11), 
                 bg='#1e1e1e', fg='#d4d4d4').pack()
        
        entry = tk.Entry(dialog, font=("Segoe UI", 11), bg='#3c3c3c', fg='#d4d4d4', 
                         relief=tk.FLAT, width=25, justify='center')
        entry.pack(pady=10)
        entry.insert(0, self.server_ip)
        entry.focus()
        
        result = {"ip": None}
        def submit():
            ip = entry.get().strip()
            if ip:
                result["ip"] = ip
                dialog.destroy()
        
        entry.bind("<Return>", lambda e: submit())
        tk.Button(dialog, text="Подключиться →", command=submit, bg='#0e639c', fg="white", 
                  font=("Segoe UI", 11, "bold"), relief=tk.FLAT, cursor="hand2", 
                  padx=20, pady=5).pack(pady=20)
        
        dialog.mainloop()
        if result["ip"]:
            self.server_ip = result["ip"]
    
    def connect_to_server(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.server_ip, self.chat_port))
            print(f"✅ Подключен к чат-серверу {self.server_ip}:{self.chat_port}")
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подключиться: {e}")
            return False
    
    def authenticate(self):
        try:
            response = self.sock.recv(1024).decode('utf-8').strip()
            
            if response == "BANNED":
                messagebox.showerror("БАН", "Вы забанены на этом сервере!")
                return False
            if response != "AUTH_REQUIRED":
                messagebox.showerror("Ошибка", "Неожиданный ответ от сервера")
                return False
            
            self.auth_window = tk.Toplevel()
            self.auth_window.title("Авторизация")
            self.auth_window.geometry("400x580")
            self.auth_window.configure(bg='#1e1e1e')
            self.auth_window.transient()
            self.auth_window.grab_set()
            
            x = (self.auth_window.winfo_screenwidth() // 2) - 200
            y = (self.auth_window.winfo_screenheight() // 2) - 290
            self.auth_window.geometry(f"+{x}+{y}")
            
            self.auth_window.protocol("WM_DELETE_WINDOW", self.on_auth_close)
            
            tk.Label(self.auth_window, text="🔐 АВТОРИЗАЦИЯ", font=("Segoe UI", 14, "bold"), 
                     bg='#1e1e1e', fg='#4ec9b0').pack(pady=20)
            
            self.remember_var = tk.BooleanVar(value=self.save_auth)
            self.status_label = tk.Label(self.auth_window, text="", bg='#1e1e1e', fg='#f48771', font=("Segoe UI", 9))
            self.status_label.pack(pady=5)
            
            self.auth_frame = tk.Frame(self.auth_window, bg='#1e1e1e')
            self.auth_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
            
            self.show_login()
            
            self.auth_window.wait_window()
            return self.auth_success
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка авторизации: {e}")
            return False
    
    def on_auth_close(self):
        self.auth_success = False
        if self.auth_window:
            self.auth_window.destroy()
    
    def set_status(self, text, is_error=True):
        self.status_label.config(text=text, fg='#f48771' if is_error else '#6a9955')
        self.auth_window.update()
    
    def clear_frame(self):
        for widget in self.auth_frame.winfo_children():
            widget.destroy()
    
    def show_login(self):
        self.clear_frame()
        self.set_status("", False)
        
        tk.Label(self.auth_frame, text="Логин:", bg='#1e1e1e', fg='#d4d4d4', font=("Segoe UI", 10)).pack(pady=(10, 5))
        login_entry = tk.Entry(self.auth_frame, bg='#3c3c3c', fg='white', font=("Segoe UI", 10), width=30)
        login_entry.pack(pady=5)
        if self.saved_username:
            login_entry.insert(0, self.saved_username)
        
        tk.Label(self.auth_frame, text="Пароль:", bg='#1e1e1e', fg='#d4d4d4', font=("Segoe UI", 10)).pack(pady=(10, 5))
        pass_entry = tk.Entry(self.auth_frame, bg='#3c3c3c', fg='white', font=("Segoe UI", 10), width=30, show="*")
        pass_entry.pack(pady=5)
        if self.saved_password and self.save_auth:
            pass_entry.insert(0, self.saved_password)
        
        remember_cb = tk.Checkbutton(self.auth_frame, text="Запомнить меня", variable=self.remember_var, 
                                     bg='#1e1e1e', fg='#d4d4d4', selectcolor='#1e1e1e',
                                     activebackground='#1e1e1e', activeforeground='#d4d4d4')
        remember_cb.pack(pady=(10, 5))
        
        def do_login():
            username = login_entry.get().strip()
            password = pass_entry.get().strip()
            if not username or not password:
                self.set_status("❌ Заполните все поля")
                return
            
            self.set_status("⏳ Подключение...", False)
            
            try:
                encoded_password = base64.b64encode(password.encode()).decode()
                auth_string = f"LOGIN|{username}|{encoded_password}\n"
                self.sock.send(auth_string.encode('utf-8'))
                
                self.sock.settimeout(15)
                response = self.sock.recv(4096).decode('utf-8').strip()
                self.sock.settimeout(None)
                
                if response.startswith("AUTH_SUCCESS"):
                    parts = response.split('|')
                    self.nickname = parts[1]
                    self.username = parts[2] if len(parts) > 2 else username
                    self.saved_password = password if self.remember_var.get() else ""
                    self.save_auth = self.remember_var.get()
                    self.save_config()
                    self.auth_success = True
                    self.auth_window.destroy()
                elif response.startswith("AUTH_FAIL"):
                    error = response.split('|')[1] if '|' in response else "Неизвестная ошибка"
                    self.set_status(error)
                else:
                    self.set_status(f"❌ Неизвестный ответ сервера")
                    
            except socket.timeout:
                self.set_status("❌ Таймаут подключения.")
            except Exception as e:
                self.set_status(f"❌ Ошибка: {str(e)[:50]}")
        
        btn_frame = tk.Frame(self.auth_frame, bg='#1e1e1e')
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Войти", command=do_login, bg='#0e639c', fg='white', 
                  font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2", width=15).pack(pady=5)
        
        tk.Button(self.auth_frame, text="Нет аккаунта? Зарегистрироваться", command=self.show_register,
                  bg='#1e1e1e', fg='#569cd6', font=("Segoe UI", 9), relief=tk.FLAT, cursor="hand2").pack()
        
        tk.Button(self.auth_frame, text="🔑 Забыли пароль?", command=self.forgot_password,
                  bg='#1e1e1e', fg='#ce9178', font=("Segoe UI", 9), relief=tk.FLAT, cursor="hand2").pack(pady=(5, 0))
        
        login_entry.focus()
        pass_entry.bind("<Return>", lambda e: do_login())
    
    def forgot_password(self):
        username = simpledialog.askstring("Восстановление пароля", "Введите ваш логин:")
        if not username:
            return
        
        try:
            self.sock.send(f"CMD:FORGOT|{username}\n".encode('utf-8'))
            self.set_status("⏳ Запрос отправлен...", False)
            
            self.sock.settimeout(10)
            response = self.sock.recv(1024).decode('utf-8').strip()
            self.sock.settimeout(None)
            
            if response.startswith("RECOVERY_CODE:"):
                code = response.split(':')[1]
                messagebox.showinfo("Код восстановления", 
                    f"Код восстановления отправлен администратору.\n"
                    f"Свяжитесь с администратором и сообщите ему:\n"
                    f"Логин: {username}\n"
                    f"Код: {code}")
            elif response == "USER_NOT_FOUND":
                messagebox.showerror("Ошибка", "Пользователь с таким логином не найден")
            else:
                messagebox.showerror("Ошибка", "Не удалось отправить запрос")
                
        except socket.timeout:
            messagebox.showerror("Ошибка", "Сервер не отвечает")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
        finally:
            self.sock.settimeout(None)
    
    def show_register(self):
        self.clear_frame()
        self.set_status("", False)
        
        tk.Label(self.auth_frame, text="Логин (от 3 до 20 символов):", bg='#1e1e1e', fg='#d4d4d4', font=("Segoe UI", 10)).pack(pady=(10, 5))
        login_entry = tk.Entry(self.auth_frame, bg='#3c3c3c', fg='white', font=("Segoe UI", 10), width=30)
        login_entry.pack(pady=5)
        
        tk.Label(self.auth_frame, text="Пароль (минимум 4 символа):", bg='#1e1e1e', fg='#d4d4d4', font=("Segoe UI", 10)).pack(pady=(10, 5))
        pass_entry = tk.Entry(self.auth_frame, bg='#3c3c3c', fg='white', font=("Segoe UI", 10), width=30, show="*")
        pass_entry.pack(pady=5)
        
        tk.Label(self.auth_frame, text="Отображаемое имя (никнейм):", bg='#1e1e1e', fg='#d4d4d4', font=("Segoe UI", 10)).pack(pady=(10, 5))
        nick_entry = tk.Entry(self.auth_frame, bg='#3c3c3c', fg='white', font=("Segoe UI", 10), width=30)
        nick_entry.pack(pady=5)
        
        remember_cb = tk.Checkbutton(self.auth_frame, text="Запомнить меня", variable=self.remember_var,
                                     bg='#1e1e1e', fg='#d4d4d4', selectcolor='#1e1e1e',
                                     activebackground='#1e1e1e', activeforeground='#d4d4d4')
        remember_cb.pack(pady=(10, 5))
        
        def do_register():
            username = login_entry.get().strip()
            password = pass_entry.get().strip()
            nickname = nick_entry.get().strip()
            
            if not username or not password:
                self.set_status("❌ Заполните логин и пароль")
                return
            if len(username) < 3:
                self.set_status("❌ Логин должен быть от 3 символов")
                return
            if len(username) > 20:
                self.set_status("❌ Логин должен быть до 20 символов")
                return
            if len(password) < 4:
                self.set_status("❌ Пароль должен быть от 4 символов")
                return
            if not nickname:
                nickname = username
            
            self.set_status("⏳ Регистрация...", False)
            
            try:
                encoded_password = base64.b64encode(password.encode()).decode()
                auth_string = f"REGISTER|{username}|{encoded_password}|{nickname}\n"
                self.sock.send(auth_string.encode('utf-8'))
                
                self.sock.settimeout(15)
                response = self.sock.recv(4096).decode('utf-8').strip()
                self.sock.settimeout(None)
                
                if response.startswith("AUTH_SUCCESS"):
                    parts = response.split('|')
                    self.nickname = parts[1]
                    self.username = parts[2] if len(parts) > 2 else username
                    self.saved_password = password if self.remember_var.get() else ""
                    self.save_auth = self.remember_var.get()
                    self.save_config()
                    self.auth_success = True
                    self.auth_window.destroy()
                elif response.startswith("AUTH_FAIL"):
                    error = response.split('|')[1] if '|' in response else "Неизвестная ошибка"
                    self.set_status(error)
                else:
                    self.set_status(f"❌ Неизвестный ответ сервера")
                    
            except socket.timeout:
                self.set_status("❌ Таймаут подключения.")
            except Exception as e:
                self.set_status(f"❌ Ошибка: {str(e)[:50]}")
        
        btn_frame = tk.Frame(self.auth_frame, bg='#1e1e1e')
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Зарегистрироваться", command=do_register, bg='#6a9955', fg='white',
                  font=("Segoe UI", 10, "bold"), relief=tk.FLAT, cursor="hand2", width=20).pack(pady=5)
        
        tk.Button(self.auth_frame, text="Уже есть аккаунт? Войти", command=self.show_login,
                  bg='#1e1e1e', fg='#569cd6', font=("Segoe UI", 9), relief=tk.FLAT, cursor="hand2").pack()
        
        login_entry.focus()
        pass_entry.bind("<Return>", lambda e: do_register())
    
    # ========== ФАЙЛОВЫЕ ФУНКЦИИ ==========
    def recv_exact(self, sock, size):
        data = b''
        while len(data) < size:
            try:
                packet = sock.recv(size - len(data))
                if not packet:
                    return None
                data += packet
            except:
                return None
        return data
    
    def load_files_list(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.server_ip, self.file_port))
            
            if self.current_chat == "general":
                sock.send(b'L')
            else:
                sock.send(b'P')
                nick_bytes = self.current_chat.encode('utf-8')
                sock.send(struct.pack('>I', len(nick_bytes)))
                sock.send(nick_bytes)
            
            size_data = self.recv_exact(sock, 4)
            if not size_data:
                sock.close()
                return
            size = struct.unpack('>I', size_data)[0]
            
            data = self.recv_exact(sock, size)
            if not data:
                sock.close()
                return
            
            data_str = data.decode('utf-8', errors='ignore')
            sock.close()
            
            try:
                files = json.loads(data_str)
                if self.current_chat == "general":
                    self.files_list = files
                else:
                    self.private_files[self.current_chat] = files
            except:
                pass
            
            self.root.after(0, self.update_files_listbox)
            
        except Exception as e:
            print(f"Ошибка загрузки файлов: {e}")
    
    def update_files_listbox(self):
        if hasattr(self, 'files_listbox'):
            self.files_listbox.delete(0, tk.END)
            
            if self.current_chat == "general":
                files = self.files_list
            else:
                files = self.private_files.get(self.current_chat, [])
            
            if not files:
                self.files_listbox.insert(tk.END, "📁 Нет файлов")
            else:
                for f in files:
                    try:
                        size_kb = f.get('size', 0) / 1024
                        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
                        name = f.get('name', 'unknown')
                        sender = f.get('sender', 'unknown')
                        display_text = f"📁 {name} ({size_str}) - {sender}"
                        self.files_listbox.insert(tk.END, display_text)
                    except:
                        pass
    
    def download_selected_file(self):
        selection = self.files_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        
        if self.current_chat == "general":
            files = self.files_list
        else:
            files = self.private_files.get(self.current_chat, [])
        
        if idx >= len(files):
            return
        
        file_info = files[idx]
        if messagebox.askyesno("Скачать файл", f"Скачать файл '{file_info.get('name', 'file')}'?"):
            threading.Thread(target=self.download_file, args=(file_info['id'], file_info['name']), daemon=True).start()
    
    def download_file(self, file_id, filename):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(60)
            sock.connect((self.server_ip, self.file_port))
            
            sock.send(b'D')
            
            id_bytes = file_id.encode('utf-8')
            sock.send(struct.pack('>I', len(id_bytes)))
            sock.send(id_bytes)
            
            response = sock.recv(1)
            if response != b'K':
                self.root.after(0, lambda: self.add_system_message("❌ Файл не найден"))
                sock.close()
                return
            
            size_data = self.recv_exact(sock, 8)
            filesize = struct.unpack('>Q', size_data)[0]
            
            name_len_data = self.recv_exact(sock, 4)
            name_len = struct.unpack('>I', name_len_data)[0]
            
            received_filename = self.recv_exact(sock, name_len).decode('utf-8')
            
            self.root.after(0, lambda: self.ask_save_location(received_filename, filesize, sock))
        except Exception as e:
            self.root.after(0, lambda: self.add_system_message(f"❌ Ошибка скачивания: {e}"))
    
    def ask_save_location(self, filename, filesize, sock):
        save_path = filedialog.asksaveasfilename(title="Сохранить файл", initialfile=filename)
        if save_path:
            threading.Thread(target=self.save_file_data, args=(save_path, filesize, sock), daemon=True).start()
        else:
            sock.close()
    
    def save_file_data(self, save_path, filesize, sock):
        try:
            with open(save_path, 'wb') as f:
                received = 0
                while received < filesize:
                    data = sock.recv(min(8192, filesize - received))
                    if not data:
                        break
                    f.write(data)
                    received += len(data)
            sock.close()
            self.root.after(0, lambda: self.add_system_message(f"✅ Файл сохранён: {os.path.basename(save_path)}"))
        except Exception as e:
            sock.close()
            self.root.after(0, lambda: self.add_system_message(f"❌ Ошибка сохранения: {e}"))
    
    def send_file(self):
        file_path = filedialog.askopenfilename(title="Выберите файл")
        if not file_path:
            return
        
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        
        if filesize > 100 * 1024 * 1024:
            self.add_system_message("❌ Файл слишком большой (макс 100MB)")
            return
        
        self.add_system_message(f"⏳ Отправка файла '{filename}'...")
        threading.Thread(target=self.upload_file, args=(file_path, filename, filesize), daemon=True).start()
    
    def upload_file(self, file_path, filename, filesize):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(60)
            sock.connect((self.server_ip, self.file_port))
            
            if self.current_chat == "general":
                sock.send(b'U')
            else:
                sock.send(b'V')
                target_bytes = self.current_chat.encode('utf-8')
                sock.send(struct.pack('>I', len(target_bytes)))
                sock.send(target_bytes)
            
            name_bytes = filename.encode('utf-8')
            sock.send(struct.pack('>I', len(name_bytes)))
            sock.send(name_bytes)
            
            sock.send(struct.pack('>Q', filesize))
            
            sender_bytes = self.nickname.encode('utf-8')
            sock.send(struct.pack('>I', len(sender_bytes)))
            sock.send(sender_bytes)
            
            response = sock.recv(1)
            if response != b'K':
                self.root.after(0, lambda: self.add_system_message("❌ Сервер не принял файл"))
                sock.close()
                return
            
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(8192)
                    if not data:
                        break
                    sock.send(data)
            
            sock.close()
            self.root.after(0, lambda: self.add_system_message(f"📤 Файл '{filename}' отправлен ({filesize/1024:.1f} KB)"))
            
        except Exception as e:
            self.root.after(0, lambda: self.add_system_message(f"❌ Ошибка отправки: {e}"))
    
    # ========== GUI ==========
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title(f"💬 Чат - {self.nickname} v{self.VERSION}")
        self.root.geometry("1100x700")
        self.root.configure(bg='#1e1e1e')
        
        self.colors = {
            'bg': '#1e1e1e', 'sidebar': '#252525', 'chat_bg': '#2d2d2d', 
            'input_bg': '#3c3c3c', 'text': '#d4d4d4', 'time': '#6a9955', 
            'server': '#dcdcaa', 'system': '#c586c0', 'error': '#f48771', 
            'button': '#0e639c', 'file_button': '#6a9955', 'color_button': '#9c3e9c'
        }
        
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ========== ЛЕВАЯ ПАНЕЛЬ (ЧАТЫ) ==========
        left_panel = tk.Frame(main_frame, bg=self.colors['sidebar'], width=220)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        tk.Label(left_panel, text="💬 ЧАТЫ", font=("Segoe UI", 11, "bold"), 
                 bg=self.colors['sidebar'], fg='#4ec9b0').pack(pady=(10, 5))
        
        self.chats_listbox = Listbox(left_panel, bg=self.colors['chat_bg'], fg=self.colors['text'], 
                                      font=("Segoe UI", 10), relief=tk.FLAT, selectbackground='#264f78',
                                      selectforeground='white', height=15)
        self.chats_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.chats_listbox.bind('<<ListboxSelect>>', self.on_chat_select)
        
        chat_buttons_frame = tk.Frame(left_panel, bg=self.colors['sidebar'])
        chat_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(chat_buttons_frame, text="🎨 Цвет ника", command=self.change_my_color,
                  bg=self.colors['color_button'], fg="white", font=("Segoe UI", 9), 
                  relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=2)
        
        tk.Button(chat_buttons_frame, text="🔄 Обновить", command=self.load_files_list,
                  bg=self.colors['button'], fg="white", font=("Segoe UI", 9), 
                  relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, pady=2)
        
        # ========== ЦЕНТРАЛЬНАЯ ПАНЕЛЬ ==========
        center_panel = tk.Frame(main_frame, bg=self.colors['bg'])
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.chat_header = tk.Label(center_panel, text="💬 ОБЩИЙ ЧАТ", font=("Segoe UI", 12, "bold"),
                                     bg=self.colors['chat_bg'], fg='#4ec9b0', height=2)
        self.chat_header.pack(fill=tk.X, pady=(0, 5))
        
        self.chat_area = scrolledtext.ScrolledText(center_panel, wrap=tk.WORD, state='normal', 
                                                    bg=self.colors['chat_bg'], fg=self.colors['text'], 
                                                    font=("Segoe UI", 10), relief=tk.FLAT, borderwidth=0, 
                                                    highlightthickness=0, selectbackground='#264f78', 
                                                    selectforeground='white')
        self.chat_area.pack(fill=tk.BOTH, expand=True)
        
        self.chat_area.tag_config("time", foreground=self.colors['time'], font=("Segoe UI", 8))
        self.chat_area.tag_config("server", foreground=self.colors['server'], font=("Segoe UI", 10, "bold"))
        self.chat_area.tag_config("system", foreground=self.colors['system'], font=("Segoe UI", 10, "italic"))
        self.chat_area.tag_config("error", foreground=self.colors['error'], font=("Segoe UI", 10, "bold"))
        
        self.chat_area.tag_config("link", foreground="#569cd6", underline=True)
        self.chat_area.tag_bind("link", "<Button-1>", self.open_link)
        self.chat_area.tag_bind("link", "<Enter>", lambda e: self.chat_area.config(cursor="hand2"))
        self.chat_area.tag_bind("link", "<Leave>", lambda e: self.chat_area.config(cursor=""))
        
        input_frame = tk.Frame(center_panel, bg=self.colors['bg'])
        input_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.message_entry = tk.Entry(input_frame, font=("Segoe UI", 10), bg=self.colors['input_bg'], 
                                       fg=self.colors['text'], relief=tk.FLAT, insertbackground=self.colors['text'])
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.message_entry.bind("<Return>", self.send_message)
        
        # Правильная привязка вставки
        self.message_entry.bind("<Control-v>", self.paste_text)
        self.message_entry.bind("<Control-V>", self.paste_text)
        self.message_entry.bind("<<Paste>>", self.paste_text)
        
        button_frame = tk.Frame(center_panel, bg=self.colors['bg'])
        button_frame.pack(fill=tk.X, pady=(5, 0))
        
        tk.Button(button_frame, text="📎 Файл", command=self.send_file,
                  bg=self.colors['file_button'], fg="white", font=("Segoe UI", 9, "bold"), 
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT, padx=(0, 5))
        
        tk.Button(button_frame, text="📜 История", command=self.show_full_history,
                  bg=self.colors['button'], fg="white", font=("Segoe UI", 9, "bold"), 
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.LEFT)
        
        tk.Button(button_frame, text="📤 Отправить", command=self.send_message,
                  bg=self.colors['button'], fg="white", font=("Segoe UI", 9, "bold"), 
                  relief=tk.FLAT, cursor="hand2").pack(side=tk.RIGHT)
        
        # ========== ПРАВАЯ ПАНЕЛЬ (ФАЙЛЫ) ==========
        right_panel = tk.Frame(main_frame, bg=self.colors['sidebar'], width=250)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        tk.Label(right_panel, text="📁 ФАЙЛЫ", font=("Segoe UI", 11, "bold"), 
                 bg=self.colors['sidebar'], fg='#4ec9b0').pack(pady=(10, 5))
        
        self.files_listbox = Listbox(right_panel, bg=self.colors['chat_bg'], fg=self.colors['text'], 
                                      font=("Segoe UI", 9), relief=tk.FLAT, selectbackground='#264f78', 
                                      selectforeground='white', height=25)
        self.files_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Button(right_panel, text="⬇️ Скачать", command=self.download_selected_file,
                  bg=self.colors['file_button'], fg="white", font=("Segoe UI", 10, "bold"), 
                  relief=tk.FLAT, cursor="hand2").pack(fill=tk.X, padx=5, pady=5)
        
        self.chat_context_menu = tk.Menu(self.root, tearoff=0, bg='#3c3c3c', fg='white', activebackground='#0e639c')
        self.chat_context_menu.add_command(label="📋 Копировать", command=self.copy_from_chat)
        self.chat_context_menu.add_command(label="✏️ Редактировать", command=self.edit_selected_message)
        self.chat_context_menu.add_command(label="💬 Личное сообщение", command=self.start_private_chat)
        self.chat_area.bind("<Button-3>", self.show_chat_context_menu)
        
        # Контекстное меню для поля ввода
        self.entry_context_menu = tk.Menu(self.root, tearoff=0, bg='#3c3c3c', fg='white', activebackground='#0e639c')
        self.entry_context_menu.add_command(label="📋 Вставить", command=self.paste_text)
        self.entry_context_menu.add_command(label="📋 Копировать", command=self.copy_from_entry)
        self.entry_context_menu.add_command(label="✂️ Вырезать", command=self.cut_from_entry)
        self.message_entry.bind("<Button-3>", self.show_entry_context_menu)
        
        self.update_chats_list()
    
    def show_entry_context_menu(self, event):
        try:
            self.entry_context_menu.post(event.x_root, event.y_root)
        except:
            pass
    
    def copy_from_entry(self):
        try:
            selected = self.message_entry.selection_get()
            if selected:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
        except:
            # Если нет выделения, копируем всё
            text = self.message_entry.get()
            if text:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
    
    def cut_from_entry(self):
        try:
            selected = self.message_entry.selection_get()
            if selected:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.message_entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
        except:
            pass
    
    def update_chats_list(self):
        self.chats_listbox.delete(0, tk.END)
        self.chats_listbox.insert(tk.END, "💬 ОБЩИЙ ЧАТ")
        
        if self.current_chat == "general":
            self.chats_listbox.itemconfig(0, {'bg': '#264f78', 'fg': 'white'})
        else:
            self.chats_listbox.itemconfig(0, {'bg': self.colors['chat_bg'], 'fg': 'white'})
        
        idx = 1
        for nick in sorted(self.private_chats_list):
            if nick != self.nickname:
                display = f"👤 {nick}"
                self.chats_listbox.insert(tk.END, display)
                if self.current_chat == nick:
                    self.chats_listbox.itemconfig(idx, {'bg': '#264f78', 'fg': 'white'})
                idx += 1
    
    def on_chat_select(self, event):
        selection = self.chats_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        if idx == 0:
            self.current_chat = "general"
            self.chat_header.config(text="💬 ОБЩИЙ ЧАТ")
        else:
            nick = self.chats_listbox.get(idx).replace("👤 ", "")
            self.current_chat = nick
            self.chat_header.config(text=f"💬 ЛИЧНЫЕ СООБЩЕНИЯ С {nick}")
            if nick not in self.private_messages:
                self.load_private_messages(nick)
            self.sock.send(f"CMD:GET_PM_HISTORY|{nick}\n".encode('utf-8'))
        
        self.update_chats_list()
        self.refresh_chat_display()
        self.load_files_list()
    
    def start_private_chat(self, target=None):
        if target is None:
            try:
                line_start = self.chat_area.index(f"{self.clicked_index} linestart")
                line_text = self.chat_area.get(line_start, f"{self.clicked_index} lineend")
                if "👤" in line_text:
                    target = line_text.split("👤")[1].split(":")[0].strip()
            except:
                pass
        
        if target and target != self.nickname:
            if target not in self.private_chats_list:
                self.private_chats_list.add(target)
                self.save_chats_list()
                self.private_messages[target] = []
                self.private_files[target] = []
                self.update_chats_list()
            
            for i in range(self.chats_listbox.size()):
                if self.chats_listbox.get(i) == f"👤 {target}":
                    self.chats_listbox.selection_clear(0, tk.END)
                    self.chats_listbox.selection_set(i)
                    self.chats_listbox.activate(i)
                    self.on_chat_select(None)
                    break
    
    def edit_selected_message(self):
        try:
            line_start = self.chat_area.index(f"{self.clicked_index} linestart")
            line_text = self.chat_area.get(line_start, f"{self.clicked_index} lineend")
            
            for tag in self.chat_area.tag_names(self.clicked_index):
                if tag.startswith("msg_id:"):
                    msg_id = tag.split(":")[1]
                    current_text = line_text.split(":", 1)[-1].strip()
                    if "(ред.)" in current_text:
                        current_text = current_text.replace("(ред.)", "").strip()
                    
                    new_text = simpledialog.askstring("Редактирование", "Новый текст:", initialvalue=current_text)
                    if new_text and new_text != current_text:
                        self.sock.send(f"CMD:EDIT|{msg_id}|{new_text}\n".encode('utf-8'))
                    return
        except:
            pass
    
    def show_chat_context_menu(self, event):
        try:
            self.clicked_index = self.chat_area.index(f"@{event.x},{event.y}")
            self.chat_context_menu.post(event.x_root, event.y_root)
        except:
            pass
    
    def copy_from_chat(self):
        try:
            selected = self.chat_area.selection_get()
            if selected:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
        except:
            pass
    
    def paste_text(self, event=None):
        """Вставка текста из буфера обмена"""
        try:
            clipboard_text = self.root.clipboard_get()
            if clipboard_text:
                # Удаляем возможные переводы строк в конце
                clipboard_text = clipboard_text.rstrip('\n\r')
                cursor_pos = self.message_entry.index(tk.INSERT)
                self.message_entry.insert(cursor_pos, clipboard_text)
        except:
            pass
        return "break"  # Предотвращаем двойную вставку
    
    def open_link(self, event):
        index = self.chat_area.index(f"@{event.x},{event.y}")
        for tag in self.chat_area.tag_names(index):
            if tag.startswith("url:"):
                webbrowser.open(tag[4:])
                break
    
    def insert_message_with_links(self, text, tag_name, time_str=None):
        if time_str:
            self.chat_area.insert(tk.END, f"[{time_str}] ", "time")
        
        url_pattern = r'(https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+)'
        last_end = 0
        
        for match in re.finditer(url_pattern, text):
            if match.start() > last_end:
                self.chat_area.insert(tk.END, text[last_end:match.start()], tag_name)
            
            url = match.group(0)
            full_url = url if url.startswith('http') else 'http://' + url
            
            tag_url = f"url:{full_url}"
            self.chat_area.tag_config(tag_url, foreground="#569cd6", underline=True)
            self.chat_area.tag_bind(tag_url, "<Button-1>", lambda e, u=full_url: webbrowser.open(u))
            self.chat_area.tag_bind(tag_url, "<Enter>", lambda e: self.chat_area.config(cursor="hand2"))
            self.chat_area.tag_bind(tag_url, "<Leave>", lambda e: self.chat_area.config(cursor=""))
            
            self.chat_area.insert(tk.END, url, tag_url)
            last_end = match.end()
        
        if last_end < len(text):
            self.chat_area.insert(tk.END, text[last_end:], tag_name)
        
        self.chat_area.insert(tk.END, "\n")
    
    def show_full_history(self):
        history_window = Toplevel(self.root)
        history_window.title("📜 Полная история общего чата")
        history_window.geometry("800x600")
        history_window.configure(bg='#1e1e1e')
        
        history_text = tk.Text(history_window, wrap=tk.WORD, font=("Segoe UI", 10), bg='#2d2d2d', 
                               fg='#d4d4d4', relief=tk.FLAT, selectbackground='#264f78', selectforeground='white')
        history_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(history_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        history_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=history_text.yview)
        
        for nick, color in self.nick_colors.items():
            history_text.tag_config(f"nick_{nick}", foreground=color, font=("Segoe UI", 10, "bold"))
        
        history_text.tag_config("server", foreground="#dcdcaa")
        history_text.tag_config("system", foreground="#c586c0")
        
        history_text.insert(tk.END, f"\n{'='*80}\n", "system")
        history_text.insert(tk.END, f"  📜 ПОЛНАЯ ИСТОРИЯ ОБЩЕГО ЧАТА\n", "system")
        history_text.insert(tk.END, f"  Всего сообщений: {len(self.message_history)}\n", "system")
        history_text.insert(tk.END, f"{'='*80}\n\n", "system")
        
        for msg in self.message_history:
            sender = msg.get('sender', '')
            text = msg.get('text', '')
            msg_time = msg.get('time', '')
            edited = msg.get('edited', False)
            edit_mark = " (ред.)" if edited else ""
            
            if sender == "СЕРВЕР":
                history_text.insert(tk.END, f"[{msg_time}] 🔔 {text}{edit_mark}\n", "server")
            elif sender == "ФАЙЛ":
                history_text.insert(tk.END, f"[{msg_time}] 📁 {text}{edit_mark}\n", "server")
            else:
                tag = f"nick_{sender}" if f"nick_{sender}" in history_text.tag_names() else "system"
                history_text.insert(tk.END, f"[{msg_time}] 👤 {sender}: {text}{edit_mark}\n", tag)
        
        history_text.see(tk.END)
        history_text.config(state='disabled')
    
    # ========== ОТОБРАЖЕНИЕ СООБЩЕНИЙ ==========
    def refresh_chat_display(self):
        self.chat_area.delete(1.0, tk.END)
        
        if self.current_chat == "general":
            for msg in self.message_history:
                self.display_message(msg)
        else:
            for msg in self.private_messages.get(self.current_chat, []):
                self.display_private_message(msg, self.current_chat)
    
    def display_message(self, msg):
        sender = msg.get('sender', '')
        text = msg.get('text', '')
        msg_time = msg.get('time', '')
        edited = msg.get('edited', False)
        edit_mark = " (ред.)" if edited else ""
        msg_id = msg.get('id', '')
        
        start_pos = self.chat_area.index("end-1c")
        
        if sender == "СЕРВЕР":
            self.chat_area.insert(tk.END, f"[{msg_time}] ", "time")
            self.chat_area.insert(tk.END, f"🔔 {text}{edit_mark}\n", "server")
        elif sender == "ФАЙЛ":
            self.chat_area.insert(tk.END, f"[{msg_time}] ", "time")
            self.chat_area.insert(tk.END, f"📁 {text}{edit_mark}\n", "server")
        else:
            self.chat_area.insert(tk.END, f"[{msg_time}] ", "time")
            color = self.get_color_for_nick(sender)
            self.chat_area.tag_config(f"nick_{sender}", foreground=color, font=("Segoe UI", 10, "bold"))
            self.chat_area.insert(tk.END, f"👤 {sender}: ", f"nick_{sender}")
            self.insert_message_with_links(f"{text}{edit_mark}", f"nick_{sender}")
        
        if msg_id:
            end_pos = self.chat_area.index("end-1c")
            self.chat_area.tag_add(f"msg_id:{msg_id}", start_pos, end_pos)
        
        self.chat_area.see(tk.END)
    
    def display_private_message(self, msg, partner):
        sender = msg.get('sender', '')
        text = msg.get('text', '')
        msg_time = msg.get('time', '')
        
        self.chat_area.insert(tk.END, f"[{msg_time}] ", "time")
        
        color = self.get_color_for_nick(sender)
        self.chat_area.tag_config(f"nick_{sender}", foreground=color, font=("Segoe UI", 10, "bold"))
        
        if sender == self.nickname:
            self.chat_area.insert(tk.END, "Вы: ", f"nick_{sender}")
        else:
            self.chat_area.insert(tk.END, f"{sender}: ", f"nick_{sender}")
        
        self.insert_message_with_links(text, f"nick_{sender}")
        self.chat_area.see(tk.END)
    
    def add_system_message(self, text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_area.insert(tk.END, f"[{timestamp}] ✨ {text}\n", "system")
        self.chat_area.see(tk.END)
    
    # ========== ОТПРАВКА СООБЩЕНИЙ ==========
    def send_message(self, event=None):
        text = self.message_entry.get().strip()
        if not text:
            return
        
        if text.startswith("/"):
            self.handle_command(text)
        else:
            if self.current_chat == "general":
                try:
                    self.sock.send((text + "\n").encode('utf-8'))
                except Exception as e:
                    self.add_system_message(f"❌ Ошибка отправки: {e}")
            else:
                self.sock.send(f"CMD:PM|{self.current_chat}|{text}\n".encode('utf-8'))
        
        self.message_entry.delete(0, tk.END)
    
    def handle_command(self, text):
        if text.startswith("/edit "):
            parts = text.split(" ", 2)
            if len(parts) >= 3:
                self.sock.send(f"CMD:EDIT|{parts[1]}|{parts[2]}\n".encode('utf-8'))
        elif text.startswith("/color "):
            parts = text.split(" ", 1)
            if len(parts) >= 2:
                color = parts[1]
                if color.startswith('#') and len(color) == 7:
                    self.set_nick_color(self.nickname, color)
                    self.add_system_message(f"🎨 Цвет ника изменён на {color}")
        elif text == "/refresh":
            self.load_files_list()
            self.add_system_message("🔄 Список файлов обновлён")
    
    # ========== ПОЛУЧЕНИЕ СООБЩЕНИЙ ==========
    def receive_messages(self):
        buffer = ""
        while self.running:
            try:
                data = self.sock.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line:
                        self.root.after(0, lambda l=line: self.process_server_line(l))
                        
            except ConnectionResetError:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", "Соединение с сервером потеряно!"))
                self.root.after(0, self.on_close)
                break
            except Exception as e:
                if self.running:
                    print(f"Ошибка получения: {e}")
                break
    
    def process_server_line(self, line):
        if not line:
            return
        
        if line.startswith("JSON_PAYLOAD:"):
            payload = line[13:]
            try:
                msg = json.loads(payload)
                msg_type = msg.get("type")
                
                if msg_type == "history":
                    self.message_history = msg.get("messages", [])
                    self.files_list = msg.get("files", [])
                    self.root.after(0, self.update_files_listbox)
                    if self.current_chat == "general":
                        self.root.after(0, self.refresh_chat_display)
                        
                elif msg_type == "private_history":
                    target = msg.get("target")
                    messages = msg.get("messages", [])
                    self.private_messages[target] = messages
                    self.save_private_messages(target)
                    if self.current_chat == target:
                        self.root.after(0, self.refresh_chat_display)
                        
                elif msg_type == "message":
                    m = msg.get("data", {})
                    self.message_history.append(m)
                    if self.current_chat == "general":
                        self.root.after(0, lambda msg=m: self.display_message(msg))
                        
                elif msg_type == "file":
                    file_data = msg.get("data", {})
                    new_file = {
                        'id': file_data.get('id', ''),
                        'name': file_data.get('name', ''),
                        'size': file_data.get('size', 0),
                        'sender': file_data.get('sender', '')
                    }
                    self.files_list.append(new_file)
                    
                    file_msg = {
                        "sender": "ФАЙЛ",
                        "text": f"{file_data['sender']} 📁 {file_data['name']} ({file_data['size']/1024:.1f} KB)",
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "id": file_data.get('id', '')
                    }
                    self.message_history.append(file_msg)
                    self.root.after(0, self.update_files_listbox)
                    if self.current_chat == "general":
                        self.root.after(0, lambda msg=file_msg: self.display_message(msg))
                        
                elif msg_type == "private_file":
                    file_data = msg.get("data", {})
                    target = msg.get("target", "")
                    
                    if target not in self.private_files:
                        self.private_files[target] = []
                    
                    new_file = {
                        'id': file_data.get('id', ''),
                        'name': file_data.get('name', ''),
                        'size': file_data.get('size', 0),
                        'sender': file_data.get('sender', '')
                    }
                    self.private_files[target].append(new_file)
                    
                    if target not in self.private_chats_list:
                        self.private_chats_list.add(target)
                        self.save_chats_list()
                        self.root.after(0, self.update_chats_list)
                    
                    if self.current_chat == target:
                        self.root.after(0, self.update_files_listbox)
                        self.root.after(0, lambda: self.add_system_message(f"📁 {file_data['sender']} отправил файл: {file_data['name']}"))
                        
                elif msg_type == "notification":
                    self.root.after(0, lambda text=msg.get("text"): self.add_system_message(text))
                    
                elif msg_type == "private_message":
                    sender = msg["from"]
                    text = msg["text"]
                    
                    if sender not in self.private_chats_list:
                        self.private_chats_list.add(sender)
                        self.save_chats_list()
                        self.private_messages[sender] = []
                        self.private_files[sender] = []
                        self.root.after(0, self.update_chats_list)
                    
                    pm = {
                        'sender': sender,
                        'text': text,
                        'time': datetime.now().strftime("%H:%M:%S")
                    }
                    
                    if sender not in self.private_messages:
                        self.private_messages[sender] = []
                    self.private_messages[sender].append(pm)
                    self.save_private_messages(sender)
                    
                    if self.current_chat == sender:
                        self.root.after(0, lambda msg=pm, s=sender: self.display_private_message(msg, s))
                    else:
                        self.root.after(0, lambda s=sender: self.add_system_message(f"💬 Новое сообщение от {s}"))
                        
                elif msg_type == "private_sent":
                    target = msg["to"]
                    text = msg["text"]
                    
                    if target not in self.private_chats_list:
                        self.private_chats_list.add(target)
                        self.save_chats_list()
                        self.private_messages[target] = []
                        self.private_files[target] = []
                        self.root.after(0, self.update_chats_list)
                    
                    pm = {
                        'sender': self.nickname,
                        'text': text,
                        'time': datetime.now().strftime("%H:%M:%S")
                    }
                    
                    if target not in self.private_messages:
                        self.private_messages[target] = []
                    self.private_messages[target].append(pm)
                    self.save_private_messages(target)
                    
                    if self.current_chat == target:
                        self.root.after(0, lambda msg=pm, t=target: self.display_private_message(msg, t))
                    
                elif msg_type == "message_edited":
                    msg_id = msg["id"]
                    new_text = msg["text"]
                    for m in self.message_history:
                        if m.get('id') == msg_id:
                            m['text'] = new_text
                            m['edited'] = True
                            break
                    if self.current_chat == "general":
                        self.root.after(0, self.refresh_chat_display)
                    
                elif msg_type == "message_deleted":
                    msg_id = msg["id"]
                    for i, m in enumerate(self.message_history):
                        if m.get('id') == msg_id:
                            del self.message_history[i]
                            break
                    if self.current_chat == "general":
                        self.root.after(0, self.refresh_chat_display)
                    
                elif msg_type == "file_deleted":
                    file_id = msg.get("id")
                    for i, f in enumerate(self.files_list):
                        if f.get('id') == file_id:
                            del self.files_list[i]
                            break
                    self.root.after(0, self.update_files_listbox)
                    
                elif msg_type == "color_update":
                    nick = msg["nick"]
                    color = msg["color"]
                    self.nick_colors[nick] = color
                    self.save_nick_colors()
                    self.root.after(0, self.refresh_chat_display)
                    
                elif msg_type == "kicked":
                    self.root.after(0, lambda: messagebox.showerror("Кик", f"Вас отключили: {msg.get('reason')}"))
                    self.root.after(100, self.on_close)
                    
                elif msg_type == "banned":
                    self.root.after(0, lambda: messagebox.showerror("БАН", f"Вы забанены: {msg.get('reason')}"))
                    self.root.after(100, self.on_close)
                    
            except json.JSONDecodeError:
                pass
                
        elif line.startswith("MSG:"):
            self.root.after(0, lambda text=line[4:]: self.add_system_message(text))
    
    def on_close(self):
        self.running = False
        self.save_nick_colors()
        self.save_chats_list()
        for nick in self.private_messages:
            self.save_private_messages(nick)
        try:
            if self.sock:
                self.sock.close()
        except:
            pass
        try:
            self.root.destroy()
        except:
            pass

if __name__ == "__main__":
    client = ChatClient()