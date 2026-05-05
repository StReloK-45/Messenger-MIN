# client/ui/main_window/theme_manager.py
import tkinter as tk
from tkinter import colorchooser, messagebox

class ThemeManager:
    def __init__(self, ui):
        self.ui = ui
    
    def change_nick_color(self):
        color = colorchooser.askcolor(title="Выберите цвет ника")
        if color and color[1]:
            self.ui.app.network.send_raw(f"CMD:COLOR|{color[1]}")
            self.ui.add_system_message(f"🎨 Цвет ника изменён")
    
    def change_theme(self):
        win = tk.Toplevel(self.ui.app.root)
        win.title("Тема")
        win.geometry("300x250")
        win.configure(bg=self.ui.color_manager.get_color('bg'))
        
        tk.Label(win, text="Выберите тему:", bg=self.ui.color_manager.get_color('bg'),
                 fg=self.ui.color_manager.get_color('text')).pack(pady=20)
        
        theme_var = tk.StringVar(value=self.ui.app.settings.theme)
        
        def apply():
            self.ui.app.settings.theme = theme_var.get()
            self.ui.app.settings.save()
            win.destroy()
            messagebox.showinfo("Успех", "Тема изменена. Перезапустите приложение.")
        
        tk.Radiobutton(win, text="🌙 Тёмная", variable=theme_var, value="dark",
                       bg=self.ui.color_manager.get_color('bg'),
                       fg=self.ui.color_manager.get_color('text')).pack(pady=5)
        tk.Radiobutton(win, text="☀️ Светлая", variable=theme_var, value="light",
                       bg=self.ui.color_manager.get_color('bg'),
                       fg=self.ui.color_manager.get_color('text')).pack(pady=5)
        tk.Radiobutton(win, text="🎨 Кастомная", variable=theme_var, value="custom",
                       bg=self.ui.color_manager.get_color('bg'),
                       fg=self.ui.color_manager.get_color('text')).pack(pady=5)
        
        tk.Button(win, text="Применить", command=apply,
                  bg=self.ui.color_manager.get_color('accent'), fg='white',
                  relief=tk.FLAT).pack(pady=20)
    
    def change_font_size(self):
        win = tk.Toplevel(self.ui.app.root)
        win.title("Размер шрифта")
        win.geometry("300x150")
        win.configure(bg=self.ui.color_manager.get_color('bg'))
        
        tk.Label(win, text=f"Текущий размер: {self.ui.app.settings.font_size}",
                 bg=self.ui.color_manager.get_color('bg'),
                 fg=self.ui.color_manager.get_color('text')).pack(pady=20)
        
        scale = tk.Scale(win, from_=8, to=16, orient=tk.HORIZONTAL,
                         bg=self.ui.color_manager.get_color('bg'),
                         fg=self.ui.color_manager.get_color('text'))
        scale.set(self.ui.app.settings.font_size)
        scale.pack(padx=20, fill=tk.X)
        
        def apply():
            new_size = int(scale.get())
            self.ui.app.settings.font_size = new_size
            self.ui.app.settings.save()
            self.ui.ui_components.message_entry.configure(font=("Segoe UI", new_size))
            win.destroy()
            self.ui.add_system_message(f"✅ Размер шрифта изменён на {new_size}")
        
        tk.Button(win, text="Применить", command=apply,
                  bg=self.ui.color_manager.get_color('accent'), fg='white',
                  relief=tk.FLAT).pack(pady=20)
    
    def custom_theme(self):
        win = tk.Toplevel(self.ui.app.root)
        win.title("Кастомная тема")
        win.geometry("450x550")
        win.configure(bg=self.ui.color_manager.get_color('bg'))
        win.transient(self.ui.app.root)
        
        tk.Label(win, text="🎨 Настройка кастомной темы", font=("Segoe UI", 14, "bold"),
                 bg=self.ui.color_manager.get_color('bg'),
                 fg=self.ui.color_manager.get_color('text')).pack(pady=15)
        
        colors = self.ui.app.settings.custom_colors.copy()
        buttons = {}
        
        color_items = [
            ("accent", "Акцентный цвет (кнопки)"),
            ("bg", "Фоновый цвет"),
            ("sidebar", "Цвет боковых панелей"),
            ("chat_bg", "Цвет области чата"),
            ("my_bubble", "Цвет своих сообщений"),
            ("other_bubble", "Цвет чужих сообщений")
        ]
        
        for key, label in color_items:
            frame = tk.Frame(win, bg=self.ui.color_manager.get_color('bg'))
            frame.pack(fill=tk.X, padx=20, pady=5)
            tk.Label(frame, text=label, bg=self.ui.color_manager.get_color('bg'),
                     fg=self.ui.color_manager.get_color('text'), width=25,
                     anchor='w').pack(side=tk.LEFT)
            
            def pick(k=key, cur=colors.get(key, '#0e639c')):
                color = colorchooser.askcolor(initialcolor=cur, title=f"Выберите цвет для {label}")
                if color and color[1]:
                    colors[k] = color[1]
                    buttons[k].config(bg=color[1])
            
            btn = tk.Button(frame, text="Выбрать", command=pick,
                           bg=colors.get(key, '#0e639c'), fg='white',
                           relief=tk.FLAT, cursor="hand2")
            btn.pack(side=tk.RIGHT)
            buttons[key] = btn
        
        def apply_custom():
            self.ui.app.settings.custom_colors = colors
            self.ui.app.settings.theme = "custom"
            self.ui.app.settings.save()
            win.destroy()
            messagebox.showinfo("Успех", "Кастомная тема сохранена! Перезапустите приложение.")
        
        def reset():
            self.ui.app.settings.reset_custom_colors()
            win.destroy()
            self.custom_theme()
        
        btn_frame = tk.Frame(win, bg=self.ui.color_manager.get_color('bg'))
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Применить", command=apply_custom,
                  bg=self.ui.color_manager.get_color('accent'), fg='white',
                  relief=tk.FLAT, padx=20, pady=8).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="Сбросить", command=reset,
                  bg='#f48771', fg='white', relief=tk.FLAT,
                  padx=20, pady=8).pack(side=tk.LEFT, padx=10)