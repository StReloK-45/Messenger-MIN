# server/network.py
import socket
import threading
import json
import time

class NetworkManager:
    def __init__(self, server):
        self.server = server
        self.lock = threading.Lock()
    
    def start_servers(self):
        self.start_chat_server()
        self.start_file_server()
    
    def start_chat_server(self):
        chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        chat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        chat_socket.bind((self.server.config.HOST, self.server.config.PORT))
        chat_socket.listen(100)
        
        def accept_clients():
            while self.server.running:
                try:
                    chat_socket.settimeout(1)
                    client, addr = chat_socket.accept()
                    ip = addr[0]
                    
                    if ip in self.server.storage.banned_ips:
                        client.send("BANNED\n".encode('utf-8'))
                        client.close()
                        self.server.log(f"🚫 Забаненный IP: {ip}", "error")
                        continue
                    
                    self.server.log(f"[+] Новое подключение: {addr}", "system")
                    client.send("AUTH_REQUIRED\n".encode('utf-8'))
                    threading.Thread(target=self.server.auth.handle_auth_loop, args=(client, addr), daemon=True).start()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.server.running:
                        self.server.log(f"Ошибка accept: {e}", "error")
        
        threading.Thread(target=accept_clients, daemon=True).start()
        self.server.log(f"💬 Чат сервер запущен на порту {self.server.config.PORT}", "system")
    
    def start_file_server(self):
        file_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        file_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        file_socket.bind((self.server.config.HOST, self.server.config.FILE_PORT))
        file_socket.listen(100)
        
        def handle_connections():
            while self.server.running:
                try:
                    file_socket.settimeout(1)
                    fs, addr = file_socket.accept()
                    self.server.log(f"[+] Файловое подключение: {addr}", "system")
                    threading.Thread(target=self.server.files.handle_file, args=(fs, addr), daemon=True).start()
                except socket.timeout:
                    continue
                except:
                    pass
        
        threading.Thread(target=handle_connections, daemon=True).start()
        self.server.log(f"📁 Файловый сервер запущен на порту {self.server.config.FILE_PORT}", "system")
    
    def broadcast(self, message, exclude_socket=None):
        with self.lock:
            message_bytes = (message + "\n").encode('utf-8')
            for client in self.server.clients[:]:
                if client != exclude_socket:
                    try:
                        client.send(message_bytes)
                    except:
                        self.remove_client(client)
    
    def send_to_client(self, client, data):
        try:
            client.send((data + "\n").encode('utf-8'))
        except:
            self.remove_client(client)
    
    def remove_client(self, client):
        if client in self.server.clients:
            data = self.server.client_data.get(client, {})
            name = data.get('nickname', 'Unknown')
            self.server.clients.remove(client)
            if client in self.server.client_data:
                del self.server.client_data[client]
            try:
                client.close()
            except:
                pass
            self.broadcast(json.dumps({"type": "notification", "text": f"{name} покинул чат"}, ensure_ascii=False))
            self.server.log(f"👤 {name} отключился | Онлайн: {len(self.server.clients)}", "server")
            self.server.root.after(0, self.server.update_online_display)