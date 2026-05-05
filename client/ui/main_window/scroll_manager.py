# client/ui/main_window/scroll_manager.py
import tkinter as tk

class ScrollManager:
    def __init__(self, ui):
        self.ui = ui
        self.auto_scroll = True
        self.chat_canvas = None
        self.messages_frame = None
        self.scrollbar = None
        self._check_after = None
    
    def setup_scroll(self, canvas, messages_frame):
        self.chat_canvas = canvas
        self.messages_frame = messages_frame
        
        self.scrollbar = tk.Scrollbar(self.chat_canvas, orient=tk.VERTICAL)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_canvas.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.chat_canvas.yview)
        
        self.chat_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.chat_canvas.bind("<Button-4>", self._on_mousewheel)
        self.chat_canvas.bind("<Button-5>", self._on_mousewheel)
        self.ui.app.root.bind("<MouseWheel>", self._on_root_mousewheel)
    
    def _on_root_mousewheel(self, event):
        self._on_mousewheel(event)
    
    def _on_mousewheel(self, event):
        if hasattr(event, 'delta'):
            delta = event.delta
        elif hasattr(event, 'num'):
            delta = -1 if event.num == 4 else 1 if event.num == 5 else 0
        else:
            delta = 0
        
        if delta > 0:
            self.auto_scroll = False
        
        if delta != 0:
            if hasattr(event, 'delta'):
                self.chat_canvas.yview_scroll(int(-1 * (delta / 120)), "units")
            else:
                self.chat_canvas.yview_scroll(-1 if delta > 0 else 1, "units")
        
        if self._check_after:
            self.ui.app.root.after_cancel(self._check_after)
        self._check_after = self.ui.app.root.after(100, self._check_scroll_position)
        return "break"
    
    def _check_scroll_position(self):
        try:
            current_pos = self.chat_canvas.yview()
            if current_pos[1] >= 0.99:
                self.auto_scroll = True
                self._hide_scroll_button()
            else:
                self._show_scroll_button()
        except:
            pass
        finally:
            self._check_after = None
    
    def _show_scroll_button(self):
        btn = self.ui.ui_components.scroll_down_btn
        if btn:
            btn.lift()
            if not btn.winfo_ismapped():
                btn.place(relx=0.95, rely=0.92, anchor='se')
    
    def _hide_scroll_button(self):
        btn = self.ui.ui_components.scroll_down_btn
        if btn:
            btn.lower()
    
    def scroll_to_bottom_click(self):
        self.auto_scroll = True
        if self.chat_canvas:
            self.chat_canvas.yview_moveto(1.0)
            self.update_scroll_region()
            self._hide_scroll_button()
    
    def force_scroll_to_bottom(self):
        self.auto_scroll = True
        if self.chat_canvas:
            self.ui.app.root.after(50, lambda: self.chat_canvas.yview_moveto(1.0))
            self.update_scroll_region()
            self._hide_scroll_button()
    
    def update_scroll_region(self):
        if self.chat_canvas:
            self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
    
    def on_frame_configure(self, event):
        self.update_scroll_region()
    
    def on_canvas_configure(self, event):
        if hasattr(self.ui, 'canvas_window'):
            self.chat_canvas.itemconfig(self.ui.canvas_window, width=event.width)