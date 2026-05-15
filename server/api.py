# server/api.py
import asyncio
import json
import os
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn
import shutil

from config import ChatConfig
from storage import Storage
from security import SecurityValidator, SimpleJWT, SimpleHash
from logger import logger

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

# ГРУППОВЫЕ МОДЕЛИ
class GroupCreate(BaseModel):
    name: str
    encrypted: bool = False

class GroupRename(BaseModel):
    group_id: int
    new_name: str

class GroupAddMember(BaseModel):
    group_id: int
    username: str

class GroupRemoveMember(BaseModel):
    group_id: int
    username: str

class GroupSetAdmin(BaseModel):
    group_id: int
    username: str
    is_admin: bool

class GroupBanMember(BaseModel):
    group_id: int
    username: str

class GroupMessageSend(BaseModel):
    group_id: int
    message: str
    encrypted: bool = False

class GroupResponse(BaseModel):
    id: int
    name: str
    created_at: str
    creator_id: int
    creator_name: str
    members_count: int
    encrypted: bool
    is_admin: bool
    is_creator: bool

class GroupMemberResponse(BaseModel):
    id: int
    username: str
    nickname: str
    is_admin: bool
    joined_at: str

class GroupMessageResponse(BaseModel):
    id: int
    sender: str
    message: str
    timestamp: str
    encrypted: bool

class GroupFileResponse(BaseModel):
    file_id: str
    name: str
    size: int
    sender_name: str
    date: str

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
        self.active_websockets: Dict[str, WebSocket] = {}
        self.ws_lock = asyncio.Lock()
        
        self._setup_routes()
        self._setup_cors()
        logger.success(f"FastAPI инициализирован на {host}:{port}")
    
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
            return {
                "message": "Messenger API v2.0",
                "status": "running",
                "websocket": f"ws://{self.host}:{self.port}/ws",
                "docs": f"http://{self.host}:{self.port}/docs"
            }
        
        # ========== Аутентификация ==========
        
        @self.app.post("/api/auth/register", response_model=LoginResponse)
        async def register(req: RegisterRequest):
            logger.info(f"Registration attempt: {req.username}")
            valid, err = SecurityValidator.validate_username(req.username)
            if not valid:
                raise HTTPException(status_code=400, detail=err)
            valid, err = SecurityValidator.validate_password(req.password)
            if not valid:
                raise HTTPException(status_code=400, detail=err)
            nickname = req.nickname or req.username
            existing = self.storage.get_user(req.username)
            if existing:
                raise HTTPException(status_code=400, detail="Username already exists")
            salt = SimpleHash.generate_salt()
            password_hash = SimpleHash.hash_password(req.password, salt)
            user_id = self.storage.create_user(req.username, password_hash, salt)
            if not user_id:
                raise HTTPException(status_code=500, detail="Registration failed")
            access_token = SimpleJWT.create_token(req.username)
            logger.success(f"User registered: {req.username}")
            return LoginResponse(
                access_token=access_token,
                username=req.username,
                nickname=nickname,
                is_admin=False
            )
        
        @self.app.post("/api/auth/login", response_model=LoginResponse)
        async def login(req: LoginRequest):
            logger.info(f"Login attempt: {req.username}")
            user = self.storage.get_user(req.username)
            if not user:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            if not SimpleHash.verify_password(req.password, user.get('salt', ''), user.get('password_hash', '')):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            self.storage.update_user_status(req.username, True)
            access_token = SimpleJWT.create_token(req.username)
            logger.success(f"User logged in: {req.username}")
            return LoginResponse(
                access_token=access_token,
                username=user['username'],
                nickname=user.get('nickname', user['username']),
                is_admin=bool(user.get('is_admin', False))
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
            return {"success": True}
        
        # ========== Пользователи ==========
        
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
        async def get_user(username: str, current_user: dict = Depends(self._get_current_user)):
            user = self.storage.get_user(username)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return {
                "username": user.get('username'),
                "nickname": user.get('nickname', user.get('username')),
                "is_online": bool(user.get('is_online', False)),
                "is_admin": bool(user.get('is_admin', False)),
                "last_seen": user.get('last_seen')
            }
        
        # ========== Сообщения ==========
        
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
                self.storage.save_private_message(sender, req.recipient, message)
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
                self.storage.save_message(sender, message)
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
        async def get_private_messages(username: str, limit: int = 100, current_user: dict = Depends(self._get_current_user)):
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
                group_id = self.storage.create_group(req.name, user['id'], req.encrypted)
                if not group_id:
                    raise HTTPException(status_code=500, detail="Failed to create group")
                logger.success(f"Group created: {req.name} by {current_user['username']}")
                return {"success": True, "group_id": group_id, "name": req.name}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Group creation error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/groups", response_model=List[GroupResponse])
        async def get_user_groups(current_user: dict = Depends(self._get_current_user)):
            try:
                user = self.storage.get_user(current_user['username'])
                groups = self.storage.get_user_groups(user['id'])
                result = []
                for g in groups:
                    members = self.storage.get_group_members(g['id'])
                    creator = self.storage.get_user_by_id(g['creator_id'])
                    result.append(GroupResponse(
                        id=g['id'],
                        name=g['name'],
                        created_at=g.get('created_at', ''),
                        creator_id=g['creator_id'],
                        creator_name=creator['username'] if creator else 'Unknown',
                        members_count=len(members),
                        encrypted=bool(g.get('encrypted', False)),
                        is_admin=bool(g.get('is_admin', False)),
                        is_creator=(g['creator_id'] == user['id'])
                    ))
                return result
            except Exception as e:
                logger.error(f"Get groups error: {e}")
                return []
        
        @self.app.get("/api/groups/{group_id}", response_model=GroupResponse)
        async def get_group(group_id: int, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            members = self.storage.get_group_members(group_id)
            creator = self.storage.get_user_by_id(group['creator_id'])
            return GroupResponse(
                id=group['id'],
                name=group['name'],
                created_at=group.get('created_at', ''),
                creator_id=group['creator_id'],
                creator_name=creator['username'] if creator else 'Unknown',
                members_count=len(members),
                encrypted=bool(group.get('encrypted', False)),
                is_admin=bool(member.get('is_admin', False)),
                is_creator=(group['creator_id'] == user['id'])
            )
        
        @self.app.put("/api/groups/{group_id}/rename")
        async def rename_group(group_id: int, req: GroupRename, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            if not member.get('is_admin') and group['creator_id'] != user['id']:
                raise HTTPException(status_code=403, detail="Only admins can rename the group")
            if self.storage.update_group_name(group_id, req.new_name):
                # Оповещаем всех участников через WebSocket
                members = self.storage.get_group_members(group_id)
                async with self.ws_lock:
                    for m in members:
                        if m['username'] in self.active_websockets:
                            try:
                                await self.active_websockets[m['username']].send_json({
                                    "type": "group_renamed",
                                    "group_id": group_id,
                                    "old_name": group['name'],
                                    "new_name": req.new_name
                                })
                            except:
                                pass
                return {"success": True}
            raise HTTPException(status_code=500, detail="Failed to rename group")
        
        @self.app.delete("/api/groups/{group_id}")
        async def delete_group(group_id: int, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            if group['creator_id'] != user['id']:
                raise HTTPException(status_code=403, detail="Only creator can delete the group")
            # Удаляем файлы группы
            files = self.storage.get_group_files(group_id)
            for f in files:
                try:
                    os.remove(f['path'])
                except:
                    pass
            if self.storage.delete_group(group_id):
                # Оповещаем участников
                members = self.storage.get_group_members(group_id)
                async with self.ws_lock:
                    for m in members:
                        if m['username'] in self.active_websockets:
                            try:
                                await self.active_websockets[m['username']].send_json({
                                    "type": "group_deleted",
                                    "group_id": group_id,
                                    "group_name": group['name']
                                })
                            except:
                                pass
                return {"success": True}
            raise HTTPException(status_code=500, detail="Failed to delete group")
        
        @self.app.post("/api/groups/{group_id}/members")
        async def add_group_member(group_id: int, req: GroupAddMember, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            if not member.get('is_admin') and group['creator_id'] != user['id']:
                raise HTTPException(status_code=403, detail="Only admins can add members")
            new_member = self.storage.get_user(req.username)
            if not new_member:
                raise HTTPException(status_code=404, detail="User not found")
            if self.storage.add_group_member(group_id, new_member['id']):
                async with self.ws_lock:
                    if new_member['username'] in self.active_websockets:
                        try:
                            await self.active_websockets[new_member['username']].send_json({
                                "type": "group_member_added",
                                "group_id": group_id,
                                "group_name": group['name'],
                                "member": new_member['username']
                            })
                        except:
                            pass
                    for m in self.storage.get_group_members(group_id):
                        if m['username'] in self.active_websockets:
                            try:
                                await self.active_websockets[m['username']].send_json({
                                    "type": "group_member_added",
                                    "group_id": group_id,
                                    "group_name": group['name'],
                                    "member": new_member['username']
                                })
                            except:
                                pass
                return {"success": True}
            raise HTTPException(status_code=500, detail="Failed to add member")
        
        @self.app.delete("/api/groups/{group_id}/members")
        async def remove_group_member(group_id: int, req: GroupRemoveMember, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            target = self.storage.get_user(req.username)
            if not target:
                raise HTTPException(status_code=404, detail="User not found")
            target_member = self.storage.get_group_member(group_id, target['id'])
            if not target_member:
                raise HTTPException(status_code=404, detail="User is not a member of this group")
            # Нельзя удалить создателя
            if target['id'] == group['creator_id']:
                raise HTTPException(status_code=403, detail="Cannot remove group creator")
            # Проверка прав
            can_remove = False
            if user['id'] == target['id']:
                can_remove = True  # Самовыход
            elif member.get('is_admin') or group['creator_id'] == user['id']:
                can_remove = True
            if not can_remove:
                raise HTTPException(status_code=403, detail="No permission to remove this member")
            if self.storage.remove_group_member(group_id, target['id']):
                async with self.ws_lock:
                    for m in self.storage.get_group_members(group_id):
                        if m['username'] in self.active_websockets:
                            try:
                                await self.active_websockets[m['username']].send_json({
                                    "type": "group_member_removed",
                                    "group_id": group_id,
                                    "group_name": group['name'],
                                    "member": target['username']
                                })
                            except:
                                pass
                return {"success": True}
            raise HTTPException(status_code=500, detail="Failed to remove member")
        
        @self.app.put("/api/groups/{group_id}/admins")
        async def set_group_admin(group_id: int, req: GroupSetAdmin, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            # Только создатель может назначать админов
            if group['creator_id'] != user['id']:
                raise HTTPException(status_code=403, detail="Only group creator can set admins")
            target = self.storage.get_user(req.username)
            if not target:
                raise HTTPException(status_code=404, detail="User not found")
            target_member = self.storage.get_group_member(group_id, target['id'])
            if not target_member:
                raise HTTPException(status_code=404, detail="User is not a member of this group")
            if self.storage.set_group_member_admin(group_id, target['id'], req.is_admin):
                async with self.ws_lock:
                    for m in self.storage.get_group_members(group_id):
                        if m['username'] in self.active_websockets:
                            try:
                                await self.active_websockets[m['username']].send_json({
                                    "type": "group_admin_changed",
                                    "group_id": group_id,
                                    "group_name": group['name'],
                                    "member": target['username'],
                                    "is_admin": req.is_admin
                                })
                            except:
                                pass
                return {"success": True}
            raise HTTPException(status_code=500, detail="Failed to set admin")
        
        @self.app.post("/api/groups/{group_id}/ban")
        async def ban_group_member(group_id: int, req: GroupBanMember, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            if not member.get('is_admin') and group['creator_id'] != user['id']:
                raise HTTPException(status_code=403, detail="Only admins can ban members")
            target = self.storage.get_user(req.username)
            if not target:
                raise HTTPException(status_code=404, detail="User not found")
            if target['id'] == group['creator_id']:
                raise HTTPException(status_code=403, detail="Cannot ban group creator")
            if self.storage.ban_group_member(group_id, target['id'], user['id']):
                async with self.ws_lock:
                    if target['username'] in self.active_websockets:
                        try:
                            await self.active_websockets[target['username']].send_json({
                                "type": "group_banned",
                                "group_id": group_id,
                                "group_name": group['name']
                            })
                        except:
                            pass
                    for m in self.storage.get_group_members(group_id):
                        if m['username'] in self.active_websockets:
                            try:
                                await self.active_websockets[m['username']].send_json({
                                    "type": "group_member_banned",
                                    "group_id": group_id,
                                    "group_name": group['name'],
                                    "member": target['username']
                                })
                            except:
                                pass
                return {"success": True}
            raise HTTPException(status_code=500, detail="Failed to ban member")
        
        @self.app.post("/api/groups/{group_id}/messages")
        async def send_group_message(group_id: int, req: GroupMessageSend, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            message = SecurityValidator.sanitize_text(req.message)
            if not message:
                raise HTTPException(status_code=400, detail="Empty message")
            msg_id = self.storage.save_group_message(group_id, user['id'], current_user['username'], message, req.encrypted)
            # Рассылаем участникам
            members = self.storage.get_group_members(group_id)
            async with self.ws_lock:
                for m in members:
                    if m['username'] in self.active_websockets:
                        try:
                            await self.active_websockets[m['username']].send_json({
                                "type": "group_message",
                                "group_id": group_id,
                                "group_name": group['name'],
                                "sender": current_user['username'],
                                "message": message,
                                "timestamp": datetime.now().isoformat(),
                                "encrypted": req.encrypted,
                                "message_id": msg_id
                            })
                        except:
                            pass
            return {"success": True, "message_id": msg_id}
        
        @self.app.get("/api/groups/{group_id}/messages", response_model=List[GroupMessageResponse])
        async def get_group_messages(group_id: int, limit: int = 100, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            messages = self.storage.get_group_messages(group_id, limit)
            return [
                GroupMessageResponse(
                    id=m['id'],
                    sender=m['sender'],
                    message=m['message'],
                    timestamp=m['timestamp'],
                    encrypted=bool(m.get('encrypted', False))
                )
                for m in messages
            ]
        
        @self.app.delete("/api/groups/{group_id}/messages/{message_id}")
        async def delete_group_message(group_id: int, message_id: int, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            if not member.get('is_admin') and group['creator_id'] != user['id']:
                raise HTTPException(status_code=403, detail="Only admins can delete messages")
            if self.storage.delete_group_message(message_id, user['id']):
                async with self.ws_lock:
                    for m in self.storage.get_group_members(group_id):
                        if m['username'] in self.active_websockets:
                            try:
                                await self.active_websockets[m['username']].send_json({
                                    "type": "group_message_deleted",
                                    "group_id": group_id,
                                    "message_id": message_id
                                })
                            except:
                                pass
                return {"success": True}
            raise HTTPException(status_code=500, detail="Failed to delete message")
        
        @self.app.delete("/api/groups/{group_id}/history")
        async def clear_group_history(group_id: int, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            if not member.get('is_admin') and group['creator_id'] != user['id']:
                raise HTTPException(status_code=403, detail="Only admins can clear history")
            if self.storage.clear_group_history(group_id):
                async with self.ws_lock:
                    for m in self.storage.get_group_members(group_id):
                        if m['username'] in self.active_websockets:
                            try:
                                await self.active_websockets[m['username']].send_json({
                                    "type": "group_history_cleared",
                                    "group_id": group_id
                                })
                            except:
                                pass
                return {"success": True}
            raise HTTPException(status_code=500, detail="Failed to clear history")
        
        @self.app.get("/api/groups/{group_id}/members", response_model=List[GroupMemberResponse])
        async def get_group_members_list(group_id: int, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            members = self.storage.get_group_members(group_id)
            return [
                GroupMemberResponse(
                    id=m['id'],
                    username=m['username'],
                    nickname=m.get('nickname', m['username']),
                    is_admin=bool(m.get('is_admin', False)),
                    joined_at=m.get('joined_at', '')
                )
                for m in members
            ]
        
        @self.app.get("/api/groups/{group_id}/files", response_model=List[GroupFileResponse])
        async def get_group_files(group_id: int, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            files = self.storage.get_group_files(group_id)
            return [
                GroupFileResponse(
                    file_id=f['file_id'],
                    name=f['name'],
                    size=f['size'],
                    sender_name=f['sender_name'],
                    date=f['date']
                )
                for f in files
            ]
        
        @self.app.post("/api/groups/{group_id}/files")
        async def upload_group_file(
            group_id: int,
            file: UploadFile = File(...),
            current_user: dict = Depends(self._get_current_user)
        ):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            # Сохраняем файл
            file_id = hashlib.md5(f"{file.filename}{datetime.now()}{user['id']}".encode()).hexdigest()[:8]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = f"{file_id}_{timestamp}_{file.filename}"
            file_path = os.path.join(self.config.RECEIVED_FILES_DIR, safe_filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            file_size = os.path.getsize(file_path)
            date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            self.storage.save_group_file(
                file_id, group_id, file.filename, file_path, 
                file_size, user['id'], current_user['username'], date_str
            )
            
            # Оповещаем участников
            members = self.storage.get_group_members(group_id)
            async with self.ws_lock:
                for m in members:
                    if m['username'] in self.active_websockets:
                        try:
                            await self.active_websockets[m['username']].send_json({
                                "type": "group_file",
                                "group_id": group_id,
                                "group_name": group['name'],
                                "file": {
                                    "file_id": file_id,
                                    "name": file.filename,
                                    "size": file_size,
                                    "sender": current_user['username'],
                                    "date": date_str
                                }
                            })
                        except:
                            pass
            
            return {"success": True, "file_id": file_id}
        
        @self.app.delete("/api/groups/{group_id}/files/{file_id}")
        async def delete_group_file(group_id: int, file_id: str, current_user: dict = Depends(self._get_current_user)):
            group = self.storage.get_group(group_id)
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            user = self.storage.get_user(current_user['username'])
            member = self.storage.get_group_member(group_id, user['id'])
            if not member:
                raise HTTPException(status_code=403, detail="You are not a member of this group")
            if not member.get('is_admin') and group['creator_id'] != user['id']:
                raise HTTPException(status_code=403, detail="Only admins can delete files")
            if self.storage.delete_group_file(file_id, user['id']):
                async with self.ws_lock:
                    for m in self.storage.get_group_members(group_id):
                        if m['username'] in self.active_websockets:
                            try:
                                await self.active_websockets[m['username']].send_json({
                                    "type": "group_file_deleted",
                                    "group_id": group_id,
                                    "file_id": file_id
                                })
                            except:
                                pass
                return {"success": True}
            raise HTTPException(status_code=500, detail="Failed to delete file")
        
        # ========== Статус ==========
        
        @self.app.get("/api/status", response_model=StatusResponse)
        async def get_status():
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
                async with self.ws_lock:
                    self.active_websockets[username] = websocket
                await websocket.send_json({
                    "type": "connected",
                    "message": f"Welcome {username}!",
                    "users_online": len(self.active_websockets)
                })
                self.storage.update_user_status(username, True)
                # Оповещаем всех о новом пользователе
                async with self.ws_lock:
                    for ws_username, ws in self.active_websockets.items():
                        if ws_username != username:
                            try:
                                await ws.send_json({"type": "user_online", "username": username})
                            except:
                                pass
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
                    elif msg_type == "ping":
                        try:
                            await websocket.send_json({"type": "pong"})
                        except:
                            pass
                    elif msg_type == "get_users":
                        users = self.storage.get_all_users()
                        online_list = [u.get('username', '') for u in users if u.get('is_online')]
                        try:
                            await websocket.send_json({"type": "users_list", "users": online_list})
                        except:
                            pass
            except WebSocketDisconnect:
                pass
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
                                await ws.send_json({"type": "user_offline", "username": username})
                            except:
                                pass
    
    def run(self):
        print(f"✅ FastAPI запущен на http://{self.host}:{self.port}")
        print(f"📖 API документация: http://{self.host}:{self.port}/docs")
        print(f"🔌 WebSocket endpoint: ws://{self.host}:{self.port}/ws")
        print(f"📁 Логи пишутся в папку logs/")
        uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")