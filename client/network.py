# client/network.py
import socket
import threading
import json
import base64
import tkinter as tk
from tkinter import messagebox
import time

class NetworkManager:
    def __init__(self, app):
        self.app = app
        self.sock = None
        self.buffer = ""
        self.authenticated = False

    def ask_server_ip(self):
        dialog = tk.Toplevel(self.app.root)
        dialog.title("Подключение к серверу")
        dialog.geometry("450x280")
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self.app.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 225
        y = (dialog.winfo_screenheight() // 2) - 140
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="🌐 ПОДКЛЮЧЕНИЕ К СЕРВЕРУ", 
                 font=("Segoe UI", 14, "bold"),
                 bg='#1e1e1e', fg='#4ec9b0').pack(pady=20)
        
        tk.Label(dialog, text="Введите IP-адрес сервера:", 
                 font=("Segoe UI", 11),
                 bg='#1e1e1e', fg='#d4d4d4').pack()
        
        ip_entry = tk.Entry(dialog, font=("Segoe UI", 12), 
                            bg='#3c3c3c', fg='#d4d4d4', 
                            relief=tk.FLAT, width=25, 
                            justify='center',
                            insertbackground='white')
        ip_entry.pack(pady=15)
        ip_entry.insert(0, self.app.settings.server_ip)
        ip_entry.select_range(0, tk.END)
        ip_entry.focus()
        
        tk.Label(dialog, text="Пример: 192.168.0.155 или 26.66.193.221 (Radmin VPN)", 
                 font=("Segoe UI", 8),
                 bg='#1e1e1e', fg='#6a9955').pack()
        
        result = {"ip": None, "cancelled": True}
        
        def on_submit():
            ip = ip_entry.get().strip()
            if ip:
                result["ip"] = ip
                result["cancelled"] = False
                dialog.destroy()
            else:
                messagebox.showwarning("Внимание", "Введите IP-адрес!", parent=dialog)
        
        def on_cancel():
            dialog.destroy()
            self.app.root.quit()
        
        btn_frame = tk.Frame(dialog, bg='#1e1e1e')
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Подключиться →", command=on_submit,
                  bg='#0e639c', fg="white", font=("Segoe UI", 11, "bold"),
                  relief=tk.FLAT, cursor="hand2", padx=25, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Отмена", command=on_cancel,
                  bg='#4a4a4a', fg="white", font=("Segoe UI", 11, "bold"),
                  relief=tk.FLAT, cursor="hand2", padx=25, pady=5).pack(side=tk.LEFT, padx=5)
        
        ip_entry.bind("<Return>", lambda e: on_submit())
        dialog.protocol("WM_DELETE_WINDOW", on_cancel)
        dialog.wait_window()
        
        return result["ip"] if not result["cancelled"] else None

    def ask_auth(self):
        auth_dialog = tk.Toplevel(self.app.root)
        auth_dialog.title("Авторизация")
        auth_dialog.geometry("400x580")
        auth_dialog.configure(bg='#1e1e1e')
        auth_dialog.transient(self.app.root)
        auth_dialog.grab_set()
        auth_dialog.resizable(False, False)
        
        auth_dialog.update_idletasks()
        x = (auth_dialog.winfo_screenwidth() // 2) - 200
        y = (auth_dialog.winfo_screenheight() // 2) - 290
        auth_dialog.geometry(f"+{x}+{y}")
        
        result = {"success": False, "nickname": None, "username": None}
        remember_var = tk.BooleanVar(value=self.app.settings.save_auth)
        
        def show_login_frame():
            for widget in form_frame.winfo_children():
                widget.destroy()
            
            tk.Label(form_frame, text="Логин:", bg='#1e1e1e', fg='#d4d4d4', 
                     font=("Segoe UI", 10)).pack(pady=(10, 5))
            login_entry = tk.Entry(form_frame, bg='#3c3c3c', fg='white', 
                                   font=("Segoe UI", 10), width=30, relief=tk.FLAT)
            login_entry.pack(pady=5)
            if self.app.settings.saved_username:
                login_entry.insert(0, self.app.settings.saved_username)
            
            tk.Label(form_frame, text="Пароль:", bg='#1e1e1e', fg='#d4d4d4', 
                     font=("Segoe UI", 10)).pack(pady=(10, 5))
            pass_entry = tk.Entry(form_frame, bg='#3c3c3c', fg='white', 
                                  font=("Segoe UI", 10), width=30, show="*", relief=tk.FLAT)
            pass_entry.pack(pady=5)
            if self.app.settings.save_auth and self.app.settings.saved_password:
                pass_entry.insert(0, self.app.settings.saved_password)
            
            remember_cb = tk.Checkbutton(form_frame, text="Запомнить меня", 
                                         variable=remember_var,
                                         bg='#1e1e1e', fg='#d4d4d4',
                                         selectcolor='#1e1e1e',
                                         activebackground='#1e1e1e',
                                         activeforeground='#d4d4d4',
                                         font=("Segoe UI", 9))
            remember_cb.pack(pady=(10, 5))
            
            def do_login():
                username = login_entry.get().strip()
                password = pass_entry.get().strip()
                if not username or not password:
                    status_label.config(text="❌ Заполните все поля", fg='#f48771')
                    return
                
                encoded = base64.b64encode(password.encode()).decode()
                self.send_raw(f"LOGIN|{username}|{encoded}")
                
                try:
                    self.sock.settimeout(5)
                    response = self.sock.recv(4096).decode('utf-8').strip()
                    self.sock.settimeout(None)
                    
                    if response.startswith("AUTH_SUCCESS"):
                        parts = response.split('|')
                        nickname = parts[1]
                        result["nickname"] = nickname
                        result["username"] = parts[2] if len(parts) > 2 else username
                        result["success"] = True
                        
                        self.app.settings.username = username
                        self.app.settings.nickname = nickname
                        self.app.settings.saved_password = password if remember_var.get() else ""
                        self.app.settings.save_auth = remember_var.get()
                        self.app.settings.save_config()
                        
                        auth_dialog.destroy()
                        self.authenticated = True
                        threading.Thread(target=self.receive_loop, daemon=True).start()
                        
                    elif response.startswith("AUTH_FAIL"):
                        error = response.split('|')[1] if '|' in response else "Ошибка"
                        status_label.config(text=f"❌ {error}", fg='#f48771')
                except socket.timeout:
                    status_label.config(text="❌ Сервер не отвечает", fg='#f48771')
                except Exception as e:
                    status_label.config(text=f"❌ Ошибка: {e}", fg='#f48771')
            
            tk.Button(form_frame, text="Войти", command=do_login,
                      bg='#0e639c', fg='white', font=("Segoe UI", 10, "bold"),
                      relief=tk.FLAT, cursor="hand2", width=20, pady=5).pack(pady=15)
            
            tk.Button(form_frame, text="Нет аккаунта? Зарегистрироваться",
                      command=show_register_frame,
                      bg='#1e1e1e', fg='#569cd6', font=("Segoe UI", 9),
                      relief=tk.FLAT, cursor="hand2").pack()
            
            tk.Button(form_frame, text="🔑 Забыли пароль?",
                      command=lambda: self.forgot_password_window(auth_dialog),
                      bg='#1e1e1e', fg='#ce9178', font=("Segoe UI", 9),
                      relief=tk.FLAT, cursor="hand2").pack(pady=(5, 0))
            
            login_entry.focus()
            pass_entry.bind("<Return>", lambda e: do_login())
        
        def show_register_frame():
            for widget in form_frame.winfo_children():
                widget.destroy()
            
            tk.Label(form_frame, text="Логин (3-20 символов):", bg='#1e1e1e', fg='#d4d4d4', 
                     font=("Segoe UI", 10)).pack(pady=(10, 5))
            login_entry = tk.Entry(form_frame, bg='#3c3c3c', fg='white', 
                                   font=("Segoe UI", 10), width=30, relief=tk.FLAT)
            login_entry.pack(pady=5)
            
            tk.Label(form_frame, text="Пароль (мин 4 символа):", bg='#1e1e1e', fg='#d4d4d4', 
                     font=("Segoe UI", 10)).pack(pady=(10, 5))
            pass_entry = tk.Entry(form_frame, bg='#3c3c3c', fg='white', 
                                  font=("Segoe UI", 10), width=30, show="*", relief=tk.FLAT)
            pass_entry.pack(pady=5)
            
            tk.Label(form_frame, text="Никнейм:", bg='#1e1e1e', fg='#d4d4d4', 
                     font=("Segoe UI", 10)).pack(pady=(10, 5))
            nick_entry = tk.Entry(form_frame, bg='#3c3c3c', fg='white', 
                                  font=("Segoe UI", 10), width=30, relief=tk.FLAT)
            nick_entry.pack(pady=5)
            
            remember_cb = tk.Checkbutton(form_frame, text="Запомнить меня", 
                                         variable=remember_var,
                                         bg='#1e1e1e', fg='#d4d4d4',
                                         selectcolor='#1e1e1e',
                                         activebackground='#1e1e1e',
                                         activeforeground='#d4d4d4',
                                         font=("Segoe UI", 9))
            remember_cb.pack(pady=(10, 5))
            
            def do_register():
                username = login_entry.get().strip()
                password = pass_entry.get().strip()
                nickname = nick_entry.get().strip()
                
                if not username or not password:
                    status_label.config(text="❌ Заполните логин и пароль", fg='#f48771')
                    return
                if len(username) < 3:
                    status_label.config(text="❌ Логин должен быть не менее 3 символов", fg='#f48771')
                    return
                if len(password) < 4:
                    status_label.config(text="❌ Пароль должен быть не менее 4 символов", fg='#f48771')
                    return
                if not nickname:
                    nickname = username
                
                encoded = base64.b64encode(password.encode()).decode()
                self.send_raw(f"REGISTER|{username}|{encoded}|{nickname}")
                
                try:
                    self.sock.settimeout(5)
                    response = self.sock.recv(4096).decode('utf-8').strip()
                    self.sock.settimeout(None)
                    
                    if response.startswith("AUTH_SUCCESS"):
                        parts = response.split('|')
                        nickname = parts[1]
                        result["nickname"] = nickname
                        result["username"] = parts[2] if len(parts) > 2 else username
                        result["success"] = True
                        
                        self.app.settings.username = username
                        self.app.settings.nickname = nickname
                        self.app.settings.saved_password = password if remember_var.get() else ""
                        self.app.settings.save_auth = remember_var.get()
                        self.app.settings.save_config()
                        
                        auth_dialog.destroy()
                        self.authenticated = True
                        threading.Thread(target=self.receive_loop, daemon=True).start()
                        
                    elif response.startswith("AUTH_FAIL"):
                        error = response.split('|')[1] if '|' in response else "Ошибка"
                        status_label.config(text=f"❌ {error}", fg='#f48771')
                except socket.timeout:
                    status_label.config(text="❌ Сервер не отвечает", fg='#f48771')
                except Exception as e:
                    status_label.config(text=f"❌ Ошибка: {e}", fg='#f48771')
            
            tk.Button(form_frame, text="Зарегистрироваться", command=do_register,
                      bg='#6a9955', fg='white', font=("Segoe UI", 10, "bold"),
                      relief=tk.FLAT, cursor="hand2", width=20, pady=5).pack(pady=15)
            
            tk.Button(form_frame, text="Уже есть аккаунт? Войти",
                      command=show_login_frame,
                      bg='#1e1e1e', fg='#569cd6', font=("Segoe UI", 9),
                      relief=tk.FLAT, cursor="hand2").pack()
            
            login_entry.focus()
        
        tk.Label(auth_dialog, text="🔐 АВТОРИЗАЦИЯ", 
                 font=("Segoe UI", 14, "bold"),
                 bg='#1e1e1e', fg='#4ec9b0').pack(pady=20)
        
        status_label = tk.Label(auth_dialog, text="", bg='#1e1e1e', 
                                fg='#f48771', font=("Segoe UI", 9))
        status_label.pack(pady=5)
        
        form_frame = tk.Frame(auth_dialog, bg='#1e1e1e')
        form_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        show_login_frame()
        
        auth_dialog.protocol("WM_DELETE_WINDOW", auth_dialog.destroy)
        auth_dialog.wait_window()
        
        return result

    def forgot_password_window(self, parent_dialog):
        parent_dialog.destroy()
        
        recovery_dialog = tk.Toplevel(self.app.root)
        recovery_dialog.title("Восстановление пароля")
        recovery_dialog.geometry("400x420")
        recovery_dialog.configure(bg='#1e1e1e')
        recovery_dialog.transient(self.app.root)
        recovery_dialog.grab_set()
        
        tk.Label(recovery_dialog, text="🔐 ВОССТАНОВЛЕНИЕ ПАРОЛЯ",
                 font=("Segoe UI", 14, "bold"),
                 bg='#1e1e1e', fg='#4ec9b0').pack(pady=20)
        
        status_label = tk.Label(recovery_dialog, text="", bg='#1e1e1e', fg='#f48771')
        status_label.pack(pady=5)
        
        step1_frame = tk.Frame(recovery_dialog, bg='#1e1e1e')
        step1_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)
        
        tk.Label(step1_frame, text="Введите ваш логин:", bg='#1e1e1e', fg='white',
                 font=("Segoe UI", 11)).pack(pady=10)
        
        username_entry = tk.Entry(step1_frame, bg='#3c3c3c', fg='white',
                                  font=("Segoe UI", 11), width=30)
        username_entry.pack(pady=10)
        username_entry.focus()
        
        def request_code():
            username = username_entry.get().strip()
            if not username:
                status_label.config(text="❌ Введите логин!")
                return
            
            self.send_raw(f"FORGOT|{username}")
            
            try:
                self.sock.settimeout(5)
                response = self.sock.recv(4096).decode('utf-8').strip()
                self.sock.settimeout(None)
                
                if response.startswith("RECOVERY_CODE|"):
                    code = response.split('|')[1]
                    if code == "ERROR":
                        status_label.config(text="❌ Пользователь не найден!")
                    else:
                        status_label.config(text=f"✅ Код отправлен администратору!", fg='#6a9955')
                        show_code_input(username)
                else:
                    status_label.config(text="❌ Пользователь не найден!")
            except socket.timeout:
                status_label.config(text="❌ Сервер не отвечает!")
            except Exception as e:
                status_label.config(text=f"❌ Ошибка: {e}")
        
        tk.Button(step1_frame, text="Получить код", command=request_code,
                  bg='#0e639c', fg='white', font=("Segoe UI", 11, "bold"),
                  relief=tk.FLAT, cursor="hand2", width=20).pack(pady=20)
        
        username_entry.bind("<Return>", lambda e: request_code())
        
        def show_code_input(username):
            for widget in recovery_dialog.winfo_children():
                widget.destroy()
            
            tk.Label(recovery_dialog, text="🔐 ВВЕДИТЕ КОД",
                     font=("Segoe UI", 14, "bold"),
                     bg='#1e1e1e', fg='#4ec9b0').pack(pady=20)
            
            status_label2 = tk.Label(recovery_dialog, text="", bg='#1e1e1e', fg='#f48771')
            status_label2.pack(pady=5)
            
            tk.Label(recovery_dialog, text=f"Код отправлен администратору.\nСпросите у него код для: {username}",
                     bg='#1e1e1e', fg='#6a9955', font=("Segoe UI", 9)).pack(pady=10)
            
            code_entry = tk.Entry(recovery_dialog, bg='#3c3c3c', fg='white',
                                  font=("Segoe UI", 16), width=10, justify='center')
            code_entry.pack(pady=20)
            code_entry.focus()
            
            attempts = [3]
            
            def verify_code():
                entered_code = code_entry.get().strip()
                if not entered_code:
                    status_label2.config(text="❌ Введите код!")
                    return
                
                self.send_raw(f"VERIFY_CODE|{username}|{entered_code}")
                
                try:
                    self.sock.settimeout(5)
                    response = self.sock.recv(4096).decode('utf-8').strip()
                    self.sock.settimeout(None)
                    
                    if response == "VERIFY_SUCCESS":
                        show_new_password(username)
                    else:
                        attempts[0] -= 1
                        if attempts[0] > 0:
                            status_label2.config(text=f"❌ Неверный код! Осталось попыток: {attempts[0]}", fg='#f48771')
                        else:
                            status_label2.config(text="❌ Попытки исчерпаны!", fg='#f48771')
                            recovery_dialog.after(1500, recovery_dialog.destroy)
                except socket.timeout:
                    status_label2.config(text="❌ Сервер не отвечает!")
                except Exception as e:
                    status_label2.config(text=f"❌ Ошибка: {e}")
            
            tk.Button(recovery_dialog, text="Проверить код", command=verify_code,
                      bg='#0e639c', fg='white', font=("Segoe UI", 11, "bold"),
                      relief=tk.FLAT, cursor="hand2", width=20).pack(pady=20)
            
            code_entry.bind("<Return>", lambda e: verify_code())
        
        def show_new_password(username):
            for widget in recovery_dialog.winfo_children():
                widget.destroy()
            
            tk.Label(recovery_dialog, text="🔐 НОВЫЙ ПАРОЛЬ",
                     font=("Segoe UI", 14, "bold"),
                     bg='#1e1e1e', fg='#4ec9b0').pack(pady=20)
            
            status_label3 = tk.Label(recovery_dialog, text="", bg='#1e1e1e', fg='#f48771')
            status_label3.pack(pady=5)
            
            tk.Label(recovery_dialog, text="Новый пароль:", bg='#1e1e1e', fg='white').pack(pady=5)
            pass_entry = tk.Entry(recovery_dialog, bg='#3c3c3c', fg='white',
                                  font=("Segoe UI", 11), width=30, show="*")
            pass_entry.pack(pady=5)
            
            tk.Label(recovery_dialog, text="Повторите пароль:", bg='#1e1e1e', fg='white').pack(pady=5)
            pass_entry2 = tk.Entry(recovery_dialog, bg='#3c3c3c', fg='white',
                                   font=("Segoe UI", 11), width=30, show="*")
            pass_entry2.pack(pady=5)
            
            def reset_password():
                p1 = pass_entry.get().strip()
                p2 = pass_entry2.get().strip()
                
                if not p1 or not p2:
                    status_label3.config(text="❌ Заполните все поля!")
                    return
                if p1 != p2:
                    status_label3.config(text="❌ Пароли не совпадают!")
                    return
                if len(p1) < 4:
                    status_label3.config(text="❌ Пароль должен быть от 4 символов!")
                    return
                
                encoded = base64.b64encode(p1.encode()).decode()
                self.send_raw(f"RESET_PASSWORD|{username}|{encoded}")
                
                try:
                    self.sock.settimeout(5)
                    response = self.sock.recv(4096).decode('utf-8').strip()
                    self.sock.settimeout(None)
                    
                    if response == "PASSWORD_RESET_OK":
                        messagebox.showinfo("Успех", "✅ Пароль успешно изменён!\nТеперь вы можете войти.")
                        recovery_dialog.destroy()
                        self.connect()
                    else:
                        status_label3.config(text="❌ Ошибка сброса пароля!")
                except socket.timeout:
                    status_label3.config(text="❌ Сервер не отвечает!")
                except Exception as e:
                    status_label3.config(text=f"❌ Ошибка: {e}")
            
            tk.Button(recovery_dialog, text="Сбросить пароль", command=reset_password,
                      bg='#6a9955', fg='white', font=("Segoe UI", 11, "bold"),
                      relief=tk.FLAT, cursor="hand2", width=20).pack(pady=20)
            
            pass_entry.focus()
            pass_entry2.bind("<Return>", lambda e: reset_password())
        
        recovery_dialog.protocol("WM_DELETE_WINDOW", recovery_dialog.destroy)
        recovery_dialog.wait_window()

    def connect(self):
        ip = self.ask_server_ip()
        if not ip:
            return False
        
        self.app.settings.server_ip = ip
        self.app.settings.save_config()
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((ip, 5555))
            
            response = self.sock.recv(1024).decode('utf-8').strip()
            if response == "BANNED":
                messagebox.showerror("БАН", "Вы забанены на этом сервере!")
                return False
            if response != "AUTH_REQUIRED":
                messagebox.showerror("Ошибка", "Неожиданный ответ от сервера")
                return False
            
            self.sock.settimeout(None)
            auth = self.ask_auth()
            if not auth["success"]:
                return False
            
            self.app.settings.nickname = auth["nickname"]
            self.app.settings.username = auth["username"]
            self.app.settings.saved_username = auth["username"]
            self.app.settings.save_config()
            self.app.root.title(f"💬 Messenger - {auth['nickname']}")
            self.authenticated = True
            
            threading.Thread(target=self.receive_loop, daemon=True).start()
            
            return True
            
        except socket.timeout:
            messagebox.showerror("Ошибка", "Таймаут подключения. Сервер не отвечает.")
            return False
        except ConnectionRefusedError:
            messagebox.showerror("Ошибка", f"Сервер {ip}:5555 не доступен")
            return False
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось подключиться: {e}")
            return False

    def send_raw(self, message):
        try:
            if self.sock:
                self.sock.send((message + "\n").encode('utf-8'))
        except:
            pass

    def send(self, message):
        if not self.authenticated:
            return
        
        if self.app.ui and self.app.ui.current_chat == "general":
            self.send_raw(message)
        elif self.app.ui:
            self.send_raw(f"CMD:PM|{self.app.ui.current_chat}|{message}")

    def receive_loop(self):
        while self.authenticated and self.sock:
            try:
                data = self.sock.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    break
                self.buffer += data
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    if line and self.app.ui:
                        self.app.root.after(0, lambda l=line: self.process_line(l))
            except:
                break
        
        self.authenticated = False
        if self.app.ui:
            self.app.root.after(0, lambda: self.app.ui.add_system_message("❌ Соединение потеряно"))

    def process_line(self, line):
        try:
            if line.startswith("JSON_PAYLOAD:"):
                payload = line[13:]
                try:
                    msg = json.loads(payload)
                    if self.app.ui:
                        self.app.root.after(0, lambda: self.app.ui.handle_server_message(msg))
                except:
                    pass
            elif line.startswith("MSG:"):
                if self.app.ui:
                    self.app.root.after(0, lambda: self.app.ui.add_system_message(line[4:]))
        except:
            pass