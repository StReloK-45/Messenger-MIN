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
                    nickname TEXT DEFAULT '',
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP,
                    is_online BOOLEAN DEFAULT 0,
                    avatar_url TEXT
                )
            ''')
            
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN nickname TEXT DEFAULT ''")
            except:
                pass
            
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
                    is_read BOOLEAN DEFAULT 0
                )
            ''')
            
            # Таблица для групп (ПОЛНАЯ ВЕРСИЯ)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    creator_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    encrypted BOOLEAN DEFAULT 0,
                    encryption_key TEXT,
                    FOREIGN KEY (creator_id) REFERENCES users(id)
                )
            ''')
            
            # Таблица для участников групп
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    is_admin BOOLEAN DEFAULT 0,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_banned BOOLEAN DEFAULT 0,
                    banned_at TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
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
                    sender_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN DEFAULT 0,
                    deleted_by INTEGER,
                    encrypted BOOLEAN DEFAULT 0,
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
                    FOREIGN KEY (sender_id) REFERENCES users(id)
                )
            ''')
            
            # Таблица для файлов групп
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS group_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id TEXT UNIQUE NOT NULL,
                    group_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    sender_id INTEGER NOT NULL,
                    sender_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted BOOLEAN DEFAULT 0,
                    deleted_by INTEGER,
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
                    FOREIGN KEY (sender_id) REFERENCES users(id)
                )
            ''')
            
            self._create_indexes(cursor)
    
    def _create_indexes(self, cursor):
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_messages_group ON group_messages(group_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_files_group ON group_files(group_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        except:
            pass
    
    # ========== Методы для групп ==========
    
    def create_group(self, name: str, creator_id: int, encrypted: bool = False) -> Optional[int]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO groups (name, creator_id, encrypted) 
                    VALUES (?, ?, ?)
                ''', (name, creator_id, 1 if encrypted else 0))
                group_id = cursor.lastrowid
                # Создатель - сразу админ
                cursor.execute('''
                    INSERT INTO group_members (group_id, user_id, is_admin) 
                    VALUES (?, ?, ?)
                ''', (group_id, creator_id, 1))
                return group_id
            except sqlite3.IntegrityError:
                return None
    
    def get_group(self, group_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups WHERE id = ?', (group_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_group_by_name(self, name: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM groups WHERE name = ?', (name,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_group_name(self, group_id: int, new_name: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE groups SET name = ? WHERE id = ?', (new_name, group_id))
            return cursor.rowcount > 0
    
    def delete_group(self, group_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Всё каскадно удалится благодаря ON DELETE CASCADE
            cursor.execute('DELETE FROM groups WHERE id = ?', (group_id,))
            return cursor.rowcount > 0
    
    def add_group_member(self, group_id: int, user_id: int, is_admin: bool = False) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO group_members (group_id, user_id, is_admin) 
                VALUES (?, ?, ?)
            ''', (group_id, user_id, 1 if is_admin else 0))
            return cursor.rowcount > 0
    
    def remove_group_member(self, group_id: int, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM group_members WHERE group_id = ? AND user_id = ?', (group_id, user_id))
            return cursor.rowcount > 0
    
    def get_group_members(self, group_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.id, u.username, u.nickname, gm.is_admin, gm.joined_at, gm.is_banned
                FROM group_members gm 
                JOIN users u ON gm.user_id = u.id 
                WHERE gm.group_id = ? AND gm.is_banned = 0
            ''', (group_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_group_member(self, group_id: int, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM group_members 
                WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def set_group_member_admin(self, group_id: int, user_id: int, is_admin: bool) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE group_members SET is_admin = ? 
                WHERE group_id = ? AND user_id = ?
            ''', (1 if is_admin else 0, group_id, user_id))
            return cursor.rowcount > 0
    
    def ban_group_member(self, group_id: int, user_id: int, admin_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE group_members SET is_banned = 1, banned_at = ? 
                WHERE group_id = ? AND user_id = ?
            ''', (datetime.now(), group_id, user_id))
            return cursor.rowcount > 0
    
    def unban_group_member(self, group_id: int, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE group_members SET is_banned = 0, banned_at = NULL 
                WHERE group_id = ? AND user_id = ?
            ''', (group_id, user_id))
            return cursor.rowcount > 0
    
    def is_group_admin(self, group_id: int, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_admin FROM group_members 
                WHERE group_id = ? AND user_id = ? AND is_banned = 0
            ''', (group_id, user_id))
            row = cursor.fetchone()
            return row and row['is_admin'] == 1
    
    def is_group_creator(self, group_id: int, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT creator_id FROM groups WHERE id = ?', (group_id,))
            row = cursor.fetchone()
            return row and row['creator_id'] == user_id
    
    def get_user_groups(self, user_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT g.id, g.name, g.created_at, g.encrypted, gm.is_admin
                FROM groups g 
                JOIN group_members gm ON g.id = gm.group_id 
                WHERE gm.user_id = ? AND gm.is_banned = 0
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def save_group_message(self, group_id: int, sender_id: int, sender_name: str, message: str, encrypted: bool = False) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO group_messages (group_id, sender_id, sender_name, message, encrypted) 
                VALUES (?, ?, ?, ?, ?)
            ''', (group_id, sender_id, sender_name, message, 1 if encrypted else 0))
            return cursor.lastrowid
    
    def get_group_messages(self, group_id: int, limit: int = 100) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sender_name as sender, message, timestamp, encrypted
                FROM group_messages 
                WHERE group_id = ? AND is_deleted = 0
                ORDER BY timestamp ASC LIMIT ?
            ''', (group_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_group_message(self, message_id: int, admin_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE group_messages SET is_deleted = 1, deleted_by = ? 
                WHERE id = ?
            ''', (admin_id, message_id))
            return cursor.rowcount > 0
    
    def clear_group_history(self, group_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM group_messages WHERE group_id = ?', (group_id,))
            return True
    
    # ========== Методы для файлов групп ==========
    
    def save_group_file(self, file_id: str, group_id: int, name: str, path: str, 
                        size: int, sender_id: int, sender_name: str, date: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO group_files (file_id, group_id, name, path, size, sender_id, sender_name, date) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (file_id, group_id, name, path, size, sender_id, sender_name, date))
            return cursor.lastrowid
    
    def get_group_files(self, group_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT file_id, name, size, sender_name, date 
                FROM group_files 
                WHERE group_id = ? AND is_deleted = 0
                ORDER BY created_at DESC
            ''', (group_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_group_file(self, file_id: str, admin_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE group_files SET is_deleted = 1, deleted_by = ? 
                WHERE file_id = ?
            ''', (admin_id, file_id))
            return cursor.rowcount > 0
    
    # ========== Старые методы для совместимости ==========
    
    def get_user(self, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_user_by_id(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_all_users(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, username, nickname, is_admin, is_online, last_seen FROM users')
            return [dict(row) for row in cursor.fetchall()]
    
    def create_user(self, username, password_hash, salt, is_admin=False):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (username, nickname, password_hash, salt, is_admin, created_at, last_seen) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (username, username, password_hash, salt, 1 if is_admin else 0, datetime.now(), datetime.now()))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                return None
    
    def update_last_seen(self, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET last_seen = ?, is_online = 1 WHERE username = ?', (datetime.now(), username))
    
    def set_user_offline(self, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_online = 0 WHERE username = ?', (username,))
    
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
    
    def save_private_message(self, sender, recipient, message):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO private_messages (sender, recipient, message, timestamp) 
                VALUES (?, ?, ?, ?)
            ''', (sender, recipient, message, datetime.now()))
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
    
    def unban_ip(self, ip_address):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM banned WHERE identifier = ?', (ip_address,))
            return cursor.rowcount > 0
    
    def get_banned_ips(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT identifier, reason, banned_at, expires_at FROM banned')
            return [dict(row) for row in cursor.fetchall()]
    
    def demote_admin(self, username):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET is_admin = 0 WHERE username = ?', (username,))
            return cursor.rowcount > 0
    
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
            cursor.execute('SELECT COUNT(*) as count FROM group_files')
            files_count = cursor.fetchone()['count']
            return {
                'users': users_count,
                'messages': messages_count,
                'private_messages': private_count,
                'groups': groups_count,
                'files': files_count
            }