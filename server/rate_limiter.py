import time
from collections import defaultdict

class RateLimiter:
    def __init__(self):
        self.limits = {
            'message': {'count': 10, 'period': 5},
            'group_create': {'count': 3, 'period': 60},
            'group_add': {'count': 10, 'period': 60},
            'friend_request': {'count': 5, 'period': 30},
            'login': {'count': 3, 'period': 10},
            'register': {'count': 2, 'period': 60},
        }
        self.actions = defaultdict(list)
        self.blacklist = {}
    
    def check_limit(self, user_id, action_type):
        if user_id in self.blacklist:
            if time.time() < self.blacklist[user_id]:
                return False
            del self.blacklist[user_id]
        
        if action_type not in self.limits:
            return True
        
        limit = self.limits[action_type]
        now = time.time()
        cutoff = now - limit['period']
        
        self.actions[user_id] = [t for t in self.actions[user_id] if t > cutoff]
        
        if len(self.actions[user_id]) >= limit['count']:
            self.blacklist[user_id] = now + 30
            return False
        
        self.actions[user_id].append(now)
        return True
    
    def get_remaining_time(self, user_id, action_type):
        if user_id in self.blacklist:
            return int(self.blacklist[user_id] - time.time())
        return 0