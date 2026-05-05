# client/ui/main_window/friends_manager.py
import tkinter as tk
from tkinter import messagebox

class FriendsManager:
    def __init__(self, ui):
        self.ui = ui
    
    def send_friend_request(self, nick):
        if nick in self.ui.friends_list:
            self.ui.add_system_message(f"👤 {nick} уже у вас в друзьях")
            return
        if nick == self.ui.app.settings.nickname:
            self.ui.add_system_message("❌ Нельзя добавить самого себя")
            return
        
        if messagebox.askyesno("Добавить в друзья", f"Отправить запрос в друзья пользователю {nick}?"):
            self.ui.app.network.send_raw(f"CMD:SEND_FRIEND_REQUEST|{nick}")
            self.ui.add_system_message(f"📨 Запрос в друзья отправлен пользователю {nick}")
    
    def add_friend(self, nick):
        self.send_friend_request(nick)
    
    def show_friends(self):
        win = tk.Toplevel(self.ui.app.root)
        win.title("👥 Друзья")
        win.geometry("350x400")
        win.configure(bg=self.ui.color_manager.get_color('sidebar'))
        
        tk.Label(win, text="👥 Список друзей", font=("Segoe UI", 14, "bold"),
                 bg=self.ui.color_manager.get_color('sidebar'), fg='white').pack(pady=15)
        
        listbox = tk.Listbox(win, bg=self.ui.color_manager.get_color('chat_bg'), fg='white',
                             font=("Segoe UI", 11), relief=tk.FLAT)
        listbox.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        if self.ui.friends_list:
            for friend in sorted(self.ui.friends_list):
                listbox.insert(tk.END, f"  👤 {friend}")
        else:
            listbox.insert(tk.END, "  У вас пока нет друзей")
        
        def show_context_menu(event):
            selection = listbox.curselection()
            if not selection:
                return
            friend = listbox.get(selection[0]).replace("  👤 ", "").strip()
            menu = tk.Menu(win, tearoff=0, bg='#3c3c3c', fg='white')
            menu.add_command(label="💬 Написать", command=lambda: [win.destroy(), self.ui.start_private_chat(friend)])
            menu.add_command(label="👤 Посмотреть профиль", command=lambda: [win.destroy(), self.ui.show_user_profile(friend)])
            menu.add_separator()
            menu.add_command(label="❌ Удалить из друзей", command=lambda: remove_friend(friend, listbox))
            menu.tk_popup(event.x_root, event.y_root)
        
        def remove_friend(friend, listbox):
            if messagebox.askyesno("Удалить", f"Удалить {friend} из друзей?"):
                self.ui.friends_list.remove(friend)
                self.ui.save_friends()
                listbox.delete(0, tk.END)
                if self.ui.friends_list:
                    for f in sorted(self.ui.friends_list):
                        listbox.insert(tk.END, f"  👤 {f}")
                else:
                    listbox.insert(tk.END, "  У вас пока нет друзей")
                self.ui.add_system_message(f"❌ {friend} удалён")
        
        listbox.bind("<Button-3>", show_context_menu)
        
        def remove_selected():
            sel = listbox.curselection()
            if sel:
                friend = listbox.get(sel[0]).replace("  👤 ", "").strip()
                remove_friend(friend, listbox)
        
        tk.Button(win, text="Удалить из друзей", command=remove_selected,
                  bg='#f48771', fg='white', relief=tk.FLAT).pack(pady=10)