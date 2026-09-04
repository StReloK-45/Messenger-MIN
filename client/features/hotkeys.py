# client/features/hotkeys.py
import tkinter as tk

class HotkeyManager:
    def __init__(self, app):
        self.app = app
        self.history_index = -1
        self.history_buffer = []
        self.register()
    
    def register(self):
        # Привязываем горячие клавиши к главному окну после его создания
        # Пока нет главного окна - пропускаем
        pass
    
    def register_to_window(self, window):
        """Привязывает горячие клавиши к указанному окну"""
        if not window:
            return
        
        window.bind('<Control-f>', lambda e: self.open_search())
        window.bind('<Control-F>', lambda e: self.open_search())
        window.bind('<Control-n>', lambda e: self.create_group())
        window.bind('<Control-N>', lambda e: self.create_group())
        window.bind('<Control-l>', lambda e: self.refresh_files())
        window.bind('<Control-L>', lambda e: self.refresh_files())
        window.bind('<F5>', lambda e: self.refresh_chats())
        window.bind('<Escape>', lambda e: self.close_menu())
        window.bind('<Control-w>', lambda e: self.quit_app())
        window.bind('<Control-W>', lambda e: self.quit_app())
        window.bind('<Control-plus>', lambda e: self.increase_font())
        window.bind('<Control-minus>', lambda e: self.decrease_font())
        window.bind('<Control-=>', lambda e: self.increase_font())
        window.bind('<Up>', self.history_up)
        window.bind('<Down>', self.history_down)
    
    def open_search(self):
        if hasattr(self.app, 'search') and self.app.search:
            self.app.search.open_panel()
    
    def create_group(self):
        if hasattr(self.app, 'ui') and self.app.ui:
            self.app.ui.create_group_dialog()
    
    def refresh_files(self):
        if hasattr(self.app, 'ui') and self.app.ui:
            self.app.ui.load_files()
    
    def refresh_chats(self):
        if hasattr(self.app, 'ui') and self.app.ui:
            self.app.ui.update_chats_list()
    
    def close_menu(self):
        if hasattr(self.app, 'ui') and self.app.ui and hasattr(self.app.ui, 'sidebar_menu'):
            self.app.ui.sidebar_menu.close()
    
    def quit_app(self):
        self.app.auth_window.quit()
    
    def increase_font(self):
        if hasattr(self.app, 'settings'):
            if self.app.settings.font_size < 16:
                self.app.settings.font_size += 1
                self.app.settings.save()
                if hasattr(self.app, 'ui') and self.app.ui:
                    self.app.ui.theme_manager.change_font_size()
    
    def decrease_font(self):
        if hasattr(self.app, 'settings'):
            if self.app.settings.font_size > 8:
                self.app.settings.font_size -= 1
                self.app.settings.save()
                if hasattr(self.app, 'ui') and self.app.ui:
                    self.app.ui.theme_manager.change_font_size()
    
    def history_up(self, event):
        if hasattr(self.app, 'ui') and self.app.ui and hasattr(self.app.ui, '_last_msg_text'):
            if self.history_index == -1 and self.app.ui._last_msg_text:
                self.history_buffer.insert(0, self.app.ui._last_msg_text)
                self.history_index = 0
            elif self.history_index < len(self.history_buffer) - 1:
                self.history_index += 1
            
            if self.history_index < len(self.history_buffer):
                if hasattr(self.app.ui, 'message_entry'):
                    self.app.ui.message_entry.delete(0, tk.END)
                    self.app.ui.message_entry.insert(0, self.history_buffer[self.history_index])
    
    def history_down(self, event):
        if self.history_index >= 0:
            self.history_index -= 1
            if self.history_index >= 0 and hasattr(self.app, 'ui') and self.app.ui:
                if hasattr(self.app.ui, 'message_entry'):
                    self.app.ui.message_entry.delete(0, tk.END)
                    self.app.ui.message_entry.insert(0, self.history_buffer[self.history_index])
            else:
                if hasattr(self.app, 'ui') and self.app.ui and hasattr(self.app.ui, 'message_entry'):
                    self.app.ui.message_entry.delete(0, tk.END)