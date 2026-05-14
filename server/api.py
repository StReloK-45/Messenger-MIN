# server/api.py
import asyncio
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from config import ChatConfig
from storage import Storage
from security import SecurityValidator, SimpleJWT, SimpleHash


# ========== Pydantic модели ==========

class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    nickname: str
    is_admin: bool

class UserResponse(BaseModel):
    username: str
    nickname: str
    is_online: bool
    is_admin: bool
    last_seen: Optional[str] = None

class MessageResponse(BaseModel):
    id: int
    sender: str
    message: str
    timestamp: str

class MessageSend(BaseModel):
    message: str
    recipient: Optional[str] = None

class PrivateMessageResponse(BaseModel):
    id: int
    sender: str
    recipient: str
    message: str
    timestamp: str

class GroupCreate(BaseModel):
    name: str

class GroupAddMember(BaseModel):
    group_name: str
    member_nickname: str

class GroupMessageSend(BaseModel):
    group_name: str
    message: str

class GroupResponse(BaseModel):
    id: int
    name: str
    created_at: str
    members_count: int

class StatusResponse(BaseModel):
    status: str
    version: str
    users_count: int
    online_count: int
    websocket_connections: int


# ========== FastAPI приложение ==========

security_scheme = HTTPBearer(auto_error=False)


class ApiServer:
    def __init__(self, storage: Storage, config: ChatConfig, host: str = "0.0.0.0", port: int = 8000):
        self.storage = storage
        self.config = config
        self.host = host
        self.port = port
        self.app = FastAPI(title="Messenger API", version="2.0.0")
        
        # WebSocket менеджеры
        self.active_websockets: Dict[str, WebSocket] = {}
        self.ws_lock = asyncio.Lock()
        
        self._setup_routes()
        self._setup_cors()
    
    def _setup_cors(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
        """Dependency для получения текущего пользователя"""
        if not credentials:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        token = credentials.credentials
        username = SimpleJWT.get_username(token)
        
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = self.storage.get_user(username)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    
    def _setup_routes(self):
        
        # ========== Root ==========
        @self.app.get("/")
        async def root():
            return {
                "message": "Messenger API v2.0",
                "status": "running",
                "websocket": f"ws://{self.host}:{self.port}/ws",
                "docs": f"http://{self.host}:{self.port}/docs"
            }
        
        # ========== Аутентификация ==========
        
        @self.app.post("/api/auth/register", response_model=LoginResponse)
        async def register(req: RegisterRequest):
            """Регистрация нового пользователя"""
            # Валидация
            valid, err = SecurityValidator.validate_username(req.username)
            if not valid:
                raise HTTPException(status_code=400, detail=err)
            
            valid, err = SecurityValidator.validate_password(req.password)
            if not valid:
                raise HTTPException(status_code=400, detail=err)
            
            nickname = req.nickname or req.username
            valid, err = SecurityValidator.validate_nickname(nickname)
            if not valid:
                raise HTTPException(status_code=400, detail=err)
            
            # Проверка существования
            existing = self.storage.get_user(req.username)
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")
            
            # Создание пользователя
            salt = SimpleHash.generate_salt()
            password_hash = SimpleHash.hash_password(req.password, salt)
            
            user_id = self.storage.create_user(req.username, password_hash, salt)
            if not user_id:
                raise HTTPException(status_code=500, detail="Registration failed")
            
            # Создаём токен
            access_token = SimpleJWT.create_token(req.username)
            
            return LoginResponse(
                access_token=access_token,
                username=req.username,
                nickname=nickname,
                is_admin=False
            )
        
        @self.app.post("/api/auth/login", response_model=LoginResponse)
        async def login(req: LoginRequest):
            """Авторизация пользователя"""
            user = self.storage.get_user(req.username)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            # Проверка пароля
            if not SimpleHash.verify_password(req.password, user.get('salt', ''), user.get('password_hash', '')):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            # Обновляем статус
            self.storage.update_user_status(req.username, True)
            
            access_token = SimpleJWT.create_token(req.username)
            
            return LoginResponse(
                access_token=access_token,
                username=user['username'],
                nickname=user['username'],
                is_admin=bool(user.get('is_admin', False))
            )
        
        @self.app.post("/api/auth/logout")
        async def logout(current_user: dict = Depends(self._get_current_user)):
            """Выход из системы"""
            username = current_user['username']
            self.storage.update_user_status(username, False)
            
            # Закрываем WebSocket если есть
            async with self.ws_lock:
                if username in self.active_websockets:
                    try:
                        await self.active_websockets[username].close()
                    except:
                        pass
                    del self.active_websockets[username]
            
            return {"success": True}
        
        # ========== Пользователи ==========
        
        @self.app.get("/api/users", response_model=List[UserResponse])
        async def get_users(current_user: dict = Depends(self._get_current_user)):
            """Список всех пользователей"""
            users = self.storage.get_all_users()
            return [
                UserResponse(
                    username=u.get('username', ''),
                    nickname=u.get('username', ''),
                    is_online=bool(u.get('is_online', False)),
                    is_admin=bool(u.get('is_admin', False)),
                    last_seen=u.get('last_seen')
                )
                for u in users
            ]
        
        @self.app.get("/api/users/online")
        async def get_online_users(current_user: dict = Depends(self._get_current_user)):
            """Список онлайн пользователей"""
            users = self.storage.get_all_users()
            online = [u.get('username', '') for u in users if u.get('is_online')]
            return {"online": online, "count": len(online)}
        
        @self.app.get("/api/users/{username}")
        async def get_user(username: str, current_user: dict = Depends(self._get_current_user)):
            """Информация о пользователе"""
            user = self.storage.get_user(username)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {
                "username": user.get('username'),
                "is_online": bool(user.get('is_online', False)),
                "is_admin": bool(user.get('is_admin', False)),
                "last_seen": user.get('last_seen')
            }
        
        # ========== Сообщения ==========
        
        @self.app.get("/api/messages", response_model=List[MessageResponse])
        async def get_messages(limit: int = 100, current_user: dict = Depends(self._get_current_user)):
            """История сообщений общего чата"""
            messages = self.storage.get_chat_history(limit)
            return [
                MessageResponse(
                    id=i,
                    sender=m.get('sender', ''),
                    message=m.get('message', ''),
                    timestamp=m.get('timestamp', '')
                )
                for i, m in enumerate(messages)
            ]
        
        @self.app.post("/api/messages")
        async def send_message(req: MessageSend, current_user: dict = Depends(self._get_current_user)):
            """Отправка сообщения (общий чат или ЛС)"""
            sender = current_user['username']
            message = SecurityValidator.sanitize_text(req.message)
            
            if not message:
                raise HTTPException(status_code=400, detail="Empty message")
            
            if req.recipient:
                # Приватное сообщение
                self.storage.save_private_message(sender, req.recipient, message)
                
                # Отправляем через WebSocket если получатель онлайн
                async with self.ws_lock:
                    if req.recipient in self.active_websockets:
                        try:
                            await self.active_websockets[req.recipient].send_json({
                                "type": "private_message",
                                "from": sender,
                                "message": message,
                                "timestamp": datetime.now().isoformat()
                            })
                        except:
                            pass
                
                return {"success": True, "type": "private", "recipient": req.recipient}
            else:
                # Общий чат
                self.storage.save_message(sender, message)
                
                # Рассылаем всем через WebSocket
                async with self.ws_lock:
                    for ws in self.active_websockets.values():
                        try:
                            await ws.send_json({
                                "type": "message",
                                "sender": sender,
                                "message": message,
                                "timestamp": datetime.now().isoformat()
                            })
                        except:
                            pass
                
                return {"success": True, "type": "general"}
        
        # ========== Приватные сообщения ==========
        
        @self.app.get("/api/private/messages/{username}", response_model=List[PrivateMessageResponse])
        async def get_private_messages(
            username: str, 
            limit: int = 100, 
            current_user: dict = Depends(self._get_current_user)
        ):
            """История переписки с пользователем"""
            messages = self.storage.get_private_messages(current_user['username'], username, limit)
            return [
                PrivateMessageResponse(
                    id=i,
                    sender=m.get('sender', ''),
                    recipient=m.get('recipient', ''),
                    message=m.get('message', ''),
                    timestamp=m.get('timestamp', '')
                )
                for i, m in enumerate(messages)
            ]
        
        # ========== Группы ==========
        
        @self.app.post("/api/groups")
        async def create_group(req: GroupCreate, current_user: dict = Depends(self._get_current_user)):
            """Создание группы"""
            valid, err = SecurityValidator.validate_group_name(req.name)
            if not valid:
                raise HTTPException(status_code=400, detail=err)
            
            existing = self.storage.get_group_by_name(req.name)
            if existing:
                raise HTTPException(status_code=400, detail="Group already exists")
            
            user = self.storage.get_user(current_user['username'])
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            group_id = self.storage.create_group(req.name, user['id'])
            if not group_id:
                raise HTTPException(status_code=500, detail="Failed to create group")
            
            return {"success": True, "group_id": group_id, "name": req.name}
        
        @self.app.get("/api/groups", response_model=List[GroupResponse])
        async def get_user_groups(current_user: dict = Depends(self._get_current_user)):
            """Список групп пользователя"""
            user = self.storage.get_user(current_user['username'])
            groups = self.storage.get_user_groups(user['id'])
            return [
                GroupResponse(
                    id=g.get('id', 0),
                    name=g.get('name', ''),
                    created_at=g.get('created_at', ''),
                    members_count=0
                )
                for g in groups
            ]
        
        @self.app.post("/api/groups/add")
        async def add_group_member(req: GroupAddMember, current_user: dict = Depends(self._get_current_user)):
            """Добавление участника в группу"""
            group = self.storage.get_group_by_name(req.group_name)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            
            # Проверяем, что текущий пользователь - создатель группы
            creator_id = group.get('creator_id', 0)
            current_user_id = self.storage.get_user(current_user['username']).get('id', 0)
            if creator_id != current_user_id:
                raise HTTPException(status_code=403, detail="Only group creator can add members")
            
            member = self.storage.get_user(req.member_nickname)
            if not member:
                raise HTTPException(status_code=404, detail="User not found")
            
            self.storage.add_group_member(group['id'], member['id'])
            return {"success": True}
        
        @self.app.post("/api/groups/message")
        async def send_group_message(req: GroupMessageSend, current_user: dict = Depends(self._get_current_user)):
            """Отправка сообщения в группу"""
            group = self.storage.get_group_by_name(req.group_name)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            
            user = self.storage.get_user(current_user['username'])
            message = SecurityValidator.sanitize_text(req.message)
            
            if not message:
                raise HTTPException(status_code=400, detail="Empty message")
            
            self.storage.save_group_message(group['id'], user['id'], current_user['username'], message)
            
            # Рассылаем участникам группы
            members = self.storage.get_group_members(group['id'])
            member_names = [m.get('username', '') for m in members if m.get('username')]
            
            async with self.ws_lock:
                for name in member_names:
                    if name in self.active_websockets:
                        try:
                            await self.active_websockets[name].send_json({
                                "type": "group_message",
                                "group": req.group_name,
                                "sender": current_user['username'],
                                "message": message,
                                "timestamp": datetime.now().isoformat()
                            })
                        except:
                            pass
            
            return {"success": True}
        
        # ========== Статус ==========
        
        @self.app.get("/api/status", response_model=StatusResponse)
        async def get_status():
            """Статус сервера"""
            users = self.storage.get_all_users()
            return StatusResponse(
                status="online",
                version="2.0.0",
                users_count=len(users),
                online_count=sum(1 for u in users if u.get('is_online')),
                websocket_connections=len(self.active_websockets)
            )
        
        # ========== WebSocket ==========
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            username = None
            
            try:
                # Ждём аутентификацию
                auth_data = await websocket.receive_json()
                token = auth_data.get("token")
                
                if not token:
                    await websocket.close(code=1008, reason="No token provided")
                    return
                
                username = SimpleJWT.get_username(token)
                if not username:
                    await websocket.close(code=1008, reason="Invalid token")
                    return
                
                user = self.storage.get_user(username)
                if not user:
                    await websocket.close(code=1008, reason="User not found")
                    return
                
                # Регистрируем WebSocket
                async with self.ws_lock:
                    self.active_websockets[username] = websocket
                
                # Отправляем подтверждение
                await websocket.send_json({
                    "type": "connected",
                    "message": f"Welcome {username}!",
                    "users_online": len(self.active_websockets)
                })
                
                # Обновляем статус
                self.storage.update_user_status(username, True)
                
                # Оповещаем всех о новом пользователе
                async with self.ws_lock:
                    for ws_username, ws in self.active_websockets.items():
                        if ws_username != username:
                            try:
                                await ws.send_json({
                                    "type": "user_online",
                                    "username": username
                                })
                            except:
                                pass
                
                # Основной цикл обработки сообщений
                while True:
                    data = await websocket.receive_json()
                    msg_type = data.get("type")
                    
                    if msg_type == "message":
                        text = SecurityValidator.sanitize_text(data.get("text", ""))
                        if text:
                            self.storage.save_message(username, text)
                            
                            async with self.ws_lock:
                                for ws in self.active_websockets.values():
                                    try:
                                        await ws.send_json({
                                            "type": "message",
                                            "sender": username,
                                            "message": text,
                                            "timestamp": datetime.now().isoformat()
                                        })
                                    except:
                                        pass
                    
                    elif msg_type == "private":
                        recipient = data.get("recipient")
                        text = SecurityValidator.sanitize_text(data.get("text", ""))
                        
                        if recipient and text:
                            self.storage.save_private_message(username, recipient, text)
                            
                            async with self.ws_lock:
                                if recipient in self.active_websockets:
                                    try:
                                        await self.active_websockets[recipient].send_json({
                                            "type": "private_message",
                                            "from": username,
                                            "message": text,
                                            "timestamp": datetime.now().isoformat()
                                        })
                                    except:
                                        pass
                                
                                try:
                                    await websocket.send_json({
                                        "type": "private_sent",
                                        "to": recipient,
                                        "message": text
                                    })
                                except:
                                    pass
                    
                    elif msg_type == "typing":
                        target = data.get("target")
                        async with self.ws_lock:
                            if target and target in self.active_websockets:
                                try:
                                    await self.active_websockets[target].send_json({
                                        "type": "typing",
                                        "from": username
                                    })
                                except:
                                    pass
                    
                    elif msg_type == "ping":
                        try:
                            await websocket.send_json({"type": "pong"})
                        except:
                            pass
                    
                    elif msg_type == "get_users":
                        users = self.storage.get_all_users()
                        online_list = [u.get('username', '') for u in users if u.get('is_online')]
                        try:
                            await websocket.send_json({
                                "type": "users_list",
                                "users": online_list
                            })
                        except:
                            pass
            
            except WebSocketDisconnect:
                pass
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                if username:
                    async with self.ws_lock:
                        if username in self.active_websockets:
                            del self.active_websockets[username]
                    
                    self.storage.update_user_status(username, False)
                    
                    async with self.ws_lock:
                        for ws in self.active_websockets.values():
                            try:
                                await ws.send_json({
                                    "type": "user_offline",
                                    "username": username
                                })
                            except:
                                pass
    
    def run(self):
        """Запуск API сервера"""
        print(f"✅ FastAPI запущен на http://{self.host}:{self.port}")
        print(f"📖 API документация: http://{self.host}:{self.port}/docs")
        print(f"🔌 WebSocket endpoint: ws://{self.host}:{self.port}/ws")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")