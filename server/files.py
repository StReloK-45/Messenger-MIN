# server/files.py
import struct
import json
import os
import re
import hashlib
from datetime import datetime

class FileManager:
    def __init__(self, server):
        self.server = server
    
    def recv_exact(self, sock, size):
        data = b''
        while len(data) < size:
            packet = sock.recv(size - len(data))
            if not packet:
                return None
            data += packet
        return data
    
    def handle_file(self, file_socket, addr):
        try:
            file_socket.settimeout(60)
            
            cmd_byte = file_socket.recv(1)
            if not cmd_byte:
                file_socket.close()
                return
            
            cmd = cmd_byte.decode('utf-8', errors='ignore')
            
            if cmd == 'L':
                general_files = [f for f in self.server.storage.files_list if f.get('chat', 'general') == 'general']
                files_json = json.dumps(general_files, ensure_ascii=True).encode('utf-8')
                file_socket.send(struct.pack('>I', len(files_json)))
                file_socket.send(files_json)
                self.server.log(f"📋 Список общих файлов: {len(general_files)}", "system")
            
            elif cmd == 'P':
                nick_len_data = self.recv_exact(file_socket, 4)
                if not nick_len_data:
                    file_socket.close()
                    return
                nick_len = struct.unpack('>I', nick_len_data)[0]
                nick = self.recv_exact(file_socket, nick_len).decode('utf-8')
                
                private_files = [f for f in self.server.storage.files_list if f.get('chat') == nick]
                files_json = json.dumps(private_files, ensure_ascii=True).encode('utf-8')
                file_socket.send(struct.pack('>I', len(files_json)))
                file_socket.send(files_json)
                self.server.log(f"📋 Личные файлы для {nick}: {len(private_files)}", "system")
            
            elif cmd == 'D':
                id_len_data = self.recv_exact(file_socket, 4)
                if not id_len_data:
                    file_socket.close()
                    return
                id_len = struct.unpack('>I', id_len_data)[0]
                file_id = self.recv_exact(file_socket, id_len).decode('utf-8')
                
                found = False
                for f in self.server.storage.files_list:
                    if f['id'] == file_id:
                        file_socket.send(b'K')
                        file_socket.send(struct.pack('>Q', f['size']))
                        name_bytes = f['name'].encode('utf-8')
                        file_socket.send(struct.pack('>I', len(name_bytes)))
                        file_socket.send(name_bytes)
                        
                        with open(f['path'], 'rb') as file:
                            while True:
                                data = file.read(8192)
                                if not data:
                                    break
                                file_socket.send(data)
                        self.server.log(f"📤 Файл {f['name']} отправлен", "system")
                        found = True
                        break
                
                if not found:
                    file_socket.send(b'E')
            
            elif cmd == 'U':
                name_len_data = self.recv_exact(file_socket, 4)
                if not name_len_data:
                    file_socket.close()
                    return
                name_len = struct.unpack('>I', name_len_data)[0]
                filename = self.recv_exact(file_socket, name_len).decode('utf-8')
                
                size_data = self.recv_exact(file_socket, 8)
                filesize = struct.unpack('>Q', size_data)[0]
                
                sender_len_data = self.recv_exact(file_socket, 4)
                if not sender_len_data:
                    file_socket.close()
                    return
                sender_len = struct.unpack('>I', sender_len_data)[0]
                sender = self.recv_exact(file_socket, sender_len).decode('utf-8')
                
                self.server.log(f"📥 Общий файл от {sender}: {filename} ({filesize/1024:.1f} KB)", "system")
                
                file_socket.send(b'K')
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
                base, ext = os.path.splitext(safe_filename)
                save_path = os.path.join(self.server.config.RECEIVED_FILES_DIR, f"{base}_{timestamp}{ext}")
                
                received = 0
                with open(save_path, 'wb') as f:
                    while received < filesize:
                        data = file_socket.recv(min(8192, filesize - received))
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                
                file_id = hashlib.md5(f"{filename}{timestamp}{sender}".encode()).hexdigest()[:8]
                file_info = {
                    'id': file_id, 'name': filename, 'path': save_path,
                    'size': filesize, 'sender': sender,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'chat': 'general'
                }
                self.server.storage.files_list.append(file_info)
                self.server.storage.save_history()
                
                self.server.log(f"✅ Файл сохранён: {save_path}", "system")
                
                self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps({
                    "type": "file",
                    "data": {"sender": sender, "name": filename, "size": filesize, "id": file_id}
                }, ensure_ascii=True))
            
            elif cmd == 'V':
                target_len_data = self.recv_exact(file_socket, 4)
                if not target_len_data:
                    file_socket.close()
                    return
                target_len = struct.unpack('>I', target_len_data)[0]
                target = self.recv_exact(file_socket, target_len).decode('utf-8')
                
                name_len_data = self.recv_exact(file_socket, 4)
                if not name_len_data:
                    file_socket.close()
                    return
                name_len = struct.unpack('>I', name_len_data)[0]
                filename = self.recv_exact(file_socket, name_len).decode('utf-8')
                
                size_data = self.recv_exact(file_socket, 8)
                filesize = struct.unpack('>Q', size_data)[0]
                
                sender_len_data = self.recv_exact(file_socket, 4)
                if not sender_len_data:
                    file_socket.close()
                    return
                sender_len = struct.unpack('>I', sender_len_data)[0]
                sender = self.recv_exact(file_socket, sender_len).decode('utf-8')
                
                self.server.log(f"📥 Личный файл от {sender} для {target}: {filename} ({filesize/1024:.1f} KB)", "system")
                
                file_socket.send(b'K')
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)
                base, ext = os.path.splitext(safe_filename)
                save_path = os.path.join(self.server.config.RECEIVED_FILES_DIR, f"{base}_{timestamp}{ext}")
                
                received = 0
                with open(save_path, 'wb') as f:
                    while received < filesize:
                        data = file_socket.recv(min(8192, filesize - received))
                        if not data:
                            break
                        f.write(data)
                        received += len(data)
                
                file_id = hashlib.md5(f"{filename}{timestamp}{sender}{target}".encode()).hexdigest()[:8]
                file_info = {
                    'id': file_id, 'name': filename, 'path': save_path,
                    'size': filesize, 'sender': sender,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'chat': target
                }
                self.server.storage.files_list.append(file_info)
                self.server.storage.save_history()
                
                self.server.log(f"✅ Личный файл сохранён: {save_path}", "system")
                
                target_socket = sender_socket = None
                for s, data in self.server.client_data.items():
                    if data['nickname'] == target:
                        target_socket = s
                    if data['nickname'] == sender:
                        sender_socket = s
                
                payload = json.dumps({
                    "type": "private_file",
                    "target": target,
                    "data": {"sender": sender, "name": filename, "size": filesize, "id": file_id}
                }, ensure_ascii=True)
                
                if target_socket:
                    self.server.network.send_to_client(target_socket, "JSON_PAYLOAD:" + payload)
                if sender_socket:
                    self.server.network.send_to_client(sender_socket, "JSON_PAYLOAD:" + payload)
            
            file_socket.close()
                
        except Exception as e:
            self.server.log(f"❌ Ошибка файла от {addr}: {e}", "error")
            try:
                file_socket.close()
            except:
                pass