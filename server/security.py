# server/security.py
import re
import html
import hashlib
import secrets
import base64
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

# ========== Валидаторы ==========

class SecurityValidator:
    MAX_USERNAME = 20
    MIN_USERNAME = 3
    MAX_PASSWORD = 100
    MIN_PASSWORD = 4
    MAX_NICKNAME = 30
    MAX_GROUP_NAME = 30
    MAX_MESSAGE = 500000
    
    @classmethod
    def validate_username(cls, username: str) -> Tuple[bool, str]:
        if not username:
            return False, "Логин не может быть пустым"
        if len(username) < cls.MIN_USERNAME:
            return False, f"Логин должен быть не менее {cls.MIN_USERNAME} символов"
        if len(username) > cls.MAX_USERNAME:
            return False, f"Логин должен быть не более {cls.MAX_USERNAME} символов"
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            return False, "Логин может содержать только буквы, цифры, _ и -"
        return True, ""
    
    @classmethod
    def validate_password(cls, password: str) -> Tuple[bool, str]:
        if not password:
            return False, "Пароль не может быть пустым"
        if len(password) < cls.MIN_PASSWORD:
            return False, f"Пароль должен быть не менее {cls.MIN_PASSWORD} символов"
        if len(password) > cls.MAX_PASSWORD:
            return False, f"Пароль должен быть не более {cls.MAX_PASSWORD} символов"
        return True, ""
    
    @classmethod
    def validate_nickname(cls, nickname: str) -> Tuple[bool, str]:
        if not nickname:
            return False, "Никнейм не может быть пустым"
        if len(nickname) > cls.MAX_NICKNAME:
            return False, f"Никнейм должен быть не более {cls.MAX_NICKNAME} символов"
        return True, ""
    
    @classmethod
    def validate_group_name(cls, name: str) -> Tuple[bool, str]:
        if not name:
            return False, "Название группы не может быть пустым"
        if len(name) > cls.MAX_GROUP_NAME:
            return False, f"Название группы должно быть не более {cls.MAX_GROUP_NAME} символов"
        return True, ""
    
    @classmethod
    def sanitize_text(cls, text: str, max_length: int = MAX_MESSAGE) -> str:
        if not text:
            return ""
        text = text[:max_length]
        text = html.escape(text)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        return text.strip()


# ========== Простое хеширование паролей (без внешних библиотек) ==========

class SimpleHash:
    """Простое хеширование паролей с солью"""
    
    @staticmethod
    def generate_salt(length: int = 16) -> str:
        """Генерирует случайную соль"""
        return secrets.token_hex(length)
    
    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """Хеширует пароль с солью"""
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    
    @staticmethod
    def verify_password(password: str, salt: str, hashed: str) -> bool:
        """Проверяет пароль"""
        return SimpleHash.hash_password(password, salt) == hashed


# ========== Простой JWT-подобный токен (без внешних библиотек) ==========

class SimpleJWT:
    """Простая реализация JWT-подобных токенов без внешних зависимостей"""
    
    SECRET_KEY = "messenger-super-secret-key-2024-change-in-production"
    TOKEN_EXPIRE_DAYS = 7
    
    @classmethod
    def create_token(cls, username: str) -> str:
        """Создаёт токен для пользователя"""
        expire = datetime.now() + timedelta(days=cls.TOKEN_EXPIRE_DAYS)
        
        payload = {
            "sub": username,
            "exp": expire.timestamp(),
            "iat": datetime.now().timestamp()
        }
        
        # Кодируем payload в base64
        payload_json = json.dumps(payload)
        payload_b64 = base64.b64encode(payload_json.encode()).decode()
        
        # Создаём подпись
        signature = hashlib.sha256(f"{payload_b64}{cls.SECRET_KEY}".encode()).hexdigest()[:32]
        
        # Формируем токен
        token = f"{payload_b64}.{signature}"
        return token
    
    @classmethod
    def verify_token(cls, token: str) -> Optional[Dict]:
        """Проверяет токен и возвращает payload"""
        try:
            if '.' not in token:
                return None
            
            payload_b64, signature = token.split('.')
            
            # Проверяем подпись
            expected_signature = hashlib.sha256(f"{payload_b64}{cls.SECRET_KEY}".encode()).hexdigest()[:32]
            if signature != expected_signature:
                return None
            
            # Декодируем payload
            payload_json = base64.b64decode(payload_b64.encode()).decode()
            payload = json.loads(payload_json)
            
            # Проверяем срок действия
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.now():
                return None
            
            return payload
        except Exception:
            return None
    
    @classmethod
    def get_username(cls, token: str) -> Optional[str]:
        """Извлекает username из токена"""
        payload = cls.verify_token(token)
        if payload:
            return payload.get("sub")
        return None


# ========== Класс для работы с паролями (совместимость со старым кодом) ==========

def hash_password(password: str) -> str:
    """Хеширует пароль (для обратной совместимости с utils.py)"""
    return hashlib.sha256(password.encode()).hexdigest()[:32]


def verify_password(password: str, hashed: str) -> bool:
    """Проверяет пароль"""
    return hash_password(password) == hashed