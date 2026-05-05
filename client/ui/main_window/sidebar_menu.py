# client/ui/main_window/sidebar_menu.py
import tkinter as tk
from tkinter import colorchooser, simpledialog, messagebox
import base64

class SidebarMenu:
    def __init__(self, ui):
        self.ui = ui
        self.window = None

    def open(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
            self.window = None
            return

        self.window = tk.Toplevel(self.ui.app.root)
        self.window.title("Меню")
        self.window.geometry("300x850")
        self.window.configure(bg=self.ui.color_manager.get_color('sidebar'))
        self.window.transient(self.ui.app.root)
        self.window.resizable(False, False)

        x = self.ui.app.root.winfo_x() + 5
        y = self.ui.app.root.winfo_y() + 50
        self.window.geometry(f"+{x}+{y}")
        self.window.bind('<FocusOut>', lambda e: self.close())

        main_frame = tk.Frame(self.window, bg=self.ui.color_manager.get_color('sidebar'))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Профиль ---
        tk.Label(main_frame, text="👤", font=("Segoe UI", 50), bg=self.ui.color_manager.get_color('sidebar')).pack(pady=(20, 5))
        tk.Label(main_frame, text=self.ui.app.settings.nickname or "User", font=("Segoe UI", 14, "bold"), bg=self.ui.color_manager.get_color('sidebar'), fg='white').pack()
        tk.Label(main_frame, text=f"@{self.ui.app.settings.username or 'user'}", font=("Segoe UI", 10), bg=self.ui.color_manager.get_color('sidebar'), fg='#888').pack()
        tk.Frame(main_frame, bg='#444', height=1).pack(fill=tk.X, padx=20, pady=15)

        # --- Пункты меню ---
        items = [
            ("🎨", "Изменить цвет ника", self.change_nick_color),
            ("🖌️", "Изменить тему", self.change_theme),
            ("🎨🎨", "Кастомная тема", self.custom_theme),
            ("📏", "Размер шрифта", self.change_font_size),
            ("✏️", "Изменить имя", self.change_display_name),
            ("👥", "Друзья", self.show_friends),
            ("🔐", "Сменить пароль", self.change_password),
            ("ℹ️", "О программе", self.show_about)
        ]

        for icon, text, cmd in items:
            btn = tk.Button(main_frame, text=f"{icon}  {text}", font=("Segoe UI", 11),
                            bg=self.ui.color_manager.get_color('sidebar'), fg='white', anchor='w',
                            relief=tk.FLAT, cursor="hand2", command=cmd, height=2)
            btn.pack(fill=tk.X, padx=15, pady=2)

        tk.Frame(main_frame, bg='#444', height=1).pack(fill=tk.X, padx=20, pady=15)

        # --- НОВАЯ КНОПКА: СМЕНИТЬ АККАУНТ ---
        tk.Button(main_frame, text="🔄  Сменить аккаунт", font=("Segoe UI", 11),
                  bg='#6a9955', fg='white', anchor='w', relief=tk.FLAT, cursor="hand2",
                  command=self.switch_account, height=2).pack(fill=tk.X, padx=15, pady=5)

        # --- КНОПКА ВЫХОДА ---
        tk.Button(main_frame, text="❌  Закрыть приложение", font=("Segoe UI", 11),
                  bg='#f48771', fg='white', anchor='w', relief=tk.FLAT, cursor="hand2",
                  command=self.quit_app, height=2).pack(fill=tk.X, padx=15, pady=5)

        self.window.focus_set()

    # --- ОСТАЛЬНЫЕ МЕТОДЫ (без изменений) ---
    def close(self):
        if self.window and self.window.winfo_exists():
            self.window.destroy()
            self.window = None

    def switch_account(self):
        self.close()
        self.ui.switch_account()  # Вызываем новый метод в chat_ui

    def quit_app(self):
        self.close()
        self.ui.app.root.quit()

    def change_nick_color(self):
        self.close()
        color = colorchooser.askcolor(title="Выберите цвет ника")
        if color and color[1]:
            self.ui.app.network.send_raw(f"CMD:COLOR|{color[1]}")
            self.ui.add_system_message(f"🎨 Цвет ника изменён")

    def change_theme(self):
        self.close()
        self.ui.theme_manager.change_theme()

    def custom_theme(self):
        self.close()
        self.ui.theme_manager.custom_theme()

    def change_font_size(self):
        self.close()
        self.ui.theme_manager.change_font_size()

    def change_display_name(self):
        self.close()
        new_name = simpledialog.askstring("Изменить имя", "Введите новое имя:")
        if new_name and new_name.strip():
            self.ui.app.network.send_raw(f"CMD:CHANGENICK|{new_name.strip()}")
            self.ui.app.settings.nickname = new_name.strip()
            self.ui.app.settings.save_config()
            self.ui.add_system_message(f"✅ Имя изменено на {new_name}")
            if hasattr(self.ui.ui_components, 'chat_header'):
                self.ui.ui_components.chat_header.config(text="💬 Общий чат")

    def show_friends(self):
        self.close()
        self.ui.friends_manager.show_friends()

    def change_password(self):
        self.close()
        win = tk.Toplevel(self.ui.app.root)
        win.title("Смена пароля")
        win.geometry("400x350")
        win.configure(bg=self.ui.color_manager.get_color('bg'))

        tk.Label(win, text="🔐 Смена пароля", font=("Segoe UI", 14, "bold"),
                 bg=self.ui.color_manager.get_color('bg'),
                 fg=self.ui.color_manager.get_color('text')).pack(pady=20)

        tk.Label(win, text="Старый пароль:", bg=self.ui.color_manager.get_color('bg'),
                 fg=self.ui.color_manager.get_color('text')).pack()
        old_pass = tk.Entry(win, show="*", bg=self.ui.color_manager.get_color('input_bg'),
                            fg=self.ui.color_manager.get_color('text'), width=30)
        old_pass.pack(pady=5)

        # ... (остальной код смены пароля без изменений) ...
        tk.Label(win, text="Новый пароль:", bg=self.ui.color_manager.get_color('bg'),
                 fg=self.ui.color_manager.get_color('text')).pack()
        new_pass = tk.Entry(win, show="*", bg=self.ui.color_manager.get_color('input_bg'),
                            fg=self.ui.color_manager.get_color('text'), width=30)
        new_pass.pack(pady=5)

        tk.Label(win, text="Подтверждение:", bg=self.ui.color_manager.get_color('bg'),
                 fg=self.ui.color_manager.get_color('text')).pack()
        confirm = tk.Entry(win, show="*", bg=self.ui.color_manager.get_color('input_bg'),
                           fg=self.ui.color_manager.get_color('text'), width=30)
        confirm.pack(pady=5)

        status = tk.Label(win, text="", bg=self.ui.color_manager.get_color('bg'), fg='#f48771')
        status.pack(pady=10)

        def change():
            if not old_pass.get() or not new_pass.get():
                status.config(text="❌ Заполните все поля!")
                return
            if new_pass.get() != confirm.get():
                status.config(text="❌ Пароли не совпадают!")
                return
            if len(new_pass.get()) < 4:
                status.config(text="❌ Пароль должен быть от 4 символов!")
                return

            encoded_new = base64.b64encode(new_pass.get().encode()).decode()
            encoded_old = base64.b64encode(old_pass.get().encode()).decode()
            self.ui.app.network.send_raw(f"CMD:CHANGEPASS|{self.ui.app.settings.username}|{encoded_old}|{encoded_new}")
            status.config(text="✅ Запрос отправлен", fg='#6a9955')
            win.after(2000, win.destroy)

        tk.Button(win, text="Сменить пароль", command=change,
                  bg=self.ui.color_manager.get_color('accent'), fg='white', relief=tk.FLAT,
                  padx=20, pady=8).pack(pady=20)

    def show_about(self):
        self.close()
        messagebox.showinfo("О программе", f"Messenger v2.0\nPython + Tkinter\n\nРазработчик: StreloK_45")