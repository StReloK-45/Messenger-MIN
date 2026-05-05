# client/ui/main_window/right_panel.py
import tkinter as tk
from tkinter import messagebox, filedialog
import socket
import struct
import json
import threading
import os

class RightPanel:
    def __init__(self, ui):
        self.ui = ui
        self.files_listbox = None
        self.files_list = []
    
    def setup(self):
        self.files_listbox = self.ui.ui_components.files_listbox
    
    def update_files_list(self):
        self.files_listbox.delete(0, tk.END)
        
        if self.ui.current_chat_type == "general":
            files = self.ui.files_list
        elif self.ui.current_chat_type == "private":
            files = self.ui.private_files.get(self.ui.current_chat, [])
        else:
            files = []
        
        if not files:
            self.files_listbox.insert(tk.END, "📁 Файлов пока нет")
        else:
            for f in files:
                size_kb = f.get('size', 0) / 1024
                size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
                self.files_listbox.insert(tk.END, f"📁 {f.get('name', 'unknown')} ({size_str})")
    
    def load_files(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.ui.app.settings.server_ip, self.ui.file_port))
            
            if self.ui.current_chat_type == "general":
                sock.send(b'L')
            else:
                sock.send(b'P')
                nick_bytes = self.ui.current_chat.encode('utf-8')
                sock.send(struct.pack('>I', len(nick_bytes)))
                sock.send(nick_bytes)
            
            size_data = self._recv_exact(sock, 4)
            if size_data:
                size = struct.unpack('>I', size_data)[0]
                data = self._recv_exact(sock, size)
                if data:
                    files = json.loads(data.decode('utf-8', errors='ignore'))
                    if self.ui.current_chat_type == "general":
                        self.ui.files_list = files
                    elif self.ui.current_chat_type == "private":
                        if self.ui.current_chat not in self.ui.private_files:
                            self.ui.private_files[self.ui.current_chat] = []
                        self.ui.private_files[self.ui.current_chat] = files
                    self.update_files_list()
                    self.ui.add_system_message("🔄 Список файлов обновлён")
            
            sock.close()
        except Exception as e:
            print(f"Ошибка загрузки файлов: {e}")
    
    def download_file(self, event=None):
        selection = self.files_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        
        if self.ui.current_chat_type == "general":
            files = self.ui.files_list
        elif self.ui.current_chat_type == "private":
            files = self.ui.private_files.get(self.ui.current_chat, [])
        else:
            return
        
        if idx >= len(files):
            return
        
        file_info = files[idx]
        if messagebox.askyesno("Скачать файл", f"Скачать файл '{file_info['name']}'?"):
            threading.Thread(target=self._download, args=(file_info,), daemon=True).start()
    
    def _download(self, file_info):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(60)
            sock.connect((self.ui.app.settings.server_ip, self.ui.file_port))
            
            sock.send(b'D')
            id_bytes = file_info['id'].encode('utf-8')
            sock.send(struct.pack('>I', len(id_bytes)))
            sock.send(id_bytes)
            
            response = sock.recv(1)
            if response != b'K':
                self.ui.app.root.after(0, lambda: self.ui.add_system_message("❌ Файл не найден"))
                sock.close()
                return
            
            size_data = self._recv_exact(sock, 8)
            filesize = struct.unpack('>Q', size_data)[0]
            name_len_data = self._recv_exact(sock, 4)
            name_len = struct.unpack('>I', name_len_data)[0]
            filename = self._recv_exact(sock, name_len).decode('utf-8')
            
            save_path = filedialog.asksaveasfilename(title="Сохранить файл", initialfile=filename)
            if save_path:
                with open(save_path, 'wb') as f:
                    received = 0
                    while received < filesize:
                        data = sock.recv(min(8192, filesize - received))
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                self.ui.app.root.after(0, lambda: self.ui.add_system_message(f"✅ Файл сохранён: {os.path.basename(save_path)}"))
            sock.close()
        except Exception as e:
            self.ui.app.root.after(0, lambda: self.ui.add_system_message(f"❌ Ошибка: {e}"))
    
    def _recv_exact(self, sock, size):
        data = b''
        while len(data) < size:
            packet = sock.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data
    
    def send_file(self):
        file_path = filedialog.askopenfilename(title="Выберите файл")
        if not file_path:
            return
        
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)
        
        if filesize > 250 * 1024 * 1024:
            self.ui.add_system_message("❌ Файл слишком большой (макс 250MB)")
            return
        
        self.ui.add_system_message(f"⏳ Отправка файла '{filename}'...")
        threading.Thread(target=self._upload_file, args=(file_path, filename, filesize), daemon=True).start()
    
    def _upload_file(self, file_path, filename, filesize):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(60)
            sock.connect((self.ui.app.settings.server_ip, self.ui.file_port))
            
            if self.ui.current_chat_type == "general":
                sock.send(b'U')
            else:
                sock.send(b'V')
                target_bytes = self.ui.current_chat.encode('utf-8')
                sock.send(struct.pack('>I', len(target_bytes)))
                sock.send(target_bytes)
            
            name_bytes = filename.encode('utf-8')
            sock.send(struct.pack('>I', len(name_bytes)))
            sock.send(name_bytes)
            sock.send(struct.pack('>Q', filesize))
            sock.send(struct.pack('>I', len(self.ui.app.settings.nickname.encode('utf-8'))))
            sock.send(self.ui.app.settings.nickname.encode('utf-8'))
            
            response = sock.recv(1)
            if response != b'K':
                self.ui.app.root.after(0, lambda: self.ui.add_system_message("❌ Сервер не принял файл"))
                sock.close()
                return
            
            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(8192)
                    if not data:
                        break
                    sock.send(data)
            
            sock.close()
            self.ui.app.root.after(0, lambda: self.ui.add_system_message(f"📤 Файл '{filename}' отправлен ({filesize/1024:.1f} KB)"))
        except Exception as e:
            self.ui.app.root.after(0, lambda: self.ui.add_system_message(f"❌ Ошибка отправки: {e}"))