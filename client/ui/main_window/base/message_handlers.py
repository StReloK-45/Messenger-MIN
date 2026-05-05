# client/ui/main_window/base/message_handlers.py
import tkinter as tk
import datetime
import time

class MessageHandlers:
    def __init__(self, ui):
        self.ui = ui
    
    def display_bubble_message(self, sender, text, msg_time, is_my=False):
        """Красивый квадратный пузырь"""
        try:
            if self.ui.ui_components.messages_frame is None:
                return
            
            msg_frame = tk.Frame(self.ui.ui_components.messages_frame,
                                 bg=self.ui.color_manager.get_color('chat_bg'))
            
            if is_my:
                msg_frame.pack(fill=tk.X, pady=4, padx=(100, 10))
                inner = tk.Frame(msg_frame, bg=self.ui.color_manager.get_color('chat_bg'))
                inner.pack(side=tk.RIGHT)
                bubble = tk.Frame(inner, bg=self.ui.color_manager.get_color('my_bubble'),
                                  highlightbackground='#1a4a6e', highlightthickness=1,
                                  padx=10, pady=6)
                bubble.pack()
                
                my_color = self.ui.color_manager.get_nick_color(self.ui.app.settings.nickname)
                tk.Label(bubble, text=self.ui.app.settings.nickname, font=("Segoe UI", 9, "bold"),
                         fg=my_color, bg=self.ui.color_manager.get_color('my_bubble')).pack(anchor='w')
                
                tk.Label(bubble, text=text, font=("Segoe UI", self.ui.app.settings.font_size),
                         fg=self.ui.color_manager.get_color('my_text'),
                         bg=self.ui.color_manager.get_color('my_bubble'),
                         justify=tk.LEFT, wraplength=350, padx=2, pady=4).pack()
                
                tk.Label(bubble, text=msg_time, font=("Segoe UI", 7),
                         fg=self.ui.color_manager.get_color('time'),
                         bg=self.ui.color_manager.get_color('my_bubble')).pack(anchor='e')
            else:
                msg_frame.pack(fill=tk.X, pady=4, padx=(10, 100))
                inner = tk.Frame(msg_frame, bg=self.ui.color_manager.get_color('chat_bg'))
                inner.pack(side=tk.LEFT)
                bubble = tk.Frame(inner, bg=self.ui.color_manager.get_color('other_bubble'),
                                  highlightbackground='#555', highlightthickness=1,
                                  padx=10, pady=6)
                bubble.pack()
                
                nick_color = self.ui.color_manager.get_nick_color(sender)
                nick_label = tk.Label(bubble, text=sender, font=("Segoe UI", 9, "bold"),
                                      fg=nick_color, bg=self.ui.color_manager.get_color('other_bubble'))
                nick_label.pack(anchor='w')
                nick_label.bind("<Button-3>", lambda e, s=sender: self.ui.show_context_menu(e, s))
                
                tk.Label(bubble, text=text, font=("Segoe UI", self.ui.app.settings.font_size),
                         fg=self.ui.color_manager.get_color('other_text'),
                         bg=self.ui.color_manager.get_color('other_bubble'),
                         justify=tk.LEFT, wraplength=350, padx=2, pady=4).pack()
                
                tk.Label(bubble, text=msg_time, font=("Segoe UI", 7),
                         fg=self.ui.color_manager.get_color('time'),
                         bg=self.ui.color_manager.get_color('other_bubble')).pack(anchor='e')
            
            msg_frame.update_idletasks()
            self.ui.scroll_manager.update_scroll_region()
            self.ui.scroll_manager.force_scroll_to_bottom()
            
        except Exception as e:
            print(f"[DEBUG] Ошибка в display_bubble_message: {e}")
    
    def add_system_message(self, text):
        sys_frame = tk.Frame(self.ui.ui_components.messages_frame,
                             bg=self.ui.color_manager.get_color('chat_bg'))
        sys_frame.pack(fill=tk.X, pady=5)
        tk.Label(sys_frame, text=text, font=("Segoe UI", 10, "italic"),
                 fg=self.ui.color_manager.get_color('system'),
                 bg=self.ui.color_manager.get_color('chat_bg')).pack()
        
        self.ui.scroll_manager.update_scroll_region()
        self.ui.scroll_manager.force_scroll_to_bottom()
    
    def send_message(self, event=None):
        if not self.ui.ui_components.message_entry:
            return
        text = self.ui.ui_components.message_entry.get().strip()
        if not text:
            return
        
        self.ui.data_manager._last_msg_text = text
        self.ui.data_manager._last_msg_time = time.time()
        
        if self.ui.data_manager.current_chat == "general":
            self.ui.app.network.send(text)
        elif self.ui.data_manager.current_chat_type == "private":
            # Отправляем, но НЕ отображаем локально - ждём подтверждение от сервера
            self.ui.app.network.send_raw(f"CMD:PM|{self.ui.data_manager.current_chat}|{text}")
        
        self.ui.ui_components.message_entry.delete(0, tk.END)