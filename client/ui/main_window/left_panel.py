# client/ui/main_window/left_panel.py
import tkinter as tk
from tkinter import simpledialog, messagebox


class LeftPanel:
    def __init__(self, ui):
        self.ui = ui
        self.chats_listbox = None
    
    def setup(self):
        self.chats_listbox = self.ui.ui_components.chats_listbox
        self.chats_listbox.bind("<Button-3>", self.show_context_menu)
    
    def update_chats_list(self):
        self.chats_listbox.delete(0, tk.END)
        self.chats_listbox.insert(tk.END, "  💬 Общий чат")
        for nick in sorted(self.ui.private_chats_list):
            self.chats_listbox.insert(tk.END, f"  👤 {nick}")
        for group_name in self.ui.group_chats:
            self.chats_listbox.insert(tk.END, f"  👥 {group_name}")
        print(f"[DEBUG] Обновлён список чатов: {len(self.ui.private_chats_list)} личных, {len(self.ui.group_chats)} групп")
    
    def create_group_dialog(self):
        group_name = simpledialog.askstring("Создать группу", "Введите название группы:")
        if not group_name:
            return
        
        # Проверка на существование
        if group_name in self.ui.group_chats:
            self.ui.add_system_message("❌ Группа с таким названием уже существует!")
            return
        
        # Создаём группу на сервере
        self.ui.app.network.send_raw(f"CMD:CREATE_GROUP|{group_name}")
        self.ui.group_chats[group_name] = {"members": {self.ui.app.settings.nickname}, "messages": [], "files": []}
        self.update_chats_list()
        self.ui.add_system_message(f"📨 Группа '{group_name}' создана!")
        
        # Если есть друзья - предлагаем добавить
        if self.ui.friends_list:
            self.add_members_from_friends(group_name)
    
    def add_members_from_friends(self, group_name):
        """Диалог выбора друзей для добавления в группу"""
        if not self.ui.friends_list:
            self.ui.add_system_message("❌ У вас нет друзей, чтобы добавить в группу")
            return
        
        win = tk.Toplevel(self.ui.app.root)
        win.title(f"Добавить участников в {group_name}")
        win.geometry("350x400")
        win.configure(bg=self.ui.color_manager.get_color('sidebar'))
        win.transient(self.ui.app.root)
        win.grab_set()
        
        tk.Label(win, text=f"Выберите друзей для группы {group_name}", 
                 font=("Segoe UI", 12, "bold"),
                 bg=self.ui.color_manager.get_color('sidebar'), fg='white').pack(pady=15)
        
        listbox = tk.Listbox(win, bg=self.ui.color_manager.get_color('chat_bg'), fg='white',
                             font=("Segoe UI", 11), relief=tk.FLAT, selectmode=tk.MULTIPLE)
        listbox.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        for friend in sorted(self.ui.friends_list):
            listbox.insert(tk.END, f"  👤 {friend}")
        
        def add_selected():
            selected = listbox.curselection()
            for idx in selected:
                friend = listbox.get(idx).replace("  👤 ", "").strip()
                self.ui.app.network.send_raw(f"CMD:ADD_TO_GROUP|{group_name}|{friend}")
                self.ui.add_system_message(f"👥 {friend} добавлен в группу {group_name}")
            win.destroy()
        
        tk.Button(win, text="Добавить выбранных", command=add_selected,
                  bg=self.ui.color_manager.get_color('accent'), fg='white',
                  relief=tk.FLAT, cursor="hand2").pack(pady=15)
        
        tk.Button(win, text="Пропустить", command=win.destroy,
                  bg='#555555', fg='white', relief=tk.FLAT, cursor="hand2").pack(pady=5)
    
    def add_members_to_group(self, group_name):
        """Добавление участников в группу (только из друзей)"""
        from tkinter import messagebox
        
        if not self.ui.friends_list:
            self.ui.add_system_message("❌ У вас нет друзей, которых можно добавить")
            return
        
        # Получаем текущих участников группы из локального кэша
        current_members = self.ui.group_chats.get(group_name, {}).get("members", set())
        print(f"[DEBUG] Текущие участники {group_name}: {current_members}")
        print(f"[DEBUG] Список друзей: {self.ui.friends_list}")
        
        # Отфильтровываем друзей, которые уже в группе
        available_friends = [f for f in self.ui.friends_list 
                            if f not in current_members 
                            and f != self.ui.app.settings.nickname]
        
        print(f"[DEBUG] Доступные для добавления: {available_friends}")
        
        if not available_friends:
            self.ui.add_system_message("❌ Нет доступных друзей для добавления (все уже в группе)")
            return
        
        win = tk.Toplevel(self.ui.app.root)
        win.title(f"Добавить участника в {group_name}")
        win.geometry("350x400")
        win.configure(bg=self.ui.color_manager.get_color('sidebar'))
        win.transient(self.ui.app.root)
        win.grab_set()
        
        tk.Label(win, text=f"Выберите друга для группы {group_name}", 
                 font=("Segoe UI", 12, "bold"),
                 bg=self.ui.color_manager.get_color('sidebar'), fg='white').pack(pady=15)
        
        listbox = tk.Listbox(win, bg=self.ui.color_manager.get_color('chat_bg'), fg='white',
                             font=("Segoe UI", 11), relief=tk.FLAT)
        listbox.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        for friend in sorted(available_friends):
            listbox.insert(tk.END, f"  👤 {friend}")
        
        def add_selected():
            selection = listbox.curselection()
            if not selection:
                win.destroy()
                return
            friend = listbox.get(selection[0]).replace("  👤 ", "").strip()
            self.ui.app.network.send_raw(f"CMD:ADD_TO_GROUP|{group_name}|{friend}")
            self.ui.add_system_message(f"👥 {friend} добавлен в группу {group_name}")
            win.destroy()
        
        tk.Button(win, text="Добавить", command=add_selected,
                  bg=self.ui.color_manager.get_color('accent'), fg='white',
                  relief=tk.FLAT, cursor="hand2").pack(pady=15)
        
        tk.Button(win, text="Закрыть", command=win.destroy,
                  bg='#555555', fg='white', relief=tk.FLAT, cursor="hand2").pack(pady=5)
    
    def show_context_menu(self, event):
        selection = self.chats_listbox.curselection()
        if not selection:
            return
        
        idx = selection[0]
        chat_text = self.chats_listbox.get(idx).strip()
        print(f"[DEBUG] ПКМ по элементу: {chat_text}")  # Отладка
        
        # Если это группа (начинается с 👥)
        if chat_text.startswith("👥"):
            group_name = chat_text.replace("👥", "").strip()
            print(f"[DEBUG] Это группа: {group_name}")  # Отладка
            self.show_group_menu(event, group_name)
        else:
            print(f"[DEBUG] Это не группа, а {chat_text}")
    
    def show_group_menu(self, event, group_name):
        print(f"[DEBUG] Показываем меню для группы {group_name}")  # Отладка
        menu = tk.Menu(self.ui.app.root, tearoff=0, bg='#3c3c3c', fg='white')
        menu.add_command(label="✏️ Изменить название", command=lambda: self.rename_group(group_name))
        menu.add_separator()
        menu.add_command(label="👥 Добавить участников", command=lambda: self.add_members_to_group(group_name))
        menu.add_separator()
        menu.add_command(label="❌ Удалить группу", command=lambda: self.delete_group(group_name))
        menu.tk_popup(event.x_root, event.y_root)
    
    def rename_group(self, old_name):
        new_name = simpledialog.askstring("Изменить название", f"Введите новое название для группы {old_name}:")
        if new_name and new_name.strip():
            # Отправляем запрос на сервер
            self.ui.app.network.send_raw(f"CMD:RENAME_GROUP|{old_name}|{new_name.strip()}")
            # Локально переименовываем
            if old_name in self.ui.group_chats:
                self.ui.group_chats[new_name.strip()] = self.ui.group_chats.pop(old_name)
                self.update_chats_list()
                if self.ui.current_chat == old_name:
                    self.ui.current_chat = new_name.strip()
                    self.ui.top_bar.set_title(f"👥 {new_name.strip()}")
            self.ui.add_system_message(f"✏️ Группа переименована в {new_name.strip()}")
    
    def add_members_to_group(self, group_name):
        """Добавление участников в группу (только из друзей)"""
        if not self.ui.friends_list:
            self.ui.add_system_message("❌ У вас нет друзей, которых можно добавить")
            return
        
        # Получаем текущих участников группы
        current_members = self.ui.group_chats.get(group_name, {}).get("members", set())
        available_friends = [f for f in self.ui.friends_list if f not in current_members and f != self.ui.app.settings.nickname]
        
        if not available_friends:
            self.ui.add_system_message("❌ Нет доступных друзей для добавления")
            return
        
        win = tk.Toplevel(self.ui.app.root)
        win.title(f"Добавить участника в {group_name}")
        win.geometry("350x400")
        win.configure(bg=self.ui.color_manager.get_color('sidebar'))
        win.transient(self.ui.app.root)
        win.grab_set()
        
        tk.Label(win, text=f"Выберите друга для группы {group_name}", 
                 font=("Segoe UI", 12, "bold"),
                 bg=self.ui.color_manager.get_color('sidebar'), fg='white').pack(pady=15)
        
        listbox = tk.Listbox(win, bg=self.ui.color_manager.get_color('chat_bg'), fg='white',
                             font=("Segoe UI", 11), relief=tk.FLAT)
        listbox.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        for friend in sorted(available_friends):
            listbox.insert(tk.END, f"  👤 {friend}")
        
        def add_selected():
            selection = listbox.curselection()
            if not selection:
                win.destroy()
                return
            friend = listbox.get(selection[0]).replace("  👤 ", "").strip()
            self.ui.app.network.send_raw(f"CMD:ADD_TO_GROUP|{group_name}|{friend}")
            self.ui.add_system_message(f"👥 {friend} добавлен в группу {group_name}")
            win.destroy()
        
        tk.Button(win, text="Добавить", command=add_selected,
                  bg=self.ui.color_manager.get_color('accent'), fg='white',
                  relief=tk.FLAT, cursor="hand2").pack(pady=15)
        
        tk.Button(win, text="Закрыть", command=win.destroy,
                  bg='#555555', fg='white', relief=tk.FLAT, cursor="hand2").pack(pady=5)
    
    def delete_group(self, group_name):
        from tkinter import messagebox
        if messagebox.askyesno("Удалить группу", f"Вы уверены, что хотите удалить группу '{group_name}'?\nЭто действие необратимо."):
            # Отправляем запрос на сервер
            self.ui.app.network.send_raw(f"CMD:DELETE_GROUP|{group_name}")
            # Удаляем локально
            if group_name in self.ui.group_chats:
                del self.ui.group_chats[group_name]
                self.update_chats_list()
                if self.ui.current_chat == group_name:
                    self.ui.current_chat = "general"
                    self.ui.current_chat_type = "general"
                    self.ui.top_bar.set_title("💬 Общий чат")
                    self.ui.chat_display.clear_chat()
            self.ui.add_system_message(f"🗑️ Группа '{group_name}' удалена")