# client/app.py
import tkinter as tk
from tkinter import messagebox
import sys
import os

from network import NetworkManager
from ui import ChatUI
from settings import AppSettings
from features.typing import TypingIndicator
from features.notifications import NotificationManager
from features.search import SearchManager
from features.hotkeys import HotkeyManager
from features.privacy import PrivacyManager

class ChatApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        
        self.settings = AppSettings()
        self.network = NetworkManager(self)
        self.typing = TypingIndicator(self)
        self.notifications = NotificationManager(self)
        self.search = SearchManager(self)
        self.hotkeys = HotkeyManager(self)
        self.privacy = PrivacyManager(self)
        self.ui = ChatUI(self)

    def run(self):
        self.root.deiconify()
        self.ui.setup_ui()
        self.root.after(500, self.attempt_connect)
        self.root.mainloop()
    
    def attempt_connect(self):
        if not self.network.connect():
            if messagebox.askyesno("Повтор", "Попробовать снова?"):
                self.attempt_connect()
            else:
                self.root.quit()
        else:
            self.typing.check_timeout()