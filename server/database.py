# server/database.py
import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        
        # Создаём папку для БД, если её нет
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def init_db(self):
        """Инициализация базы данных: создание всех таблиц и индексов"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP,
                    is_online BOOLEAN DEFAULT 0,
                    avatar_url TEXT
                )
            ''')
            
            # Таблица для общих сообщений (чат-история)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_private BOOLEAN DEFAULT 0,
                    recipient TEXT
                )
            ''')
            
            # Таблица для приватных сообщений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS private_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_read BOOLEAN DEFAULT 0
                )
            ''')
            
            # Таблица для забаненных пользователей/IP
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS banned (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier TEXT UNIQUE NOT NULL,
                    reason TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            ''')
            
            # Таблица для сессий (для будущего FastAPI)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    ip_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            ''')
            
            # Таблица для групп
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    creator_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (creator_id) REFERENCES users(id)
                )
            ''')
            
            # Таблица для участников групп
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES groups(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE(group_id, user_id)
                )
            ''')
            
            # Таблица для сообщений в группах
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS group_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    sender_id INTEGER NOT NULL,
                    sender_nickname TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES groups(id),
                    FOREIGN KEY (sender_id) REFERENCES users(id)
                )
            ''')
            
            # Таблица для файлов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    sender_id INTEGER NOT NULL,
                    sender_nickname TEXT NOT NULL,
                    chat_type TEXT NOT NULL,
                    chat_target TEXT,
                    date TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sender_id) REFERENCES users(id)
                )
            ''')
            
            # Создаём индексы для ускорения запросов
            self._create_indexes(cursor)
    
    def _create_indexes(self, cursor):
        """Создаёт все индексы для ускорения запросов"""
        try:
            # Индексы для таблицы messages
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender)')
            
            # Индексы для таблицы private_messages
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_private_messages_users ON private_messages(sender, recipient)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_private_messages_timestamp ON private_messages(timestamp)')
            
            # Индексы для таблицы sessions
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username)')
            
            # Индексы для таблицы users
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_online ON users(is_online)')
            
            # Индексы для групп
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_messages_group ON group_messages(group_id)')
            
        except sqlite3.OperationalError as e:
            print(f"Предупреждение: не удалось создать некоторые индексы - {e}")
    
    # === Методы для работы с пользователями ===
    
    def create_user(self, username, password_hash, salt, is_admin=False):
        """Создаёт нового пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (username, password_hash, salt, is_admin, created_at, last_seen) 
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (username, password_hash, salt, 1 if is_admin else 0, datetime.now(), datetime.now()))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None
    
    def get_user(self, username):
        """Получает информацию о пользователе"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_last_seen(self, username):
        """Обновляет время последнего визита"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_seen = ?, is_online = 1 WHERE username = ?
            ''', (datetime.now(), username))
    
    def set_user_offline(self, username):
        """Устанавливает статус пользователя 'оффлайн'"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_online = 0 WHERE username = ?', (username,))
    
    def get_all_users(self):
        """Возвращает список всех пользователей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, password_hash, salt, is_admin, is_online, last_seen FROM users')
            return [dict(row) for row in cursor.fetchall()]
    
    def demote_admin(self, username):
        """Забирает права администратора"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_admin = 0 WHERE username = ?', (username,))
            return cursor.rowcount > 0
    
    # === Методы для работы с сообщениями ===
    
    def save_message(self, sender, message, is_private=False, recipient=None):
        """Сохраняет сообщение в историю"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (sender, message, timestamp, is_private, recipient) 
                VALUES (?, ?, ?, ?, ?)
            ''', (sender, message, datetime.now(), is_private, recipient))
            return cursor.lastrowid
    
    def get_chat_history(self, limit=100):
        """Получает последние сообщения из общего чата"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sender, message, timestamp 
                FROM messages 
                WHERE is_private = 0 OR is_private IS NULL
                ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            messages = [dict(row) for row in cursor.fetchall()]
            return list(reversed(messages))
    
    def save_private_message(self, sender, recipient, message):
        """Сохраняет приватное сообщение"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO private_messages (sender, recipient, message, timestamp) 
                VALUES (?, ?, ?, ?)
            ''', (sender, recipient, message, datetime.now()))
            return cursor.lastrowid
    
    def get_private_messages(self, user1, user2, limit=100):
        """Получает переписку между двумя пользователями"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sender, recipient, message, timestamp 
                FROM private_messages 
                WHERE (sender = ? AND recipient = ?) OR (sender = ? AND recipient = ?)
                ORDER BY timestamp ASC LIMIT ?
            ''', (user1, user2, user2, user1, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    # === Методы для работы с банами ===
    
    def ban_ip(self, ip_address, reason=None, expires_at=None):
        """Блокирует IP-адрес"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO banned (identifier, reason, expires_at) 
                    VALUES (?, ?, ?)
                ''', (ip_address, reason, expires_at))
                return True
            except sqlite3.IntegrityError:
                return False
    
    def is_banned(self, identifier):
        """Проверяет, заблокирован ли IP/пользователь"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM banned 
                WHERE identifier = ? AND (expires_at IS NULL OR expires_at > ?)
            ''', (identifier, datetime.now()))
            return cursor.fetchone() is not None
    
    def get_banned_ips(self):
        """Возвращает список забаненных IP"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT identifier, reason, banned_at, expires_at FROM banned')
            return [dict(row) for row in cursor.fetchall()]
    
    def unban_ip(self, ip_address):
        """Разблокирует IP-адрес"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM banned WHERE identifier = ?', (ip_address,))
            return cursor.rowcount > 0
    
    # === Методы для работы с сессиями ===
    
    def create_session(self, username, token, ip_address, expires_at):
        """Создаёт новую сессию"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (username, token, ip_address, expires_at) 
                VALUES (?, ?, ?, ?)
            ''', (username, token, ip_address, expires_at))
            return cursor.lastrowid
    
    def get_session(self, token):
        """Получает сессию по токену"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM sessions WHERE token = ? AND expires_at > ?
            ''', (token, datetime.now()))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def delete_session(self, token):
        """Удаляет сессию (выход)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
    
    def delete_expired_sessions(self):
        """Удаляет просроченные сессии"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE expires_at <= ?', (datetime.now(),))
            return cursor.rowcount
    
    # === Методы для работы с группами ===
    
    def create_group(self, name, creator_id):
        """Создаёт новую группу"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO groups (name, creator_id) VALUES (?, ?)', (name, creator_id))
                group_id = cursor.lastrowid
                cursor.execute('INSERT INTO group_members (group_id, user_id) VALUES (?, ?)', (group_id, creator_id))
                return group_id
            except sqlite3.IntegrityError:
                return None
    
    def add_group_member(self, group_id, user_id):
        """Добавляет участника в группу"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)', (group_id, user_id))
            return cursor.rowcount > 0
    
    def remove_group_member(self, group_id, user_id):
        """Удаляет участника из группы"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, user_id))
            return cursor.rowcount > 0
    
    def get_group_by_name(self, name):
        """Получает группу по названию"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups WHERE name = ?', (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_group_by_id(self, group_id):
        """Получает группу по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups WHERE id = ?', (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_group_members(self, group_id):
        """Получает список участников группы"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.id, u.username, u.nickname 
                FROM group_members gm 
                JOIN users u ON gm.user_id = u.id 
                WHERE gm.group_id = ?
            ''', (group_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_groups(self, user_id):
        """Получает список групп пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT g.id, g.name, g.created_at 
                FROM groups g 
                JOIN group_members gm ON g.id = gm.group_id 
                WHERE gm.user_id = ?
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_group(self, group_id):
        """Удаляет группу и все связанные данные"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM group_messages WHERE group_id = ?', (group_id,))
            cursor.execute('DELETE FROM group_members WHERE group_id = ?', (group_id,))
            cursor.execute('DELETE FROM groups WHERE id = ?', (group_id,))
            return True
    
    def save_group_message(self, group_id, sender_id, sender_nickname, message):
        """Сохраняет сообщение в группе"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO group_messages (group_id, sender_id, sender_nickname, message, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (group_id, sender_id, sender_nickname, message, datetime.now()))
            return cursor.lastrowid
    
    def get_group_messages(self, group_id, limit=100):
        """Получает сообщения группы"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sender_nickname, message, timestamp 
                FROM group_messages 
                WHERE group_id = ? 
                ORDER BY timestamp ASC LIMIT ?
            ''', (group_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    # === Методы для работы с файлами ===
    
    def save_file(self, file_id, name, path, size, sender_id, sender_nickname, chat_type, chat_target, date):
        """Сохраняет информацию о файле"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO files (file_id, name, path, size, sender_id, sender_nickname, chat_type, chat_target, date) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (file_id, name, path, size, sender_id, sender_nickname, chat_type, chat_target, date))
            return cursor.lastrowid
    
    def get_file_by_id(self, file_id):
        """Получает файл по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM files WHERE file_id = ?', (file_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_files_by_chat(self, chat_type, chat_target=None):
        """Получает файлы по типу чата"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if chat_target:
                cursor.execute('''
                    SELECT file_id, name, size, sender_nickname, date 
                    FROM files 
                    WHERE chat_type = ? AND chat_target = ?
                    ORDER BY created_at DESC
                ''', (chat_type, chat_target))
            else:
                cursor.execute('''
                    SELECT file_id, name, size, sender_nickname, date 
                    FROM files 
                    WHERE chat_type = ?
                    ORDER BY created_at DESC
                ''', (chat_type,))
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_file(self, file_id):
        """Удаляет информацию о файле"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM files WHERE file_id = ?', (file_id,))
            return cursor.rowcount > 0
    
    # === Статистика ===
    
    def get_stats(self):
        """Возвращает статистику базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM users')
            users_count = cursor.fetchone()['count']
            cursor.execute('SELECT COUNT(*) as count FROM messages')
            messages_count = cursor.fetchone()['count']
            cursor.execute('SELECT COUNT(*) as count FROM private_messages')
            private_count = cursor.fetchone()['count']
            cursor.execute('SELECT COUNT(*) as count FROM groups')
            groups_count = cursor.fetchone()['count']
            cursor.execute('SELECT COUNT(*) as count FROM files')
            files_count = cursor.fetchone()['count']
            
            return {
                'users': users_count,
                'messages': messages_count,
                'private_messages': private_count,
                'groups': groups_count,
                'files': files_count
            }