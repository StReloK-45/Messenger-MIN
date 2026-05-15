# server/storage.py
import os
from database import Database
from typing import Optional, List, Dict, Any

class Storage:
    def __init__(self, config):
        self.config = config
        self.db = Database(config.DATABASE_PATH)
        self._load_cache()
        print(f"✅ Storage инициализирован (SQLite)")
    
    def _load_cache(self):
        pass
    
    # ========== Пользователи ==========
    
    def get_user(self, username: str) -> Optional[Dict]:
        return self.db.get_user(username)
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        return self.db.get_user_by_id(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        return self.get_user(username)
    
    def create_user(self, username: str, password_hash: str, salt: str, is_admin: bool = False) -> Optional[int]:
        return self.db.create_user(username, password_hash, salt, is_admin)
    
    def get_all_users(self) -> List[Dict]:
        return self.db.get_all_users()
    
    def update_user_status(self, username: str, is_online: bool):
        if is_online:
            self.db.update_last_seen(username)
        else:
            self.db.set_user_offline(username)
    
    def demote_admin(self, username: str) -> bool:
        return self.db.demote_admin(username)
    
    # ========== Группы ==========
    
    def create_group(self, name: str, creator_id: int, encrypted: bool = False) -> Optional[int]:
        return self.db.create_group(name, creator_id, encrypted)
    
    def get_group(self, group_id: int) -> Optional[Dict]:
        return self.db.get_group(group_id)
    
    def get_group_by_name(self, name: str) -> Optional[Dict]:
        return self.db.get_group_by_name(name)
    
    def update_group_name(self, group_id: int, new_name: str) -> bool:
        return self.db.update_group_name(group_id, new_name)
    
    def delete_group(self, group_id: int) -> bool:
        return self.db.delete_group(group_id)
    
    def add_group_member(self, group_id: int, user_id: int, is_admin: bool = False) -> bool:
        return self.db.add_group_member(group_id, user_id, is_admin)
    
    def remove_group_member(self, group_id: int, user_id: int) -> bool:
        return self.db.remove_group_member(group_id, user_id)
    
    def get_group_members(self, group_id: int) -> List[Dict]:
        return self.db.get_group_members(group_id)
    
    def get_group_member(self, group_id: int, user_id: int) -> Optional[Dict]:
        return self.db.get_group_member(group_id, user_id)
    
    def set_group_member_admin(self, group_id: int, user_id: int, is_admin: bool) -> bool:
        return self.db.set_group_member_admin(group_id, user_id, is_admin)
    
    def ban_group_member(self, group_id: int, user_id: int, admin_id: int) -> bool:
        return self.db.ban_group_member(group_id, user_id, admin_id)
    
    def unban_group_member(self, group_id: int, user_id: int) -> bool:
        return self.db.unban_group_member(group_id, user_id)
    
    def is_group_admin(self, group_id: int, user_id: int) -> bool:
        return self.db.is_group_admin(group_id, user_id)
    
    def is_group_creator(self, group_id: int, user_id: int) -> bool:
        return self.db.is_group_creator(group_id, user_id)
    
    def get_user_groups(self, user_id: int) -> List[Dict]:
        return self.db.get_user_groups(user_id)
    
    def save_group_message(self, group_id: int, sender_id: int, sender_name: str, message: str, encrypted: bool = False) -> int:
        return self.db.save_group_message(group_id, sender_id, sender_name, message, encrypted)
    
    def get_group_messages(self, group_id: int, limit: int = 100) -> List[Dict]:
        return self.db.get_group_messages(group_id, limit)
    
    def delete_group_message(self, message_id: int, admin_id: int) -> bool:
        return self.db.delete_group_message(message_id, admin_id)
    
    def clear_group_history(self, group_id: int) -> bool:
        return self.db.clear_group_history(group_id)
    
    # ========== Файлы групп ==========
    
    def save_group_file(self, file_id: str, group_id: int, name: str, path: str, 
                        size: int, sender_id: int, sender_name: str, date: str) -> int:
        return self.db.save_group_file(file_id, group_id, name, path, size, sender_id, sender_name, date)
    
    def get_group_files(self, group_id: int) -> List[Dict]:
        return self.db.get_group_files(group_id)
    
    def delete_group_file(self, file_id: str, admin_id: int) -> bool:
        return self.db.delete_group_file(file_id, admin_id)
    
    # ========== Общие сообщения ==========
    
    def save_message(self, sender: str, message: str, is_private: bool = False, recipient: str = None) -> int:
        return self.db.save_message(sender, message, is_private, recipient)
    
    def get_chat_history(self, limit: int = 100) -> List[Dict]:
        return self.db.get_chat_history(limit)
    
    def get_messages_history(self, limit: int = 100) -> List[Dict]:
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
    
    # ========== Приватные сообщения ==========
    
    def save_private_message(self, sender: str, recipient: str, message: str) -> int:
        return self.db.save_private_message(sender, recipient, message)
    
    def get_private_messages(self, user1: str, user2: str, limit: int = 100) -> List[Dict]:
        return self.db.get_private_messages(user1, user2, limit)
    
    # ========== Баны ==========
    
    def ban_ip(self, ip: str, reason: str = None) -> bool:
        return self.db.ban_ip(ip, reason)
    
    def is_banned(self, ip: str) -> bool:
        return self.db.is_banned(ip)
    
    def unban_ip(self, ip: str) -> bool:
        return self.db.unban_ip(ip)
    
    def get_banned_ips(self) -> List[str]:
        bans = self.db.get_banned_ips()
        return [b.get('identifier', '') for b in bans if b.get('identifier')]
    
    # ========== Статистика ==========
    
    def get_stats(self) -> Dict:
        return self.db.get_stats()