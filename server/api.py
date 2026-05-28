# server/api.py
import asyncio
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

from config import ChatConfig
from storage import Storage
from security import SecurityValidator, SimpleJWT, SimpleHash
from logger import logger


# ========== Pydantic модели ==========

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=4, max_length=100)
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
    has_offline_messages: bool = False

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
    message: str = Field(..., max_length=5000)
    recipient: Optional[str] = None

class PrivateMessageResponse(BaseModel):
    id: int
    sender: str
    recipient: str
    message: str
    timestamp: str

class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)

class GroupRename(BaseModel):
    old_name: str
    new_name: str = Field(..., min_length=1, max_length=30)

class GroupAddMember(BaseModel):
    group_name: str
    member_nickname: str

class GroupRemoveMember(BaseModel):
    group_name: str
    member_nickname: str

class GroupMessageSend(BaseModel):
    group_name: str
    message: str = Field(..., max_length=5000)

class GroupResponse(BaseModel):
    id: int
    name: str
    created_at: str
    members_count: int
    is_owner: bool = False

class StatusResponse(BaseModel):
    status: str
    version: str
    users_count: int
    online_count: int
    websocket_connections: int
    offline_messages_count: int

class OfflineMessageResponse(BaseModel):
    id: int
    sender: str
    message: str
    timestamp: str


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
        
        logger.success(f"FastAPI initialized on {host}:{port}")
    
    def _setup_cors(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
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
        
        @self.app.get("/")
        async def root():
            logger.info("Root endpoint accessed")
            return {
                "message": "Messenger API v2.0",
                "status": "running",
                "websocket": f"ws://{self.host}:{self.port}/ws",
                "docs": f"http://{self.host}:{self.port}/docs",
                "endpoints": {
                    "auth": "/api/auth/...",
                    "users": "/api/users",
                    "messages": "/api/messages",
                    "groups": "/api/groups",
                    "files": "/api/files"
                }
            }
        
        # ========== АУТЕНТИФИКАЦИЯ ==========
        
        @self.app.post("/api/auth/register", response_model=LoginResponse)
        async def register(req: RegisterRequest):
            logger.info(f"Registration attempt: {req.username}")
            
            valid, err = SecurityValidator.validate_username(req.username)
            if not valid:
                logger.warning(f"Registration failed: {err}")
                raise HTTPException(status_code=400, detail=err)
            
            valid, err = SecurityValidator.validate_password(req.password)
            if not valid:
                logger.warning(f"Registration failed: {err}")
                raise HTTPException(status_code=400, detail=err)
            
            nickname = req.nickname or req.username
            valid, err = SecurityValidator.validate_nickname(nickname)
            if not valid:
                logger.warning(f"Registration failed: {err}")
                raise HTTPException(status_code=400, detail=err)
            
            existing = self.storage.get_user(req.username)
            if existing:
                logger.warning(f"Registration failed: user {req.username} already exists")
                raise HTTPException(status_code=400, detail="Username already exists")
            
            salt = SimpleHash.generate_salt()
            password_hash = SimpleHash.hash_password(req.password, salt)
            
            user_id = self.storage.create_user(req.username, password_hash, salt)
            if not user_id:
                logger.error(f"Registration failed: database error")
                raise HTTPException(status_code=500, detail="Registration failed")
            
            self.storage.update_user_nickname(req.username, nickname)
            
            access_token = SimpleJWT.create_token(req.username)
            logger.success(f"User registered: {req.username}")
            logger.save_event("registration", {"username": req.username})
            
            return LoginResponse(
                access_token=access_token,
                username=req.username,
                nickname=nickname,
                is_admin=False,
                has_offline_messages=False
            )
        
        @self.app.post("/api/auth/login", response_model=LoginResponse)
        async def login(req: LoginRequest):
            logger.info(f"Login attempt: {req.username}")
            
            user = self.storage.get_user(req.username)
            if not user:
                logger.warning(f"Login failed: user {req.username} not found")
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            if not SimpleHash.verify_password(req.password, user.get('salt', ''), user.get('password_hash', '')):
                logger.warning(f"Login failed: wrong password for {req.username}")
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            self.storage.update_user_status(req.username, True)
            access_token = SimpleJWT.create_token(req.username)
            
            # Проверяем наличие оффлайн-сообщений
            offline_msgs = self.storage.get_offline_messages(req.username)
            has_offline = len(offline_msgs) > 0
            
            logger.success(f"User logged in: {req.username}")
            logger.save_event("login", {"username": req.username})
            
            return LoginResponse(
                access_token=access_token,
                username=user['username'],
                nickname=user.get('nickname', user['username']),
                is_admin=bool(user.get('is_admin', False)),
                has_offline_messages=has_offline
            )
        
        @self.app.post("/api/auth/logout")
        async def logout(current_user: dict = Depends(self._get_current_user)):
            username = current_user['username']
            self.storage.update_user_status(username, False)
            
            async with self.ws_lock:
                if username in self.active_websockets:
                    try:
                        await self.active_websockets[username].close()
                    except:
                        pass
                    del self.active_websockets[username]
            
            logger.info(f"User logged out: {username}")
            return {"success": True}
        
        # ========== ПОЛЬЗОВАТЕЛИ ==========
        
        @self.app.get("/api/users", response_model=List[UserResponse])
        async def get_users(current_user: dict = Depends(self._get_current_user)):
            users = self.storage.get_all_users()
            return [
                UserResponse(
                    username=u.get('username', ''),
                    nickname=u.get('nickname', u.get('username', '')),
                    is_online=bool(u.get('is_online', False)),
                    is_admin=bool(u.get('is_admin', False)),
                    last_seen=u.get('last_seen')
                )
                for u in users
            ]
        
        @self.app.get("/api/users/online")
        async def get_online_users():
            users = self.storage.get_all_users()
            online = [u.get('username', '') for u in users if u.get('is_online')]
            return {"online": online, "count": len(online)}
        
        @self.app.get("/api/users/{username}")
        async def get_user_profile(username: str, current_user: dict = Depends(self._get_current_user)):
            user = self.storage.get_user(username)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {
                "username": user['username'],
                "nickname": user.get('nickname', user['username']),
                "is_online": bool(user.get('is_online', False)),
                "is_admin": bool(user.get('is_admin', False)),
                "last_seen": user.get('last_seen')
            }
        
        # ========== СООБЩЕНИЯ ==========
        
        @self.app.get("/api/messages", response_model=List[MessageResponse])
        async def get_messages(limit: int = 100, current_user: dict = Depends(self._get_current_user)):
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
            sender = current_user['username']
            message = SecurityValidator.sanitize_text(req.message)
            
            if not message:
                raise HTTPException(status_code=400, detail="Empty message")
            
            if req.recipient:
                # Приватное сообщение
                self.storage.save_private_message(sender, req.recipient, message)
                logger.chat(sender, f"[PM to {req.recipient}] {message}")
                
                async with self.ws_lock:
                    if req.recipient in self.active_websockets:
                        try:
                            await self.active_websockets[req.recipient].send_json({
                                "type": "private_message",
                                "from": sender,
                                "message": message,
                                "timestamp": datetime.now().isoformat()
                            })
                        except Exception as e:
                            logger.error(f"WebSocket send error: {e}")
                    else:
                        # Сохраняем оффлайн-сообщение
                        self.storage.save_offline_message(req.recipient, sender, message, is_private=True)
                        logger.info(f"Offline message saved from {sender} to {req.recipient}")
                
                return {"success": True, "type": "private", "recipient": req.recipient}
            else:
                # Общее сообщение
                self.storage.save_message(sender, message)
                logger.chat(sender, message)
                
                async with self.ws_lock:
                    for ws in self.active_websockets.values():
                        try:
                            await ws.send_json({
                                "type": "message",
                                "sender": sender,
                                "message": message,
                                "timestamp": datetime.now().isoformat()
                            })
                        except Exception as e:
                            logger.error(f"WebSocket broadcast error: {e}")
                
                return {"success": True, "type": "general"}
        
        # ========== ПРИВАТНЫЕ СООБЩЕНИЯ ==========
        
        @self.app.get("/api/private/messages/{username}", response_model=List[PrivateMessageResponse])
        async def get_private_messages(
            username: str, 
            limit: int = 100, 
            current_user: dict = Depends(self._get_current_user)
        ):
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
        
        @self.app.get("/api/private/offline", response_model=List[OfflineMessageResponse])
        async def get_offline_messages(current_user: dict = Depends(self._get_current_user)):
            """Получение оффлайн-сообщений"""
            username = current_user['username']
            messages = self.storage.get_offline_messages(username)
            
            # Отмечаем как доставленные
            msg_ids = [m['id'] for m in messages]
            if msg_ids:
                self.storage.mark_offline_messages_delivered(msg_ids)
            
            return [
                OfflineMessageResponse(
                    id=m['id'],
                    sender=m['sender'],
                    message=m['message'],
                    timestamp=m['timestamp']
                )
                for m in messages
            ]
        
        # ========== ГРУППЫ ==========
        
        @self.app.post("/api/groups")
        async def create_group(req: GroupCreate, current_user: dict = Depends(self._get_current_user)):
            try:
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
                
                logger.success(f"Group created: {req.name} by {current_user['username']}")
                return {"success": True, "group_id": group_id, "name": req.name}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Group creation error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/api/groups/rename")
        async def rename_group(req: GroupRename, current_user: dict = Depends(self._get_current_user)):
            """Переименование группы"""
            try:
                group = self.storage.get_group_by_name(req.old_name)
                if not group:
                    raise HTTPException(status_code=404, detail="Group not found")
                
                user = self.storage.get_user(current_user['username'])
                if group['creator_id'] != user['id']:
                    raise HTTPException(status_code=403, detail="Only group creator can rename")
                
                valid, err = SecurityValidator.validate_group_name(req.new_name)
                if not valid:
                    raise HTTPException(status_code=400, detail=err)
                
                if self.storage.rename_group(group['id'], req.new_name):
                    return {"success": True, "old_name": req.old_name, "new_name": req.new_name}
                else:
                    raise HTTPException(status_code=500, detail="Failed to rename group")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Group rename error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/groups", response_model=List[GroupResponse])
        async def get_user_groups(current_user: dict = Depends(self._get_current_user)):
            try:
                user = self.storage.get_user(current_user['username'])
                groups = self.storage.get_user_groups(user['id'])
                return [
                    GroupResponse(
                        id=g.get('id', 0),
                        name=g.get('name', ''),
                        created_at=g.get('created_at', ''),
                        members_count=0,
                        is_owner=(g.get('creator_id') == user['id'])
                    )
                    for g in groups
                ]
            except Exception as e:
                logger.error(f"Get groups error: {e}")
                return []
        
        @self.app.get("/api/groups/{group_name}/members")
        async def get_group_members(group_name: str, current_user: dict = Depends(self._get_current_user)):
            """Получение участников группы"""
            group = self.storage.get_group_by_name(group_name)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            
            members = self.storage.get_group_members(group['id'])
            return {"members": [m.get('nickname', m.get('username')) for m in members]}
        
        @self.app.post("/api/groups/add")
        async def add_group_member(req: GroupAddMember, current_user: dict = Depends(self._get_current_user)):
            try:
                group = self.storage.get_group_by_name(req.group_name)
                if not group:
                    raise HTTPException(status_code=404, detail="Group not found")
                
                member = self.storage.get_user_by_nickname(req.member_nickname)
                if not member:
                    raise HTTPException(status_code=404, detail=f"User {req.member_nickname} not found")
                
                # Проверяем, не является ли пользователь уже участником
                members = self.storage.get_group_members(group['id'])
                member_ids = [m['id'] for m in members]
                if member['id'] in member_ids:
                    raise HTTPException(status_code=400, detail="User already in group")
                
                self.storage.add_group_member(group['id'], member['id'])
                logger.info(f"User {req.member_nickname} added to group {req.group_name}")
                return {"success": True, "member": req.member_nickname, "group": req.group_name}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Add member error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/groups/remove")
        async def remove_group_member(req: GroupRemoveMember, current_user: dict = Depends(self._get_current_user)):
            """Удаление участника из группы"""
            try:
                group = self.storage.get_group_by_name(req.group_name)
                if not group:
                    raise HTTPException(status_code=404, detail="Group not found")
                
                user = self.storage.get_user(current_user['username'])
                if group['creator_id'] != user['id'] and current_user['username'] != req.member_nickname:
                    raise HTTPException(status_code=403, detail="Only group creator can remove members")
                
                member = self.storage.get_user_by_nickname(req.member_nickname)
                if not member:
                    raise HTTPException(status_code=404, detail=f"User {req.member_nickname} not found")
                
                # Проверяем, является ли пользователь участником
                members = self.storage.get_group_members(group['id'])
                member_ids = [m['id'] for m in members]
                if member['id'] not in member_ids:
                    raise HTTPException(status_code=400, detail="User not in group")
                
                self.storage.remove_group_member(group['id'], member['id'])
                logger.info(f"User {req.member_nickname} removed from group {req.group_name}")
                return {"success": True, "member": req.member_nickname, "group": req.group_name}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Remove member error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/api/groups/{group_name}")
        async def delete_group(group_name: str, current_user: dict = Depends(self._get_current_user)):
            """Удаление группы"""
            try:
                group = self.storage.get_group_by_name(group_name)
                if not group:
                    raise HTTPException(status_code=404, detail="Group not found")
                
                user = self.storage.get_user(current_user['username'])
                if group['creator_id'] != user['id']:
                    raise HTTPException(status_code=403, detail="Only group creator can delete")
                
                self.storage.delete_group(group['id'])
                logger.info(f"Group {group_name} deleted by {current_user['username']}")
                return {"success": True}
            except Exception as e:
                logger.error(f"Delete group error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/groups/message")
        async def send_group_message(req: GroupMessageSend, current_user: dict = Depends(self._get_current_user)):
            try:
                group = self.storage.get_group_by_name(req.group_name)
                if not group:
                    raise HTTPException(status_code=404, detail="Group not found")
                
                user = self.storage.get_user(current_user['username'])
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                
                message = SecurityValidator.sanitize_text(req.message)
                
                if not message:
                    raise HTTPException(status_code=400, detail="Empty message")
                
                self.storage.save_group_message(group['id'], user['id'], current_user['username'], message)
                logger.chat(current_user['username'], f"[GROUP {req.group_name}] {message}")
                
                members = self.storage.get_group_members(group['id'])
                member_names = [m.get('nickname', m.get('username', '')) for m in members]
                
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
                            except Exception as e:
                                logger.error(f"Group message send error: {e}")
                
                return {"success": True}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Group message error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ========== СТАТУС ==========
        
        @self.app.get("/api/status", response_model=StatusResponse)
        async def get_status():
            users = self.storage.get_all_users()
            offline_msgs = self.storage.get_stats().get('offline_messages', 0)
            return StatusResponse(
                status="online",
                version="2.0.0",
                users_count=len(users),
                online_count=sum(1 for u in users if u.get('is_online')),
                websocket_connections=len(self.active_websockets),
                offline_messages_count=offline_msgs
            )
        
        # ========== WEBSOCKET ==========
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            username = None
            
            try:
                # Устанавливаем таймаут для получения токена
                try:
                    auth_data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
                except asyncio.TimeoutError:
                    await websocket.close(code=1008, reason="Authentication timeout")
                    return
                
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
                
                async with self.ws_lock:
                    self.active_websockets[username] = websocket
                
                logger.connection(websocket.client.host, f"WebSocket connected: {username}")
                
                # Отправляем оффлайн-сообщения
                offline_msgs = self.storage.get_offline_messages(username)
                if offline_msgs:
                    for msg in offline_msgs:
                        await websocket.send_json({
                            "type": "offline_message",
                            "from": msg['sender'],
                            "message": msg['message'],
                            "timestamp": msg['timestamp']
                        })
                    
                    msg_ids = [m['id'] for m in offline_msgs]
                    self.storage.mark_offline_messages_delivered(msg_ids)
                    logger.info(f"Delivered {len(offline_msgs)} offline messages to {username}")
                
                # Отправляем подтверждение
                await websocket.send_json({
                    "type": "connected",
                    "message": f"Welcome {username}!",
                    "users_online": len(self.active_websockets)
                })
                
                self.storage.update_user_status(username, True)
                
                # Уведомляем всех о входе пользователя
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
                    try:
                        data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
                    except asyncio.TimeoutError:
                        # Отправляем ping для поддержания соединения
                        try:
                            await websocket.send_json({"type": "ping"})
                        except:
                            break
                        continue
                    
                    msg_type = data.get("type")
                    
                    if msg_type == "message":
                        text = SecurityValidator.sanitize_text(data.get("text", ""))
                        if text:
                            self.storage.save_message(username, text)
                            logger.chat(username, text)
                            
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
                            logger.chat(username, f"[PM to {recipient}] {text}")
                            
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
                    
                    elif msg_type == "group":
                        group_name = data.get("group")
                        text = SecurityValidator.sanitize_text(data.get("text", ""))
                        
                        if group_name and text:
                            group = self.storage.get_group_by_name(group_name)
                            if group:
                                user_obj = self.storage.get_user(username)
                                if user_obj:
                                    self.storage.save_group_message(group['id'], user_obj['id'], username, text)
                                    members = self.storage.get_group_members(group['id'])
                                    member_names = [m.get('nickname', m.get('username', '')) for m in members]
                                    
                                    async with self.ws_lock:
                                        for name in member_names:
                                            if name in self.active_websockets:
                                                try:
                                                    await self.active_websockets[name].send_json({
                                                        "type": "group_message",
                                                        "group": group_name,
                                                        "sender": username,
                                                        "message": text,
                                                        "timestamp": datetime.now().isoformat()
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
                    
                    elif msg_type == "typing":
                        recipient = data.get("recipient")
                        if recipient and recipient in self.active_websockets:
                            try:
                                await self.active_websockets[recipient].send_json({
                                    "type": "typing",
                                    "from": username
                                })
                            except:
                                pass
            
            except WebSocketDisconnect:
                logger.connection("unknown", f"WebSocket disconnected: {username}")
            except asyncio.TimeoutError:
                logger.warning(f"WebSocket timeout for {username}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
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
                    
                    logger.connection("unknown", f"WebSocket disconnected: {username}")
    
    def run(self):
        print(f"FastAPI running on http://{self.host}:{self.port}")
        print(f"API documentation: http://{self.host}:{self.port}/docs")
        print(f"WebSocket endpoint: ws://{self.host}:{self.port}/ws")
        print(f"Logs are written to logs/ directory")
        
        # ВАЖНО: Убедитесь что websockets установлена
        # Запускаем с правильными настройками для WebSocket
        uvicorn.run(
            self.app, 
            host=self.host, 
            port=self.port, 
            log_level="warning",
            ws="websockets",  # Явно указываем использование websockets
            ws_ping_interval=20,
            ws_ping_timeout=10
        )