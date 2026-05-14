# server/storage.py
import os
from database import Database
from typing import Optional, List, Dict, Any

class Storage:
    """Единое хранилище для SQLite с совместимостью со старым кодом"""
    
    def __init__(self, config):
        self.config = config
        self.db = Database(config.DATABASE_PATH)
        
        # Для обратной совместимости со старыми модулями
        self.users_db = {}
        self.messages_history = []
        self.files_list = []
        self.private_messages = {}
        self.banned_ips = set()
        self.message_counter = 0
        
        self._load_cache()
        print(f"✅ Storage инициализирован (SQLite)")
    
    def _load_cache(self):
        """Загружает данные в кэш для обратной совместимости"""
        try:
            users = self.db.get_all_users()
            for user in users:
                self.users_db[user['username']] = {
                    'username': user['username'],
                    'password_hash': user.get('password_hash', ''),
                    'salt': user.get('salt', ''),
                    'is_admin': user.get('is_admin', False),
                    'is_online': user.get('is_online', False)
                }
            
            messages = self.db.get_chat_history(500)
            self.messages_history = [
                {
                    'id': f"msg_{i}",
                    'sender': m.get('sender', ''),
                    'text': m.get('message', ''),
                    'time': m.get('timestamp', '')[11:16] if m.get('timestamp') else "",
                    'edited': False
                }
                for i, m in enumerate(messages)
            ]
            self.message_counter = len(self.messages_history)
            
            banned = self.db.get_banned_ips()
            self.banned_ips = {b.get('identifier', '') for b in banned if b.get('identifier')}
        except Exception as e:
            print(f"⚠️ Ошибка загрузки кэша: {e}")
    
    # ========== Методы для работы с пользователями ==========
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Получает пользователя по username"""
        return self.db.get_user(username)
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Алиас для get_user (для совместимости с auth.py)"""
        return self.get_user(username)
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Получает пользователя по ID"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, password_hash, salt, is_admin, is_online, last_seen FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_user_by_nickname(self, nickname: str) -> Optional[Dict]:
        """Получает пользователя по nickname"""
        return self.db.get_user(nickname)
    
    def create_user(self, username: str, password_hash: str, salt: str, is_admin: bool = False) -> Optional[int]:
        """Создаёт пользователя"""
        user_id = self.db.create_user(username, password_hash, salt, is_admin)
        if user_id:
            self.users_db[username] = {
                'username': username,
                'password_hash': password_hash,
                'salt': salt,
                'is_admin': is_admin,
                'is_online': False
            }
        return user_id
    
    def get_all_users(self) -> List[Dict]:
        """Получает всех пользователей"""
        return self.db.get_all_users()
    
    def update_user_status(self, username: str, is_online: bool):
        """Обновляет статус пользователя"""
        if is_online:
            self.db.update_last_seen(username)
        else:
            self.db.set_user_offline(username)
        
        if username in self.users_db:
            self.users_db[username]['is_online'] = is_online
    
    def demote_admin(self, username: str) -> bool:
        """Забирает права администратора"""
        return self.db.demote_admin(username)
    
    def update_user_nickname(self, username: str, nickname: str) -> bool:
        """Обновляет никнейм пользователя"""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET nickname = ? WHERE username = ?', (nickname, username))
            return cursor.rowcount > 0
    
    # ========== Методы для работы с сообщениями ==========
    
    def save_message(self, sender: str, message: str, is_private: bool = False, recipient: str = None) -> int:
        """Сохраняет сообщение"""
        return self.db.save_message(sender, message, is_private, recipient)
    
    def add_message(self, message: Dict):
        """Добавляет сообщение в историю (для совместимости)"""
        self.messages_history.append(message)
        self.db.save_message(
            message.get('sender', ''),
            message.get('text', ''),
            is_private=False
        )
    
    def get_chat_history(self, limit: int = 100) -> List[Dict]:
        """Получает историю сообщений"""
        return self.db.get_chat_history(limit)
    
    def get_messages_history(self, limit: int = 100) -> List[Dict]:
        """Алиас для get_chat_history (для совместимости)"""
        messages = self.db.get_chat_history(limit)
        return [
            {
                'id': f"msg_{i}",
                'sender': m.get('sender', ''),
                'text': m.get('message', ''),
                'time': m.get('timestamp', '')[11:16] if m.get('timestamp') else "",
                'edited': False
            }
            for i, m in enumerate(messages)
        ]
    
    def save_history(self):
        """Сохраняет историю (для совместимости - ничего не делает, БД автосохраняется)"""
        pass
    
    # ========== Приватные сообщения ==========
    
    def save_private_message(self, sender: str, recipient: str, message: str) -> int:
        """Сохраняет приватное сообщение"""
        return self.db.save_private_message(sender, recipient, message)
    
    def get_private_messages(self, user1: str, user2: str, limit: int = 100) -> List[Dict]:
        """Получает переписку между пользователями"""
        return self.db.get_private_messages(user1, user2, limit)
    
    def add_private_message(self, chat_id: str, msg_id: str, user_id: int, sender: str, text: str, timestamp: str):
        """Добавляет приватное сообщение (для совместимости)"""
        self.db.save_private_message(sender, chat_id.replace('|', '_'), text)
    
    def save_private_messages(self):
        """Сохраняет приватные сообщения (для совместимости)"""
        pass
    
    # ========== Баны ==========
    
    def ban_ip(self, ip: str, reason: str = None) -> bool:
        """Блокирует IP"""
        return self.db.ban_ip(ip, reason)
    
    def is_banned(self, ip: str) -> bool:
        """Проверяет, забанен ли IP"""
        return self.db.is_banned(ip)
    
    def unban_ip(self, ip: str) -> bool:
        """Разбанивает IP"""
        return self.db.unban_ip(ip)
    
    def save_bans(self):
        """Сохраняет баны (для совместимости)"""
        pass
    
    def get_banned_ips(self) -> List[str]:
        """Получает список забаненных IP"""
        bans = self.db.get_banned_ips()
        return [b.get('identifier', '') for b in bans if b.get('identifier')]
    
    # ========== Друзья ==========
    
    def add_friend(self, username: str, friend: str) -> bool:
        """Добавляет друга"""
        return True
    
    def get_friends(self, username: str) -> List[str]:
        """Получает список друзей"""
        return []
    
    def save_friends(self):
        """Сохраняет список друзей"""
        pass
    
    # ========== Группы ==========
    
    def create_group(self, name: str, creator_id: int) -> Optional[int]:
        """Создаёт группу"""
        return self.db.create_group(name, creator_id)
    
    def get_group_by_name(self, name: str) -> Optional[Dict]:
        """Получает группу по имени"""
        return self.db.get_group_by_name(name)
    
    def get_group_by_id(self, group_id: int) -> Optional[Dict]:
        """Получает группу по ID"""
        return self.db.get_group_by_id(group_id)
    
    def add_group_member(self, group_id: int, user_id: int) -> bool:
        """Добавляет участника в группу"""
        return self.db.add_group_member(group_id, user_id)
    
    def remove_group_member(self, group_id: int, user_id: int) -> bool:
        """Удаляет участника из группы"""
        return self.db.remove_group_member(group_id, user_id)
    
    def get_group_members(self, group_id: int) -> List[Dict]:
        """Получает участников группы"""
        return self.db.get_group_members(group_id)
    
    def get_user_groups(self, user_id: int) -> List[Dict]:
        """Получает группы пользователя"""
        return self.db.get_user_groups(user_id)
    
    def save_group_message(self, group_id: int, sender_id: int, sender_nickname: str, message: str) -> int:
        """Сохраняет сообщение в группе"""
        return self.db.save_group_message(group_id, sender_id, sender_nickname, message)
    
    def get_group_messages(self, group_id: int, limit: int = 100) -> List[Dict]:
        """Получает сообщения группы"""
        return self.db.get_group_messages(group_id, limit)
    
    def delete_group(self, group_id: int) -> bool:
        """Удаляет группу"""
        return self.db.delete_group(group_id)
    
    # ========== Файлы ==========
    
    def save_file(self, file_id: str, name: str, path: str, size: int, sender_id: int, 
                  sender_nickname: str, chat_type: str, chat_target: str, date: str) -> int:
        """Сохраняет информацию о файле"""
        return self.db.save_file(file_id, name, path, size, sender_id, sender_nickname, 
                                  chat_type, chat_target, date)
    
    def get_file_by_id(self, file_id: str) -> Optional[Dict]:
        """Получает файл по ID"""
        return self.db.get_file_by_id(file_id)
    
    def get_files_by_chat(self, chat_type: str, chat_target: str = None) -> List[Dict]:
        """Получает файлы по типу чата"""
        return self.db.get_files_by_chat(chat_type, chat_target)
    
    def delete_file(self, file_id: str) -> bool:
        """Удаляет файл"""
        return self.db.delete_file(file_id)
    
    # ========== Статистика ==========
    
    def get_stats(self) -> Dict:
        """Возвращает статистику"""
        return self.db.get_stats()