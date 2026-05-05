# client/ui/main_window/chat_display.py
class ChatDisplay:
    def __init__(self, ui):
        self.ui = ui
    
    def display_bubble_message(self, sender, text, msg_time, is_my=False):
        """Отображает сообщение в виде красивого пузыря"""
        self.ui.scroll_manager.insert_message(sender, text, msg_time, is_my)
    
    def add_system_message(self, text):
        """Добавляет системное сообщение"""
        self.ui.scroll_manager.insert_system_message(text)
    
    def clear_chat(self):
        """Очищает чат"""
        self.ui.scroll_manager.clear_chat()
    
    def update_font_size(self, size):
        """Обновляет размер шрифта"""
        self.ui.scroll_manager.update_font_size(size)