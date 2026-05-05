# client/ui/main_window/top_bar.py
import tkinter as tk

class TopBar:
    def __init__(self, ui):
        self.ui = ui
        self.title_label = None
        self.status_label = None
        self.menu_btn = None
        self.chat_header = None
        self.add_member_btn = None
    
    def setup(self, parent):
        top_bar = tk.Frame(parent, bg=self.ui.color_manager.get_color('top_bar'), height=50)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)
        
        self.menu_btn = tk.Button(top_bar, text="☰", font=("Segoe UI", 16),
                                  bg=self.ui.color_manager.get_color('top_bar'),
                                  fg=self.ui.color_manager.get_color('text'),
                                  relief=tk.FLAT, cursor="hand2", bd=0,
                                  command=self.ui.open_menu)
        self.menu_btn.pack(side=tk.LEFT, padx=15, pady=8)
        
        self.title_label = tk.Label(top_bar, text=self.ui.app.settings.nickname or "User",
                                    font=("Segoe UI", 12, "bold"),
                                    bg=self.ui.color_manager.get_color('top_bar'),
                                    fg=self.ui.color_manager.get_color('text'))
        self.title_label.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(top_bar, text="🟢 онлайн",
                                     font=("Segoe UI", 9),
                                     bg=self.ui.color_manager.get_color('top_bar'), fg='#6a9955')
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Кнопка добавления участников (будет видна только в группах)
        self.add_member_btn = tk.Button(top_bar, text="➕", font=("Segoe UI", 14),
                                        bg=self.ui.color_manager.get_color('accent'), 
                                        fg='white',
                                        relief=tk.FLAT, cursor="hand2", bd=0,
                                        command=self.add_member)
        self.add_member_btn.pack(side=tk.LEFT, padx=10)
        self.add_member_btn.pack_forget()  # Скрываем изначально
        
        tk.Button(top_bar, text="🔍", font=("Segoe UI", 14),
                  bg=self.ui.color_manager.get_color('top_bar'),
                  fg=self.ui.color_manager.get_color('text'),
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self.open_search).pack(side=tk.RIGHT, padx=15)
    
    def open_search(self):
        if hasattr(self.ui.app, 'search') and self.ui.app.search:
            self.ui.app.search.open_panel()
    
    def add_member(self):
        """Добавление участника в текущую группу (только из друзей)"""
        if self.ui.current_chat_type != "group":
            return
        
        if not self.ui.friends_list:
            self.ui.add_system_message("❌ У вас нет друзей, которых можно добавить")
            return
        
        win = tk.Toplevel(self.ui.app.root)
        win.title(f"Добавить участника в {self.ui.current_chat}")
        win.geometry("350x400")
        win.configure(bg=self.ui.color_manager.get_color('sidebar'))
        win.transient(self.ui.app.root)
        win.grab_set()
        
        tk.Label(win, text=f"Выберите друга для группы {self.ui.current_chat}", 
                 font=("Segoe UI", 12, "bold"),
                 bg=self.ui.color_manager.get_color('sidebar'), fg='white').pack(pady=15)
        
        # Показываем только тех друзей, кто ещё не в группе
        current_members = self.ui.group_chats.get(self.ui.current_chat, {}).get("members", set())
        available_friends = [f for f in self.ui.friends_list if f not in current_members and f != self.ui.app.settings.nickname]
        
        if not available_friends:
            tk.Label(win, text="Нет доступных друзей для добавления",
                     bg=self.ui.color_manager.get_color('sidebar'), fg='#f48771').pack(pady=20)
            tk.Button(win, text="Закрыть", command=win.destroy,
                      bg=self.ui.color_manager.get_color('accent'), fg='white',
                      relief=tk.FLAT, cursor="hand2").pack(pady=10)
            return
        
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
            self.ui.app.network.send_raw(f"CMD:ADD_TO_GROUP|{self.ui.current_chat}|{friend}")
            self.ui.add_system_message(f"👥 {friend} добавлен в группу {self.ui.current_chat}")
            win.destroy()
        
        tk.Button(win, text="Добавить", command=add_selected,
                  bg=self.ui.color_manager.get_color('accent'), fg='white',
                  relief=tk.FLAT, cursor="hand2").pack(pady=15)
    
    def set_title(self, title):
        self.title_label.config(text=title)
        if self.chat_header:
            self.chat_header.config(text=title)
        
        # Показываем кнопку добавления участников только для групп
        if self.ui.current_chat_type == "group":
            self.add_member_btn.pack(side=tk.LEFT, padx=10)
        else:
            self.add_member_btn.pack_forget()
    
    def set_status(self, status):
        self.status_label.config(text=status)