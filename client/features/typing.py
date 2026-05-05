# client/features/typing.py
import time

class TypingIndicator:
    def __init__(self, app):
        self.app = app
        self.typing_users = {}
    
    def user_typing(self, nick):
        self.typing_users[nick] = time.time()
    
    def send_typing(self, chat_type="general", target=None):
        if self.app.authenticated:
            if chat_type == "general":
                self.app.send_raw("CMD:TYPING|general")
            elif chat_type == "private" and target:
                self.app.send_raw(f"CMD:TYPING|{target}")
    
    def check_timeout(self):
        pass