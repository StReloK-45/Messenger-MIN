# client/ui/main_window/base/color_manager.py
import hashlib
import colorsys

class ColorManager:
    def __init__(self, app):
        self.app = app
        self.nick_colors = {}
    
    def get_color(self, key):
        return self.app.settings.get_color(key)
    
    def get_nick_color(self, nick):
        if nick not in self.nick_colors:
            hash_val = int(hashlib.md5(nick.encode()).hexdigest()[:6], 16)
            hue = hash_val % 360
            r, g, b = colorsys.hls_to_rgb(hue/360.0, 0.6, 0.75)
            self.nick_colors[nick] = f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'
        return self.nick_colors[nick]