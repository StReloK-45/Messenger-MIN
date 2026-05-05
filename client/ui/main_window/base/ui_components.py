# client/ui/main_window/base/ui_components.py
import tkinter as tk

class UIComponents:
    def __init__(self, ui):
        self.ui = ui
        self.chat_canvas = None
        self.messages_frame = None
        self.canvas_window = None
        self.message_entry = None
        self.chats_listbox = None
        self.files_listbox = None
        self.status_label = None
        self.chat_header = None
        self.menu_btn = None
        self.scrollbar = None
        self.main_frame = None
        self.scroll_down_btn = None
    
    def setup_ui(self, root):
        """Главный метод создания всего интерфейса"""
        root.title(f"💬 Messenger - {self.ui.app.settings.nickname or 'User'}")
        root.geometry("1100x700")
        root.configure(bg=self.ui.color_manager.get_color('bg'))
        root.minsize(900, 500)
        
        # ========== ВЕРХНЯЯ ПАНЕЛЬ ==========
        top_bar = tk.Frame(root, bg=self.ui.color_manager.get_color('top_bar'), height=50)
        top_bar.pack(fill=tk.X, side=tk.TOP)
        top_bar.pack_propagate(False)
        
        self.menu_btn = tk.Button(top_bar, text="☰", font=("Segoe UI", 16),
                                  bg=self.ui.color_manager.get_color('top_bar'),
                                  fg=self.ui.color_manager.get_color('text'),
                                  relief=tk.FLAT, cursor="hand2", bd=0,
                                  command=self.ui.open_menu)
        self.menu_btn.pack(side=tk.LEFT, padx=15, pady=8)
        
        tk.Label(top_bar, text=self.ui.app.settings.nickname or "User",
                 font=("Segoe UI", 12, "bold"),
                 bg=self.ui.color_manager.get_color('top_bar'),
                 fg=self.ui.color_manager.get_color('text')).pack(side=tk.LEFT)
        
        self.status_label = tk.Label(top_bar, text="🟢 онлайн",
                                     font=("Segoe UI", 9),
                                     bg=self.ui.color_manager.get_color('top_bar'), fg='#6a9955')
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        tk.Button(top_bar, text="🔍", font=("Segoe UI", 14),
                  bg=self.ui.color_manager.get_color('top_bar'),
                  fg=self.ui.color_manager.get_color('text'),
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self.ui.open_search).pack(side=tk.RIGHT, padx=15)
        
        # ========== ОСНОВНАЯ ОБЛАСТЬ ==========
        self.main_frame = tk.Frame(root, bg=self.ui.color_manager.get_color('bg'))
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ========== ЛЕВАЯ ПАНЕЛЬ ==========
        left_panel = tk.Frame(self.main_frame, bg=self.ui.color_manager.get_color('sidebar'), width=270)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)
        
        tk.Label(left_panel, text="💬 Чаты", font=("Segoe UI", 14, "bold"),
                 bg=self.ui.color_manager.get_color('sidebar'),
                 fg=self.ui.color_manager.get_color('text')).pack(pady=15)
        
        self.chats_listbox = tk.Listbox(left_panel, bg=self.ui.color_manager.get_color('chat_bg'),
                                        fg=self.ui.color_manager.get_color('text'),
                                        font=("Segoe UI", 11),
                                        relief=tk.FLAT, selectbackground=self.ui.color_manager.get_color('accent'),
                                        selectforeground='white', borderwidth=0)
        self.chats_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.chats_listbox.insert(tk.END, "  💬 Общий чат")
        self.chats_listbox.bind('<<ListboxSelect>>', self.ui.on_chat_select)
        
        btn_frame = tk.Frame(left_panel, bg=self.ui.color_manager.get_color('sidebar'))
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        tk.Button(btn_frame, text="🎨 Цвет ника", font=("Segoe UI", 10),
                  bg=self.ui.color_manager.get_color('accent'), fg='white', relief=tk.FLAT,
                  cursor="hand2", command=self.ui.change_nick_color).pack(fill=tk.X, pady=2)
        
        tk.Button(btn_frame, text="🔄 Обновить файлы", font=("Segoe UI", 10),
                  bg='#6a9955', fg='white', relief=tk.FLAT,
                  cursor="hand2", command=self.ui.load_files).pack(fill=tk.X, pady=2)
        
        tk.Button(btn_frame, text="👥 Создать группу", font=("Segoe UI", 10),
                  bg='#9c3e9c', fg='white', relief=tk.FLAT,
                  cursor="hand2", command=self.ui.create_group_dialog).pack(fill=tk.X, pady=2)
        
        # ========== ПРАВАЯ ПАНЕЛЬ ==========
        right_panel = tk.Frame(self.main_frame, bg=self.ui.color_manager.get_color('sidebar'), width=240)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)
        
        tk.Label(right_panel, text="📁 Файлы", font=("Segoe UI", 14, "bold"),
                 bg=self.ui.color_manager.get_color('sidebar'),
                 fg=self.ui.color_manager.get_color('text')).pack(pady=15)
        
        self.files_listbox = tk.Listbox(right_panel, bg=self.ui.color_manager.get_color('chat_bg'),
                                        fg=self.ui.color_manager.get_color('text'), font=("Segoe UI", 10),
                                        relief=tk.FLAT, selectbackground=self.ui.color_manager.get_color('accent'),
                                        borderwidth=0)
        self.files_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.files_listbox.insert(tk.END, "📁 Файлов пока нет")
        self.files_listbox.bind("<Double-Button-1>", self.ui.download_file)
        
        # ========== ЦЕНТРАЛЬНАЯ ПАНЕЛЬ ==========
        center_panel = tk.Frame(self.main_frame, bg=self.ui.color_manager.get_color('chat_bg'))
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.chat_header = tk.Label(center_panel, text="💬 Общий чат",
                                    font=("Segoe UI", 14, "bold"),
                                    bg=self.ui.color_manager.get_color('chat_bg'),
                                    fg=self.ui.color_manager.get_color('text'),
                                    anchor='w', padx=20, height=2)
        self.chat_header.pack(fill=tk.X)
        
        tk.Frame(center_panel, bg='#444', height=1).pack(fill=tk.X)
        
        # Canvas для сообщений
        self.chat_canvas = tk.Canvas(center_panel, bg=self.ui.color_manager.get_color('chat_bg'),
                                     highlightthickness=0, bd=0)
        self.chat_canvas.pack(fill=tk.BOTH, expand=True)
        
        self.messages_frame = tk.Frame(self.chat_canvas, bg=self.ui.color_manager.get_color('chat_bg'))
        self.canvas_window = self.chat_canvas.create_window((0, 0), window=self.messages_frame,
                                                             anchor=tk.NW, width=self.chat_canvas.winfo_width())
        
        self.messages_frame.bind("<Configure>", self.ui.scroll_manager.on_frame_configure)
        self.chat_canvas.bind("<Configure>", self.ui.scroll_manager.on_canvas_configure)
        
        # Настройка прокрутки
        self.ui.scroll_manager.setup_scroll(self.chat_canvas, self.messages_frame)
        
        # ===== КНОПКА ПРОКРУТКИ ВНИЗ =====
        self.scroll_down_btn = tk.Button(
            center_panel, 
            text="↓", 
            font=("Segoe UI", 14, "bold"),
            bg=self.ui.color_manager.get_color('accent'), 
            fg='white',
            relief=tk.FLAT, 
            cursor="hand2",
            bd=0,
            command=self.ui.scroll_manager.scroll_to_bottom_click
        )
        self.scroll_down_btn.place(relx=0.95, rely=0.92, anchor='se')
        self.scroll_down_btn.config(width=3, height=1, bd=0, highlightthickness=0)
        self.scroll_down_btn.lower()
        # =================================
        
        tk.Frame(center_panel, bg='#444', height=1).pack(fill=tk.X)
        
        # ========== ПОЛЕ ВВОДА ==========
        input_frame = tk.Frame(center_panel, bg=self.ui.color_manager.get_color('chat_bg'), height=55)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        input_frame.pack_propagate(False)
        
        input_bg = tk.Frame(input_frame, bg=self.ui.color_manager.get_color('input_bg'))
        input_bg.pack(fill=tk.X, padx=15, pady=8)
        
        tk.Button(input_bg, text="😊", font=("Segoe UI Emoji", 16),
                  bg=self.ui.color_manager.get_color('input_bg'),
                  fg=self.ui.color_manager.get_color('text'),
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self.ui.add_emoji).pack(side=tk.LEFT, padx=(5, 0), pady=2)
        
        self.message_entry = tk.Entry(input_bg,
                                      font=("Segoe UI", self.ui.app.settings.font_size),
                                      bg=self.ui.color_manager.get_color('input_bg'),
                                      fg=self.ui.color_manager.get_color('text'),
                                      relief=tk.FLAT, bd=0,
                                      insertbackground=self.ui.color_manager.get_color('text'))
        self.message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=2)
        self.message_entry.bind("<Return>", self.ui.send_message)
        
        tk.Button(input_bg, text="📎", font=("Segoe UI", 14),
                  bg=self.ui.color_manager.get_color('input_bg'),
                  fg=self.ui.color_manager.get_color('text'),
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self.ui.send_file).pack(side=tk.RIGHT, padx=(0, 5), pady=2)
        
        tk.Button(input_bg, text="📤", font=("Segoe UI", 14),
                  bg=self.ui.color_manager.get_color('accent'), fg='white',
                  relief=tk.FLAT, cursor="hand2", bd=0,
                  command=self.ui.send_message).pack(side=tk.RIGHT, padx=(0, 5), pady=2)
        
        # Передаём ссылки
        self.ui.left_panel.chats_listbox = self.chats_listbox
        self.ui.right_panel.files_listbox = self.files_listbox
        self.ui.top_bar.status_label = self.status_label
        self.ui.top_bar.chat_header = self.chat_header
        self.ui.chat_canvas = self.chat_canvas
        self.ui.messages_frame = self.messages_frame
        self.ui.canvas_window = self.canvas_window
        self.ui.messages_frame = self.messages_frame
        self.ui.canvas_window = self.canvas_window
        
        # Принудительное обновление
        self.chat_canvas.update_idletasks()
        self.messages_frame.update_idletasks()