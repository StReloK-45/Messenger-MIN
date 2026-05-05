# client/features/privacy.py
class PrivacyManager:
    def __init__(self, app):
        self.app = app
        self.blocked = set()
        self.load_blocked()
    
    def load_blocked(self):
        if hasattr(self.app.settings, 'blocked_users'):
            self.blocked = set(self.app.settings.blocked_users)
    
    def block_user(self, nick):
        if nick not in self.blocked:
            self.blocked.add(nick)
            self.app.settings.blocked_users = list(self.blocked)
            self.app.settings.save()
            if self.app.ui:
                self.app.ui.add_system_message(f"🔒 {nick} заблокирован")
    
    def unblock_user(self, nick):
        if nick in self.blocked:
            self.blocked.remove(nick)
            self.app.settings.blocked_users = list(self.blocked)
            self.app.settings.save()
            if self.app.ui:
                self.app.ui.add_system_message(f"✅ {nick} разблокирован")
    
    def is_blocked(self, nick):
        return nick in self.blocked
    
    def can_send_private_message(self, from_nick, to_nick):
        if self.is_blocked(from_nick):
            return False
        return True