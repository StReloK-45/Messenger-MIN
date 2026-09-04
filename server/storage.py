# server/storage.py
import json
import os

class Storage:
    def __init__(self, config):
        self.config = config
        os.makedirs(self.config.DATA_DIR, exist_ok=True)
        
        self.users_db = {}
        self.messages_history = []
        self.files_list = []
        self.private_messages = {}
        self.message_counter = 0
        self.banned_ips = set()
        self.friends = {}
        self.groups = {}
        
        self.load_all()
    
    def load_all(self):
        self.load_users()
        self.load_history()
        self.load_private_messages()
        self.load_bans()
        self.load_friends()
        self.load_groups()
    
    def load_users(self):
        if os.path.exists(self.config.USERS_FILE):
            try:
                with open(self.config.USERS_FILE, 'r', encoding='utf-8') as f:
                    self.users_db = json.load(f)
            except:
                self.users_db = {}
        else:
            self.users_db = {}
            self.save_users()
    
    def load_history(self):
        if os.path.exists(self.config.CHAT_HISTORY_FILE):
            try:
                with open(self.config.CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.messages_history = data.get('messages', [])
                    self.files_list = data.get('files', [])
                    self.message_counter = data.get('counter', 0)
            except:
                self.messages_history = []
                self.files_list = []
                self.message_counter = 0
    
    def load_private_messages(self):
        if os.path.exists(self.config.PRIVATE_MESSAGES_FILE):
            try:
                with open(self.config.PRIVATE_MESSAGES_FILE, 'r', encoding='utf-8') as f:
                    self.private_messages = json.load(f)
            except:
                self.private_messages = {}
    
    def load_bans(self):
        if os.path.exists(self.config.BANNED_IPS_FILE):
            try:
                with open(self.config.BANNED_IPS_FILE, 'r') as f:
                    self.banned_ips = set(json.load(f))
            except:
                self.banned_ips = set()
    
    def load_friends(self):
        friends_file = os.path.join(self.config.DATA_DIR, "friends.json")
        try:
            if os.path.exists(friends_file):
                with open(friends_file, 'r', encoding='utf-8') as f:
                    self.friends = json.load(f)
            else:
                self.friends = {}
        except:
            self.friends = {}
    
    def load_groups(self):
        groups_file = os.path.join(self.config.DATA_DIR, "groups.json")
        try:
            if os.path.exists(groups_file):
                with open(groups_file, 'r', encoding='utf-8') as f:
                    self.groups = json.load(f)
            else:
                self.groups = {}
        except:
            self.groups = {}
    
    def save_users(self):
        with open(self.config.USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.users_db, f, ensure_ascii=False, indent=2)
    
    def save_history(self):
        clean_files = []
        for f in self.files_list:
            clean_files.append({
                'id': str(f.get('id', '')), 'name': str(f.get('name', '')),
                'path': str(f.get('path', '')), 'size': int(f.get('size', 0)),
                'sender': str(f.get('sender', '')), 'date': str(f.get('date', '')),
                'chat': str(f.get('chat', 'general'))
            })
        
        clean_messages = []
        for m in self.messages_history:
            clean_messages.append({
                'id': str(m.get('id', '')), 'sender': str(m.get('sender', '')),
                'text': str(m.get('text', '')), 'time': str(m.get('time', '')),
                'edited': bool(m.get('edited', False))
            })
        
        data = {'messages': clean_messages, 'files': clean_files, 'counter': int(self.message_counter)}
        
        with open(self.config.CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=True, indent=2)
    
    def save_private_messages(self):
        with open(self.config.PRIVATE_MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.private_messages, f, ensure_ascii=True, indent=2)
    
    def save_bans(self):
        with open(self.config.BANNED_IPS_FILE, 'w') as f:
            json.dump(list(self.banned_ips), f)
    
    def save_friends(self):
        friends_file = os.path.join(self.config.DATA_DIR, "friends.json")
        try:
            with open(friends_file, 'w', encoding='utf-8') as f:
                json.dump(self.friends, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения друзей: {e}")
    
    def save_groups(self):
        groups_file = os.path.join(self.config.DATA_DIR, "groups.json")
        try:
            with open(groups_file, 'w', encoding='utf-8') as f:
                json.dump(self.groups, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения групп: {e}")
    
    def get_friends(self, username):
        return self.friends.get(username, [])
    
    def add_friend(self, user1, user2):
        if user1 not in self.friends:
            self.friends[user1] = []
        if user2 not in self.friends:
            self.friends[user2] = []
        
        if user2 not in self.friends[user1]:
            self.friends[user1].append(user2)
        if user1 not in self.friends[user2]:
            self.friends[user2].append(user1)
        
        self.save_friends()
        return True
    
    def create_group(self, group_name, creator, members):
        if group_name in self.groups:
            return False
        
        self.groups[group_name] = {
            "creator": creator,
            "members": members,
            "messages": [],
            "files": []
        }
        self.save_groups()
        return True
    
    def add_member_to_group(self, group_name, member):
        if group_name not in self.groups:
            return False
        if member not in self.groups[group_name]["members"]:
            self.groups[group_name]["members"].append(member)
            self.save_groups()
        return True
    
    def get_group_members(self, group_name):
        return self.groups.get(group_name, {}).get("members", [])
    
    def add_group_message(self, group_name, message):
        if group_name in self.groups:
            self.groups[group_name]["messages"].append(message)
            self.save_groups()
    
    def get_group_messages(self, group_name):
        return self.groups.get(group_name, {}).get("messages", [])
    
    def add_group_file(self, group_name, file_info):
        if group_name in self.groups:
            self.groups[group_name]["files"].append(file_info)
            self.save_groups()
    
    def get_group_files(self, group_name):
        return self.groups.get(group_name, {}).get("files", [])