# server/database.py
import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        self.init_db()
    
    @contextmanager
    def get_connection(self):
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
                    nickname TEXT DEFAULT ''
                )
            ''')
            
            # Таблица для общих сообщений
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
                    is_read BOOLEAN DEFAULT 0,
                    delivered_at TIMESTAMP
                )
            ''')
            
            # Таблица для оффлайн-сообщений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS offline_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_private BOOLEAN DEFAULT 1,
                    delivered BOOLEAN DEFAULT 0,
                    delivered_at TIMESTAMP
                )
            ''')
            
            # Таблица для забаненных
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS banned (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identifier TEXT UNIQUE NOT NULL,
                    reason TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            ''')
            
            # Таблица для сессий
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
            
            # Таблица для сообщений в группах - ИСПРАВЛЕНО: sender_nickname вместо sender_name
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
            
            self._create_indexes(cursor)
    
    def _create_indexes(self, cursor):
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_private_messages_users ON private_messages(sender, recipient)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_private_messages_timestamp ON private_messages(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_online ON users(is_online)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_messages_group ON group_messages(group_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_offline_messages_recipient ON offline_messages(recipient, delivered)')
        except sqlite3.OperationalError as e:
            print(f"Warning: Could not create some indexes - {e}")
    
    # === Users ===
    
    def create_user(self, username, password_hash, salt, is_admin=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (username, password_hash, salt, is_admin, created_at, last_seen, nickname) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (username, password_hash, salt, 1 if is_admin else 0, datetime.now(), datetime.now(), username))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None
    
    def get_user(self, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_user_by_id(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, nickname, is_admin, is_online, last_seen FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_last_seen(self, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_seen = ?, is_online = 1 WHERE username = ?
            ''', (datetime.now(), username))
    
    def set_user_offline(self, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_online = 0 WHERE username = ?', (username,))
    
    def get_all_users(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, nickname, is_admin, is_online, last_seen FROM users')
            return [dict(row) for row in cursor.fetchall()]
    
    def demote_admin(self, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_admin = 0 WHERE username = ?', (username,))
            return cursor.rowcount > 0
    
    def update_user_nickname(self, username, new_nickname):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET nickname = ? WHERE username = ?', (new_nickname, username))
            return cursor.rowcount > 0
    
    # === Messages ===
    
    def save_message(self, sender, message, is_private=False, recipient=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO messages (sender, message, timestamp, is_private, recipient) 
                VALUES (?, ?, ?, ?, ?)
            ''', (sender, message, datetime.now(), is_private, recipient))
            return cursor.lastrowid
    
    def get_chat_history(self, limit=100):
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
    
    # === Offline Messages (NEW) ===
    
    def save_offline_message(self, recipient, sender, message, is_private=True):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO offline_messages (recipient, sender, message, is_private, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (recipient, sender, message, is_private, datetime.now()))
            return cursor.lastrowid
    
    def get_offline_messages(self, recipient):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sender, message, timestamp, is_private 
                FROM offline_messages 
                WHERE recipient = ? AND delivered = 0
                ORDER BY timestamp ASC
            ''', (recipient,))
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_offline_messages_delivered(self, message_ids):
        if not message_ids:
            return 0
        placeholders = ','.join('?' * len(message_ids))
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE offline_messages 
                SET delivered = 1, delivered_at = ? 
                WHERE id IN ({placeholders})
            ''', (datetime.now(), *message_ids))
            return cursor.rowcount
    
    def delete_old_offline_messages(self, days=30):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff = datetime.now().timestamp() - (days * 86400)
            cursor.execute('DELETE FROM offline_messages WHERE julianday(datetime(timestamp)) < julianday("now", ?)', (f'-{days} days',))
            return cursor.rowcount
    
    # === Private Messages ===
    
    def save_private_message(self, sender, recipient, message):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO private_messages (sender, recipient, message, timestamp, delivered_at) 
                VALUES (?, ?, ?, ?, ?)
            ''', (sender, recipient, message, datetime.now(), datetime.now()))
            return cursor.lastrowid
    
    def get_private_messages(self, user1, user2, limit=100):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sender, recipient, message, timestamp 
                FROM private_messages 
                WHERE (sender = ? AND recipient = ?) OR (sender = ? AND recipient = ?)
                ORDER BY timestamp ASC LIMIT ?
            ''', (user1, user2, user2, user1, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_private_messages_read(self, sender, recipient):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE private_messages 
                SET is_read = 1 
                WHERE sender = ? AND recipient = ? AND is_read = 0
            ''', (sender, recipient))
            return cursor.rowcount
    
    # === Bans ===
    
    def ban_ip(self, ip_address, reason=None, expires_at=None):
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
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM banned 
                WHERE identifier = ? AND (expires_at IS NULL OR expires_at > ?)
            ''', (identifier, datetime.now()))
            return cursor.fetchone() is not None
    
    def get_banned_ips(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT identifier, reason, banned_at, expires_at FROM banned')
            return [dict(row) for row in cursor.fetchall()]
    
    def unban_ip(self, ip_address):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM banned WHERE identifier = ?', (ip_address,))
            return cursor.rowcount > 0
    
    # === Sessions ===
    
    def create_session(self, username, token, ip_address, expires_at):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (username, token, ip_address, expires_at) 
                VALUES (?, ?, ?, ?)
            ''', (username, token, ip_address, expires_at))
            return cursor.lastrowid
    
    def get_session(self, token):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM sessions WHERE token = ? AND expires_at > ?
            ''', (token, datetime.now()))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def delete_session(self, token):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
    
    def delete_expired_sessions(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM sessions WHERE expires_at <= ?', (datetime.now(),))
            return cursor.rowcount
    
    # === Groups ===
    
    def create_group(self, name, creator_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO groups (name, creator_id) VALUES (?, ?)', (name, creator_id))
                group_id = cursor.lastrowid
                cursor.execute('INSERT INTO group_members (group_id, user_id) VALUES (?, ?)', (group_id, creator_id))
                return group_id
            except sqlite3.IntegrityError:
                return None
    
    def rename_group(self, group_id, new_name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE groups SET name = ? WHERE id = ?', (new_name, group_id))
            return cursor.rowcount > 0
    
    def add_group_member(self, group_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (?, ?)', (group_id, user_id))
            return cursor.rowcount > 0
    
    def remove_group_member(self, group_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, user_id))
            return cursor.rowcount > 0
    
    def get_group_by_name(self, name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups WHERE name = ?', (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_group_by_id(self, group_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups WHERE id = ?', (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_group_members(self, group_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.id, u.username, u.nickname 
                FROM group_members gm 
                JOIN users u ON gm.user_id = u.id 
                WHERE gm.group_id = ?
            ''', (group_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_group_member_names(self, group_id):
        members = self.get_group_members(group_id)
        return [m.get('nickname', m.get('username', '')) for m in members]
    
    def get_user_groups(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT g.id, g.name, g.created_at, g.creator_id
                FROM groups g 
                JOIN group_members gm ON g.id = gm.group_id 
                WHERE gm.user_id = ?
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_group(self, group_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM group_messages WHERE group_id = ?', (group_id,))
            cursor.execute('DELETE FROM group_members WHERE group_id = ?', (group_id,))
            cursor.execute('DELETE FROM groups WHERE id = ?', (group_id,))
            return True
    
    def save_group_message(self, group_id, sender_id, sender_nickname, message):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO group_messages (group_id, sender_id, sender_nickname, message, timestamp) 
                VALUES (?, ?, ?, ?, ?)
            ''', (group_id, sender_id, sender_nickname, message, datetime.now()))
            return cursor.lastrowid
    
    def get_group_messages(self, group_id, limit=100):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT sender_nickname as sender, message, timestamp 
                FROM group_messages 
                WHERE group_id = ? 
                ORDER BY timestamp ASC LIMIT ?
            ''', (group_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    # === Files ===
    
    def save_file(self, file_id, name, path, size, sender_id, sender_nickname, chat_type, chat_target, date):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO files (file_id, name, path, size, sender_id, sender_nickname, chat_type, chat_target, date) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (file_id, name, path, size, sender_id, sender_nickname, chat_type, chat_target, date))
            return cursor.lastrowid
    
    def get_file_by_id(self, file_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM files WHERE file_id = ?', (file_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_files_by_chat(self, chat_type, chat_target=None):
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
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM files WHERE file_id = ?', (file_id,))
            return cursor.rowcount > 0
    
    # === Stats ===
    
    def get_stats(self):
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
            cursor.execute('SELECT COUNT(*) as count FROM offline_messages WHERE delivered = 0')
            offline_count = cursor.fetchone()['count']
            
            return {
                'users': users_count,
                'messages': messages_count,
                'private_messages': private_count,
                'groups': groups_count,
                'files': files_count,
                'offline_messages': offline_count
            }
    
    # === Friends ===
    
    def add_friend(self, user_id, friend_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS friends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    friend_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    UNIQUE(user_id, friend_id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (friend_id) REFERENCES users(id)
                )
            ''')
            try:
                cursor.execute('INSERT INTO friends (user_id, friend_id) VALUES (?, ?)', (user_id, friend_id))
                return True
            except sqlite3.IntegrityError:
                return False
    
    def get_friends(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS friends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    friend_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'accepted',
                    UNIQUE(user_id, friend_id)
                )
            ''')
            cursor.execute('''
                SELECT u.username, u.nickname 
                FROM friends f 
                JOIN users u ON f.friend_id = u.id 
                WHERE f.user_id = ? AND f.status = 'accepted'
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]