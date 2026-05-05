# client/features/notifications.py
import time

class NotificationManager:
    def __init__(self, app):
        self.app = app
        self.last_notification = {}
        self.notification_cooldown = 3
    
    def get_main_window(self):
        """Возвращает главное окно"""
        if hasattr(self.app, 'main_window') and self.app.main_window:
            return self.app.main_window
        return None
    
    def flash_taskbar(self):
        """Мигает задачей в панели задач Windows"""
        try:
            import ctypes
            window = self.get_main_window()
            if window:
                hwnd = window.winfo_id()
                ctypes.windll.user32.FlashWindow(hwnd, True)
        except:
            pass
    
    def notify_new_message(self, sender, chat_type="general"):
        """Уведомление о новом сообщении"""
        current_time = time.time()
        
        if sender in self.last_notification:
            if current_time - self.last_notification[sender] < self.notification_cooldown:
                return
        
        self.last_notification[sender] = current_time
        
        try:
            window = self.get_main_window()
            if not window:
                return
            
            is_focused = window.focus_get() is not None
            if not is_focused:
                self.flash_taskbar()
            
            old_title = window.title()
            if chat_type == "private":
                window.title(f"💬 Новое сообщение от {sender}!")
                window.after(5000, lambda: window.title(old_title))
        except:
            pass
    
    def show_desktop_notification(self, title, message):
        pass
    
    def clear_notifications(self):
        self.last_notification.clear()