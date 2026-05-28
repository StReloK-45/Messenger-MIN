# server/files.py
import struct
import json
import os
import re
import hashlib
import time
import threading
import socket
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from logger import logger


class FileManager:
    """Управление файловыми операциями (загрузка, скачивание, удаление)"""
    
    MAX_FILE_SIZE = 250 * 1024 * 1024  # 250 MB
    ALLOWED_EXTENSIONS = {
        '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
        '.mp3', '.mp4', '.wav', '.ogg', '.flac', '.mp3',
        '.zip', '.rar', '.7z', '.tar', '.gz',
        '.py', '.js', '.html', '.css', '.json', '.xml', '.yaml', '.yml',
        '.exe', '.msi', '.deb', '.rpm'
    }
    MAX_FILENAME_LENGTH = 255
    
    def __init__(self, server):
        self.server = server
        self._active_transfers: Dict[str, Dict] = {}
        self._transfer_lock = threading.Lock()
    
    def recv_exact(self, sock: socket.socket, size: int) -> Optional[bytes]:
        """Получение точного количества байт из сокета"""
        data = b''
        original_timeout = sock.gettimeout()
        
        while len(data) < size:
            try:
                remaining = size - len(data)
                chunk = sock.recv(min(8192, remaining))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                return None
            except Exception as e:
                logger.error(f"recv_exact error: {e}")
                return None
        
        return data
    
    def validate_filename(self, filename: str) -> Tuple[bool, str]:
        """Валидация имени файла"""
        if not filename:
            return False, "Empty filename"
        
        if len(filename) > self.MAX_FILENAME_LENGTH:
            return False, f"Filename too long (max {self.MAX_FILENAME_LENGTH} chars)"
        
        # Проверка на опасные символы
        dangerous_patterns = [r'\.\.', r'[/\\]', r'^\.', r'[\x00-\x1f]']
        for pattern in dangerous_patterns:
            if re.search(pattern, filename):
                return False, "Filename contains invalid characters"
        
        # Проверка расширения (опционально, можно отключить)
        ext = os.path.splitext(filename)[1].lower()
        if ext and ext not in self.ALLOWED_EXTENSIONS:
            logger.warning(f"Unknown file extension: {ext} for {filename}")
            # Разрешаем, но логируем
        
        return True, ""
    
    def get_safe_filename(self, filename: str) -> str:
        """Генерация безопасного имени файла"""
        safe_name = re.sub(r'[\\/*?:"<>|]', '_', filename)
        safe_name = re.sub(r'[\x00-\x1f]', '', safe_name)
        safe_name = safe_name.strip()
        
        if not safe_name:
            safe_name = "unnamed_file"
        
        return safe_name
    
    def generate_file_id(self, filename: str, sender: str, target: str = "") -> str:
        """Генерация уникального ID файла"""
        data = f"{filename}{sender}{target}{datetime.now().timestamp()}{os.urandom(4).hex()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    def save_file_to_disk(self, filename: str, filesize: int, sender: str, 
                          chat_type: str, chat_target: str, 
                          file_socket: socket.socket) -> Optional[Dict]:
        """Сохраняет файл на диск и возвращает информацию о нём"""
        try:
            # Валидация
            valid, err = self.validate_filename(filename)
            if not valid:
                self._send_error(file_socket, err)
                return None
            
            if filesize > self.MAX_FILE_SIZE:
                self._send_error(file_socket, f"File too large (max {self.MAX_FILE_SIZE // (1024*1024)} MB)")
                return None
            
            # Подготовка пути
            safe_filename = self.get_safe_filename(filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base, ext = os.path.splitext(safe_filename)
            final_filename = f"{base}_{timestamp}{ext}"
            
            # Создание директории по типу чата
            if chat_type == "general":
                subdir = "general"
            elif chat_type == "private":
                subdir = f"private_{chat_target}"
            elif chat_type == "group":
                subdir = f"group_{chat_target}"
            else:
                subdir = "other"
            
            save_dir = os.path.join(self.server.config.RECEIVED_FILES_DIR, subdir)
            os.makedirs(save_dir, exist_ok=True)
            
            save_path = os.path.join(save_dir, final_filename)
            
            # Приём файла с прогрессом
            received = 0
            last_log = time.time()
            transfer_id = f"{sender}_{filename}_{int(time.time())}"
            
            # Регистрируем активную передачу
            with self._transfer_lock:
                self._active_transfers[transfer_id] = {
                    'filename': filename,
                    'size': filesize,
                    'received': 0,
                    'start_time': time.time()
                }
            
            try:
                with open(save_path, 'wb') as f:
                    while received < filesize:
                        chunk_size = min(8192, filesize - received)
                        data = self.recv_exact(file_socket, chunk_size)
                        if data is None:
                            raise Exception("File transfer interrupted")
                        
                        f.write(data)
                        received += len(data)
                        
                        # Обновляем прогресс
                        with self._transfer_lock:
                            if transfer_id in self._active_transfers:
                                self._active_transfers[transfer_id]['received'] = received
                        
                        # Логирование прогресса каждые 10 секунд или при завершении
                        if time.time() - last_log > 10 or received == filesize:
                            progress = (received / filesize) * 100
                            logger.info(f"File upload progress: {progress:.1f}% ({received}/{filesize}) - {filename}")
                            last_log = time.time()
            finally:
                # Удаляем запись о передаче
                with self._transfer_lock:
                    if transfer_id in self._active_transfers:
                        del self._active_transfers[transfer_id]
            
            # Генерация ID
            file_id = self.generate_file_id(filename, sender, chat_target)
            
            # Получение ID отправителя
            user = self.server.storage.get_user_by_nickname(sender)
            sender_id = user['id'] if user else 0
            
            # Сохранение в БД
            date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.server.storage.save_file(
                file_id, filename, save_path, filesize,
                sender_id, sender, chat_type, chat_target, date_str
            )
            
            file_info = {
                'id': file_id,
                'name': filename,
                'path': save_path,
                'size': filesize,
                'sender': sender,
                'date': date_str,
                'chat_type': chat_type,
                'chat_target': chat_target
            }
            
            # Добавляем в кэш для обратной совместимости
            if chat_type == "general":
                self.server.storage.files_list.append(file_info)
            elif chat_type == "private":
                if chat_target not in self.server.storage.private_files:
                    self.server.storage.private_files[chat_target] = []
                self.server.storage.private_files[chat_target].append(file_info)
            elif chat_type == "group":
                if chat_target not in self.server.storage.group_messages:
                    self.server.storage.group_messages[chat_target] = {}
                if 'files' not in self.server.storage.group_messages[chat_target]:
                    self.server.storage.group_messages[chat_target]['files'] = []
                self.server.storage.group_messages[chat_target]['files'].append(file_info)
            
            self.server.storage.save_history()
            
            logger.info(f"File saved: {filename} ({filesize/1024:.1f} KB) from {sender} to {chat_type}/{chat_target}")
            return file_info
            
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            self._send_error(file_socket, f"Save failed: {str(e)[:100]}")
            return None
    
    def _send_error(self, sock: socket.socket, error_msg: str):
        """Отправка ошибки клиенту"""
        try:
            sock.send(b'E')
            error_bytes = error_msg.encode('utf-8')[:255]
            sock.send(struct.pack('>I', len(error_bytes)))
            sock.send(error_bytes)
        except Exception as e:
            logger.error(f"Error sending error: {e}")
    
    def _send_success(self, sock: socket.socket):
        """Отправка подтверждения успеха"""
        try:
            sock.send(b'K')
        except Exception as e:
            logger.error(f"Error sending success: {e}")
    
    def handle_file(self, file_socket: socket.socket, addr: tuple):
        """Обработка файловых операций"""
        try:
            file_socket.settimeout(60)
            
            # Получение команды
            cmd_byte = file_socket.recv(1)
            if not cmd_byte:
                file_socket.close()
                return
            
            cmd = cmd_byte.decode('utf-8', errors='ignore')
            
            # ========== СПИСОК ОБЩИХ ФАЙЛОВ ==========
            if cmd == 'L':
                self._handle_list_general_files(file_socket)
            
            # ========== СПИСОК ЛИЧНЫХ ФАЙЛОВ ==========
            elif cmd == 'P':
                self._handle_list_private_files(file_socket)
            
            # ========== СПИСОК ФАЙЛОВ ГРУППЫ ==========
            elif cmd == 'G':
                self._handle_list_group_files(file_socket)
            
            # ========== СКАЧИВАНИЕ ФАЙЛА ==========
            elif cmd == 'D':
                self._handle_download_file(file_socket)
            
            # ========== ЗАГРУЗКА ФАЙЛА В ОБЩИЙ ЧАТ ==========
            elif cmd == 'U':
                self._handle_upload_general_file(file_socket)
            
            # ========== ЗАГРУЗКА ФАЙЛА В ЛИЧНЫЙ ЧАТ ==========
            elif cmd == 'V':
                self._handle_upload_private_file(file_socket)
            
            # ========== ЗАГРУЗКА ФАЙЛА В ГРУППУ ==========
            elif cmd == 'C':  # C for Group (upload)
                self._handle_upload_group_file(file_socket)
            
            # ========== УДАЛЕНИЕ ФАЙЛА ==========
            elif cmd == 'X':
                self._handle_delete_file(file_socket)
            
            else:
                logger.warning(f"Unknown file command: {cmd} from {addr}")
                file_socket.send(b'E')
            
            file_socket.close()
            
        except socket.timeout:
            logger.warning(f"File socket timeout from {addr}")
        except ConnectionResetError:
            logger.warning(f"File connection reset from {addr}")
        except Exception as e:
            logger.error(f"File handler error from {addr}: {e}")
            try:
                file_socket.close()
            except:
                pass
    
    def _handle_list_general_files(self, sock: socket.socket):
        """Отправка списка общих файлов"""
        general_files = [f for f in self.server.storage.files_list if f.get('chat_type', 'general') == 'general']
        files_json = json.dumps(general_files, ensure_ascii=True)
        sock.send(struct.pack('>I', len(files_json)))
        sock.send(files_json.encode('utf-8'))
        logger.info(f"Listed {len(general_files)} general files")
    
    def _handle_list_private_files(self, sock: socket.socket):
        """Отправка списка личных файлов"""
        nick_len_data = self.recv_exact(sock, 4)
        if not nick_len_data:
            return
        
        nick_len = struct.unpack('>I', nick_len_data)[0]
        nickname = self.recv_exact(sock, nick_len).decode('utf-8')
        
        private_files = [f for f in self.server.storage.files_list 
                        if f.get('chat_type') == 'private' and f.get('chat_target') == nickname]
        files_json = json.dumps(private_files, ensure_ascii=True)
        sock.send(struct.pack('>I', len(files_json)))
        sock.send(files_json.encode('utf-8'))
        logger.info(f"Listed {len(private_files)} private files for {nickname}")
    
    def _handle_list_group_files(self, sock: socket.socket):
        """Отправка списка файлов группы"""
        group_len_data = self.recv_exact(sock, 4)
        if not group_len_data:
            return
        
        group_len = struct.unpack('>I', group_len_data)[0]
        group_name = self.recv_exact(sock, group_len).decode('utf-8')
        
        group_files = self.server.storage.get_files_by_chat('group', group_name)
        files_json = json.dumps(group_files, ensure_ascii=True)
        sock.send(struct.pack('>I', len(files_json)))
        sock.send(files_json.encode('utf-8'))
        logger.info(f"Listed {len(group_files)} group files for {group_name}")
    
    def _handle_download_file(self, sock: socket.socket):
        """Отправка файла клиенту"""
        id_len_data = self.recv_exact(sock, 4)
        if not id_len_data:
            return
        
        id_len = struct.unpack('>I', id_len_data)[0]
        file_id = self.recv_exact(sock, id_len).decode('utf-8')
        
        # Поиск файла
        file_info = self.server.storage.get_file_by_id(file_id)
        if not file_info:
            sock.send(b'E')
            error_msg = "File not found"
            sock.send(struct.pack('>I', len(error_msg)))
            sock.send(error_msg.encode('utf-8'))
            logger.warning(f"File not found: {file_id}")
            return
        
        file_path = file_info.get('path')
        if not os.path.exists(file_path):
            sock.send(b'E')
            error_msg = "File not found on disk"
            sock.send(struct.pack('>I', len(error_msg)))
            sock.send(error_msg.encode('utf-8'))
            logger.warning(f"File missing on disk: {file_path}")
            return
        
        # Отправка файла
        filesize = file_info.get('size', 0)
        filename = file_info.get('name', 'file')
        
        sock.send(b'K')
        sock.send(struct.pack('>Q', filesize))
        name_bytes = filename.encode('utf-8')
        sock.send(struct.pack('>I', len(name_bytes)))
        sock.send(name_bytes)
        
        sent = 0
        last_log = time.time()
        
        with open(file_path, 'rb') as f:
            while True:
                data = f.read(8192)
                if not data:
                    break
                sock.send(data)
                sent += len(data)
                
                if time.time() - last_log > 10:
                    progress = (sent / filesize) * 100
                    logger.info(f"File download progress: {progress:.1f}% - {filename}")
                    last_log = time.time()
        
        logger.info(f"File downloaded: {filename} ({filesize/1024:.1f} KB)")
    
    def _handle_upload_general_file(self, sock: socket.socket):
        """Загрузка файла в общий чат"""
        file_info = self._receive_file_metadata(sock, 'general', '')
        if not file_info:
            return
        
        self._send_success(sock)
        
        result = self.save_file_to_disk(
            file_info['filename'],
            file_info['filesize'],
            file_info['sender'],
            'general',
            '',
            sock
        )
        
        if result:
            self._broadcast_file_notification('general', '', result)
            self._send_success(sock)
        else:
            sock.send(b'E')
    
    def _handle_upload_private_file(self, sock: socket.socket):
        """Загрузка файла в личный чат"""
        # Получаем получателя
        target_len_data = self.recv_exact(sock, 4)
        if not target_len_data:
            return
        
        target_len = struct.unpack('>I', target_len_data)[0]
        target = self.recv_exact(sock, target_len).decode('utf-8')
        
        file_info = self._receive_file_metadata(sock, 'private', target)
        if not file_info:
            return
        
        self._send_success(sock)
        
        result = self.save_file_to_disk(
            file_info['filename'],
            file_info['filesize'],
            file_info['sender'],
            'private',
            target,
            sock
        )
        
        if result:
            self._broadcast_file_notification('private', target, result)
            self._send_success(sock)
        else:
            sock.send(b'E')
    
    def _handle_upload_group_file(self, sock: socket.socket):
        # Получаем название группы
        group_len_data = self.recv_exact(sock, 4)
        if not group_len_data:
            return
        
        group_len = struct.unpack('>I', group_len_data)[0]
        group_name = self.recv_exact(sock, group_len).decode('utf-8')
        
        # Проверяем существование группы
        group = self.server.storage.get_group_by_name(group_name)
        if not group:
            self._send_error(sock, f"Group not found: {group_name}")
            return
        
        # Получаем метаданные файла
        name_len_data = self.recv_exact(sock, 4)
        if not name_len_data:
            return
        
        name_len = struct.unpack('>I', name_len_data)[0]
        filename = self.recv_exact(sock, name_len).decode('utf-8')
        
        size_data = self.recv_exact(sock, 8)
        if not size_data:
            return
        
        filesize = struct.unpack('>Q', size_data)[0]
        
        sender_len_data = self.recv_exact(sock, 4)
        if not sender_len_data:
            return
        
        sender_len = struct.unpack('>I', sender_len_data)[0]
        sender = self.recv_exact(sock, sender_len).decode('utf-8')
        
        self._send_success(sock)
        
        result = self.save_file_to_disk(
            filename, filesize, sender,
            'group', group_name, sock
        )
        
        if result:
            self._broadcast_file_notification('group', group_name, result)
            self._send_success(sock)
        else:
            sock.send(b'E')
    
    def _receive_file_metadata(self, sock: socket.socket, chat_type: str, 
                                chat_target: str) -> Optional[Dict]:
        """Получение метаданных файла"""
        # Имя файла
        name_len_data = self.recv_exact(sock, 4)
        if not name_len_data:
            return None
        
        name_len = struct.unpack('>I', name_len_data)[0]
        filename = self.recv_exact(sock, name_len).decode('utf-8')
        
        # Размер файла
        size_data = self.recv_exact(sock, 8)
        if not size_data:
            return None
        
        filesize = struct.unpack('>Q', size_data)[0]
        
        # Отправитель
        sender_len_data = self.recv_exact(sock, 4)
        if not sender_len_data:
            return None
        
        sender_len = struct.unpack('>I', sender_len_data)[0]
        sender = self.recv_exact(sock, sender_len).decode('utf-8')
        
        logger.info(f"Receiving file: {filename} ({filesize/1024:.1f} KB) from {sender} to {chat_type}/{chat_target}")
        
        return {
            'filename': filename,
            'filesize': filesize,
            'sender': sender,
            'chat_type': chat_type,
            'chat_target': chat_target
        }
    
    def _broadcast_file_notification(self, chat_type: str, chat_target: str, file_info: Dict):
        """Отправка уведомления о новом файле"""
        notification = {
            "type": "file" if chat_type == "general" else "private_file" if chat_type == "private" else "group_file",
            "data": {
                "id": file_info['id'],
                "name": file_info['name'],
                "size": file_info['size'],
                "sender": file_info['sender'],
                "date": file_info['date']
            }
        }
        
        if chat_type == "private":
            notification["target"] = chat_target
            self.server.network.broadcast_private_message(file_info['sender'], chat_target, notification)
        elif chat_type == "group":
            notification["group"] = chat_target
            self.server.network.broadcast_group_message(chat_target, notification)
        else:
            self.server.network.broadcast_json(notification)
        
        logger.info(f"File notification broadcast: {file_info['name']} to {chat_type}/{chat_target}")
    
    def _handle_delete_file(self, sock: socket.socket):
        """Удаление файла"""
        id_len_data = self.recv_exact(sock, 4)
        if not id_len_data:
            return
        
        id_len = struct.unpack('>I', id_len_data)[0]
        file_id = self.recv_exact(sock, id_len).decode('utf-8')
        
        file_info = self.server.storage.get_file_by_id(file_id)
        if not file_info:
            self._send_error(sock, "File not found")
            return
        
        # Удаляем физический файл
        file_path = file_info.get('path')
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Deleted file from disk: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete file from disk: {e}")
        
        # Удаляем из БД
        self.server.storage.delete_file(file_id)
        
        # Удаляем из кэша
        chat_type = file_info.get('chat_type', 'general')
        chat_target = file_info.get('chat_target')
        
        if chat_type == "general":
            self.server.storage.files_list = [f for f in self.server.storage.files_list if f.get('id') != file_id]
        elif chat_type == "private" and chat_target:
            if chat_target in self.server.storage.private_files:
                self.server.storage.private_files[chat_target] = [
                    f for f in self.server.storage.private_files[chat_target] if f.get('id') != file_id
                ]
        elif chat_type == "group" and chat_target:
            if chat_target in self.server.storage.group_messages:
                if 'files' in self.server.storage.group_messages[chat_target]:
                    self.server.storage.group_messages[chat_target]['files'] = [
                        f for f in self.server.storage.group_messages[chat_target]['files'] if f.get('id') != file_id
                    ]
        
        # Уведомляем всех
        notification = {
            "type": "file_deleted",
            "id": file_id,
            "name": file_info.get('name')
        }
        
        if chat_type == "private" and chat_target:
            self.server.network.broadcast_private_message(
                file_info.get('sender_nickname', ''), chat_target, notification
            )
        elif chat_type == "group" and chat_target:
            self.server.network.broadcast_group_message(chat_target, notification)
        else:
            self.server.network.broadcast_json(notification)
        
        self._send_success(sock)
        logger.info(f"File deleted: {file_id} ({file_info.get('name')})")
    
    def get_active_transfers(self) -> Dict:
        """Получение списка активных передач"""
        with self._transfer_lock:
            return dict(self._active_transfers)
    
    def cleanup_old_transfers(self, timeout_seconds: int = 300):
        """Очистка зависших передач"""
        now = time.time()
        with self._transfer_lock:
            to_remove = []
            for tid, transfer in self._active_transfers.items():
                if now - transfer.get('start_time', 0) > timeout_seconds:
                    to_remove.append(tid)
            
            for tid in to_remove:
                del self._active_transfers[tid]
            
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} stale file transfers")