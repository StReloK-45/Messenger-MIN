# client/features/search.py
import tkinter as tk

class SearchManager:
    def __init__(self, app):
        self.app = app
        self.window = None
    
    def get_main_window(self):
        if hasattr(self.app, 'main_window') and self.app.main_window:
            return self.app.main_window
        return None
    
    def open_panel(self):
        if self.window and self.window.winfo_exists():
            self.window.lift()
            return
        
        parent = self.get_main_window()
        if not parent:
            return
        
        self.window = tk.Toplevel(parent)
        self.window.title("🔍 Поиск")
        self.window.geometry("400x300")
        self.window.configure(bg='#2d2d2d')
        
        tk.Label(self.window, text="Поиск по сообщениям", font=("Segoe UI", 14, "bold"),
                 bg='#2d2d2d', fg='white').pack(pady=10)
        
        self.entry = tk.Entry(self.window, bg='#3c3c3c', fg='white', font=("Segoe UI", 11))
        self.entry.pack(fill=tk.X, padx=20, pady=10)
        self.entry.bind("<KeyRelease>", self.search)
        
        self.listbox = tk.Listbox(self.window, bg='#3c3c3c', fg='white')
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    def search(self, event=None):
        query = self.entry.get().strip().lower()
        self.listbox.delete(0, tk.END)
        
        if not query or not self.app.ui:
            return
        
        for msg in self.app.ui.message_history:
            if query in msg.get('text', '').lower():
                sender = msg.get('sender', '')
                text = msg.get('text', '')[:50]
                self.listbox.insert(tk.END, f"{sender}: {text}")