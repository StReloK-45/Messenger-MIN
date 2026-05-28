# server/network.py
import socket
import threading
import json
import time
import struct
import os
from datetime import datetime
from typing import Optional, Dict, Any

from logger import logger


class NetworkManager:
    """Управление сетевыми соединениями (TCP сокеты)"""
    
    def __init__(self, server):
        self.server = server
        self.lock = threading.Lock()
        self.chat_socket: Optional[socket.socket] = None
        self.file_socket: Optional[socket.socket] = None
        self.running = False
        self._cleanup_thread: Optional[threading.Thread] = None
    
    def start_servers(self):
        """Запуск всех сетевых серверов"""
        self.running = True
        self.start_chat_server()
        self.start_file_server()
        self._start_cleanup_thread()
    
    def start_chat_server(self):
        """Запуск TCP сервера для чата (порт 5555)"""
        self.chat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.chat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Настройка таймаутов для предотвращения зависаний
        self.chat_socket.settimeout(1.0)
        
        try:
            self.chat_socket.bind((self.server.config.HOST, self.server.config.PORT))
            self.chat_socket.listen(100)
            
            def accept_clients():
                logger.success(f"Chat server started on port {self.server.config.PORT}")
                
                while self.running:
                    try:
                        client, addr = self.chat_socket.accept()
                        ip = addr[0]
                        
                        # Проверка бана
                        if self.server.storage.is_banned(ip):
                            self._send_banned_and_close(client, ip)
                            continue
                        
                        # Настройка клиентского сокета
                        client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        if hasattr(socket, 'TCP_KEEPIDLE'):
                            client.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 30)
                            client.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, 10)
                            client.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, 3)
                        
                        logger.connection(ip, "connected to chat")
                        client.send("AUTH_REQUIRED\n".encode('utf-8'))
                        
                        auth_thread = threading.Thread(
                            target=self.server.auth.handle_auth_loop,
                            args=(client, addr),
                            daemon=True
                        )
                        auth_thread.start()
                        
                    except socket.timeout:
                        continue
                    except OSError as e:
                        if self.running:
                            logger.error(f"Socket accept error: {e}")
                    except Exception as e:
                        if self.running:
                            logger.error(f"Unexpected accept error: {e}")
            
            accept_thread = threading.Thread(target=accept_clients, daemon=True)
            accept_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to start chat server: {e}")
            raise
    
    def start_file_server(self):
        """Запуск TCP сервера для файлов (порт 5556)"""
        self.file_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.file_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.file_socket.settimeout(1.0)
        
        try:
            self.file_socket.bind((self.server.config.HOST, self.server.config.FILE_PORT))
            self.file_socket.listen(50)
            
            def handle_connections():
                logger.success(f"File server started on port {self.server.config.FILE_PORT}")
                
                while self.running:
                    try:
                        fs, addr = self.file_socket.accept()
                        fs.settimeout(60)
                        logger.connection(addr[0], "file connection")
                        
                        file_thread = threading.Thread(
                            target=self.server.files.handle_file,
                            args=(fs, addr),
                            daemon=True
                        )
                        file_thread.start()
                        
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.running:
                            logger.error(f"File server error: {e}")
            
            file_thread = threading.Thread(target=handle_connections, daemon=True)
            file_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to start file server: {e}")
            raise
    
    def _start_cleanup_thread(self):
        """Запуск потока для периодической очистки"""
        def cleanup_loop():
            while self.running:
                time.sleep(60)  # Каждую минуту
                self._cleanup_stale_connections()
        
        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def _cleanup_stale_connections(self):
        """Очистка зависших соединений"""
        with self.lock:
            stale_clients = []
            now = time.time()
            
            for client in self.server.clients[:]:
                try:
                    # Проверка соединения отправкой keepalive
                    client.settimeout(0.1)
                    client.send(b'')
                    client.settimeout(None)
                except (socket.error, BrokenPipeError, ConnectionResetError):
                    stale_clients.append(client)
                except Exception:
                    pass
            
            for client in stale_clients:
                self.remove_client(client)
            
            if stale_clients:
                logger.info(f"Cleaned up {len(stale_clients)} stale connections")
    
    def _send_banned_and_close(self, client: socket.socket, ip: str):
        """Отправка сообщения о бане и закрытие соединения"""
        try:
            client.send("BANNED\n".encode('utf-8'))
            client.close()
        except:
            pass
        logger.warning(f"Banned IP attempted connection: {ip}")
    
    def broadcast(self, message: str, exclude_socket: Optional[socket.socket] = None):
        """Отправка сообщения всем подключенным клиентам"""
        with self.lock:
            message_bytes = (message + "\n").encode('utf-8')
            failed_clients = []
            
            for client in self.server.clients[:]:
                if client == exclude_socket:
                    continue
                
                try:
                    client.send(message_bytes)
                except (socket.error, BrokenPipeError, ConnectionResetError):
                    failed_clients.append(client)
                except Exception as e:
                    logger.error(f"Broadcast send error: {e}")
                    failed_clients.append(client)
            
            # Удаляем проблемные соединения
            for client in failed_clients:
                self.remove_client(client)
    
    def broadcast_json(self, data: Dict[str, Any], exclude_socket: Optional[socket.socket] = None):
        """Отправка JSON сообщения всем клиентам"""
        message = "JSON_PAYLOAD:" + json.dumps(data, ensure_ascii=False)
        self.broadcast(message, exclude_socket)
    
    def send_to_client(self, client: socket.socket, data: str) -> bool:
        """Отправка данных конкретному клиенту"""
        try:
            client.send((data + "\n").encode('utf-8'))
            return True
        except (socket.error, BrokenPipeError, ConnectionResetError):
            self.remove_client(client)
            return False
        except Exception as e:
            logger.error(f"Send to client error: {e}")
            self.remove_client(client)
            return False
    
    def send_to_user(self, nickname: str, data: str) -> bool:
        """Отправка данных пользователю по никнейму"""
        with self.lock:
            for client, user_data in self.server.client_data.items():
                if user_data.get('nickname') == nickname:
                    return self.send_to_client(client, data)
        return False
    
    def send_to_users(self, nicknames: list, data: str) -> int:
        """Отправка данных списку пользователей"""
        sent_count = 0
        with self.lock:
            for client, user_data in self.server.client_data.items():
                if user_data.get('nickname') in nicknames:
                    if self.send_to_client(client, data):
                        sent_count += 1
        return sent_count
    
    def broadcast_group_message(self, group_name: str, message: Dict[str, Any]):
        """Отправка сообщения всем участникам группы"""
        group = self.server.storage.get_group_by_name(group_name)
        if not group:
            logger.warning(f"Group {group_name} not found for broadcast")
            return
        
        members = self.server.storage.get_group_member_names(group['id'])
        
        with self.lock:
            for client, user_data in self.server.client_data.items():
                if user_data.get('nickname') in members:
                    self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(message, ensure_ascii=False))
    
    def broadcast_private_message(self, sender: str, recipient: str, message: Dict[str, Any]):
        """Отправка приватного сообщения отправителю и получателю"""
        with self.lock:
            for client, user_data in self.server.client_data.items():
                nickname = user_data.get('nickname')
                if nickname in (sender, recipient):
                    self.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(message, ensure_ascii=False))
    
    def remove_client(self, client: socket.socket):
        """Удаление клиента из всех структур"""
        with self.lock:
            if client in self.server.clients:
                self.server.clients.remove(client)
            
            user_data = self.server.client_data.pop(client, {})
            nickname = user_data.get('nickname', 'Unknown')
            username = user_data.get('username', '')
            
            try:
                client.close()
            except:
                pass
            
            # Обновляем статус в БД
            if username:
                self.server.storage.update_user_status(username, False)
            
            # Оповещаем остальных
            if nickname != 'Unknown':
                self.broadcast_json({
                    "type": "notification",
                    "text": f"{nickname} покинул чат"
                })
                
                # Обновляем список онлайн
                online_users = [data['nickname'] for data in self.server.client_data.values()]
                self.broadcast_json({
                    "type": "online_users",
                    "users": online_users
                })
            
            logger.info(f"Client disconnected: {nickname} | Online: {len(self.server.clients)}")
            
            if hasattr(self.server, 'update_online_display'):
                self.server.update_online_display()
    
    def get_online_count(self) -> int:
        """Получение количества онлайн пользователей"""
        return len(self.server.clients)
    
    def get_online_users(self) -> list:
        """Получение списка онлайн пользователей"""
        with self.lock:
            return [data['nickname'] for data in self.server.client_data.values()]
    
    def is_user_online(self, nickname: str) -> bool:
        """Проверка, находится ли пользователь в сети"""
        with self.lock:
            for user_data in self.server.client_data.values():
                if user_data.get('nickname') == nickname:
                    return True
        return False
    
    def get_client_by_nickname(self, nickname: str) -> Optional[socket.socket]:
        """Получение сокета клиента по никнейму"""
        with self.lock:
            for client, user_data in self.server.client_data.items():
                if user_data.get('nickname') == nickname:
                    return client
        return None
    
    def stop_servers(self):
        """Остановка всех сетевых серверов"""
        self.running = False
        
        # Закрываем сокеты
        if self.chat_socket:
            try:
                self.chat_socket.close()
            except:
                pass
        
        if self.file_socket:
            try:
                self.file_socket.close()
            except:
                pass
        
        # Закрываем все клиентские соединения
        with self.lock:
            for client in self.server.clients[:]:
                try:
                    client.close()
                except:
                    pass
            self.server.clients.clear()
            self.server.client_data.clear()
        
        logger.info("Network servers stopped")
    
    def get_network_stats(self) -> dict:
        """Получение статистики сети"""
        return {
            "chat_server_running": self.chat_socket is not None,
            "file_server_running": self.file_socket is not None,
            "connected_clients": len(self.server.clients),
            "online_users": len(self.get_online_users())
        }