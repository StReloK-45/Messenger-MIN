# server/admin.py
import json
import time
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

from logger import logger


class AdminManager:
    """Управление административными командами и функциями"""
    
    def __init__(self, server):
        self.server = server
        self.admin_commands = {
            'kick': self.kick_user,
            'ban': self.ban_user,
            'unban': self.unban_ip,
            'mute': self.mute_user,
            'unmute': self.unmute_user,
            'delmsg': self.delete_message,
            'delfile': self.delete_file,
            'users': self.show_online_users,
            'banned': self.show_banned_ips,
            'history': self.show_recent_history,
            'stats': self.show_server_stats,
            'clearusers': self.clear_users,
            'clearhistory': self.clear_history,
            'cleargroups': self.clear_groups,
            'groupkick': self.kick_from_group,
            'groupban': self.ban_from_group,
            'announce': self.send_announcement,
            'maintenance': self.maintenance_mode,
            'saveall': self.save_all_data,
            'stop': self.stop_server,
            'help': self.show_help
        }
    
    def get_help_text(self) -> str:
        """Возвращает текст помощи по командам"""
        return (
            "📋 ДОСТУПНЫЕ АДМИН КОМАНДЫ:\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "/kick <ник> [причина] - кикнуть пользователя\n"
            "/ban <ник> [причина] - забанить пользователя\n"
            "/unban <IP> - разбанить IP\n"
            "/mute <ник> <минуты> - замьютить пользователя\n"
            "/unmute <ник> - снять мут\n"
            "/delmsg <id> - удалить сообщение по ID\n"
            "/delfile <id> - удалить файл по ID\n"
            "/users - показать онлайн пользователей\n"
            "/banned - показать список банов\n"
            "/history [количество] - показать историю (по умолч. 50)\n"
            "/stats - подробная статистика сервера\n"
            "/clearusers - очистить БД пользователей\n"
            "/clearhistory - очистить историю чата\n"
            "/cleargroups - удалить все группы\n"
            "/groupkick <группа> <ник> - кикнуть из группы\n"
            "/groupban <группа> <ник> - забанить в группе\n"
            "/announce <текст> - глобальное объявление\n"
            "/maintenance - режим обслуживания\n"
            "/saveall - сохранить все данные\n"
            "/stop - остановить сервер\n"
            "/help - показать эту справку"
        )
    
    def show_help(self):
        """Показывает справку"""
        self.server.log(self.get_help_text(), "admin")
    
    def execute(self, command: str, args: List[str], executor_nickname: str = None) -> bool:
        """
        Выполняет административную команду
        Возвращает True если команда распознана и выполнена
        """
        if not command.startswith('/'):
            return False
        
        cmd = command[1:].lower()
        
        # Поиск в словаре команд
        if cmd in self.admin_commands:
            try:
                result = self.admin_commands[cmd](args)
                logger.admin(f"Command '{cmd}' executed by {executor_nickname or 'console'}")
                return result
            except Exception as e:
                self.server.log(f"❌ Ошибка выполнения команды: {e}", "error")
                return False
        
        return False
    
    # ========== ОСНОВНЫЕ КОМАНДЫ ==========
    
    def kick_user(self, args: List[str]) -> bool:
        """Кик пользователя"""
        if len(args) < 1:
            self.server.log("❌ Использование: /kick <ник> [причина]", "error")
            return False
        
        nickname = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "Кикнут администратором"
        
        for client, data in list(self.server.client_data.items()):
            if data['nickname'] == nickname:
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                    "type": "kicked",
                    "reason": reason
                }, ensure_ascii=False))
                time.sleep(0.1)
                self.server.network.remove_client(client)
                self.server.log(f"Пользователь {nickname} кикнут. Причина: {reason}", "admin")
                return True
        
        self.server.log(f"❌ Пользователь {nickname} не найден в онлайне", "error")
        return False
    
    def ban_user(self, args: List[str]) -> bool:
        """Бан пользователя"""
        if len(args) < 1:
            self.server.log("❌ Использование: /ban <ник> [причина]", "error")
            return False
        
        nickname = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "Забанен администратором"
        
        for client, data in list(self.server.client_data.items()):
            if data['nickname'] == nickname:
                ip = data['addr']
                self.server.storage.ban_ip(ip, reason)
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps({
                    "type": "banned",
                    "reason": reason
                }, ensure_ascii=False))
                time.sleep(0.1)
                self.server.network.remove_client(client)
                self.server.log(f"Пользователь {nickname} забанен (IP: {ip})", "admin")
                return True
        
        self.server.log(f"❌ Пользователь {nickname} не найден в онлайне", "error")
        return False
    
    def unban_ip(self, args: List[str]) -> bool:
        """Разбан IP"""
        if len(args) < 1:
            self.server.log("❌ Использование: /unban <IP>", "error")
            return False
        
        ip = args[0]
        
        if self.server.storage.unban_ip(ip):
            self.server.log(f"✅ IP {ip} разбанен", "admin")
            return True
        
        self.server.log(f"❌ IP {ip} не найден в списке банов", "error")
        return False
    
    def mute_user(self, args: List[str]) -> bool:
        """Мут пользователя"""
        if len(args) < 2:
            self.server.log("❌ Использование: /mute <ник> <минуты>", "error")
            return False
        
        nickname = args[0]
        try:
            minutes = int(args[1])
        except ValueError:
            self.server.log("❌ Количество минут должно быть числом!", "error")
            return False
        
        if minutes <= 0 or minutes > 1440:
            self.server.log("❌ Минуты должны быть от 1 до 1440 (сутки)", "error")
            return False
        
        until = datetime.now() + timedelta(minutes=minutes)
        self.server.chat.muted_users[nickname] = until
        
        self.server.network.broadcast_json({
            "type": "notification",
            "text": f"Пользователь {nickname} получил мут на {minutes} мин."
        })
        
        self.server.log(f"Пользователь {nickname} замьючен на {minutes} минут", "admin")
        
        if hasattr(self.server, 'update_online_display'):
            self.server.update_online_display()
        
        return True
    
    def unmute_user(self, args: List[str]) -> bool:
        """Снятие мута"""
        if len(args) < 1:
            self.server.log("❌ Использование: /unmute <ник>", "error")
            return False
        
        nickname = args[0]
        
        if nickname in self.server.chat.muted_users:
            del self.server.chat.muted_users[nickname]
            self.server.network.broadcast_json({
                "type": "notification",
                "text": f"Мут с {nickname} снят."
            })
            self.server.log(f"Мут с пользователя {nickname} снят", "admin")
            
            if hasattr(self.server, 'update_online_display'):
                self.server.update_online_display()
            return True
        
        self.server.log(f"❌ Пользователь {nickname} не в муте", "error")
        return False
    
    def delete_message(self, args: List[str]) -> bool:
        """Удаление сообщения"""
        if len(args) < 1:
            self.server.log("❌ Использование: /delmsg <id>", "error")
            return False
        
        msg_id = args[0]
        
        for i, msg in enumerate(self.server.storage.messages_history):
            if msg.get('id') == msg_id:
                deleted_msg = self.server.storage.messages_history.pop(i)
                self.server.storage.save_history()
                self.server.network.broadcast_json({
                    "type": "message_deleted",
                    "id": msg_id
                })
                self.server.log(f"Сообщение {msg_id} удалено (автор: {deleted_msg.get('sender')})", "admin")
                return True
        
        self.server.log(f"❌ Сообщение с ID {msg_id} не найдено", "error")
        return False
    
    def delete_file(self, args: List[str]) -> bool:
        """Удаление файла"""
        if len(args) < 1:
            self.server.log("❌ Использование: /delfile <id>", "error")
            return False
        
        file_id = args[0]
        file_info = self.server.storage.get_file_by_id(file_id)
        
        if file_info:
            # Удаляем физический файл
            file_path = file_info.get('path')
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    self.server.log(f"⚠️ Не удалось удалить файл: {e}", "warning")
            
            # Удаляем из БД
            self.server.storage.delete_file(file_id)
            
            self.server.network.broadcast_json({
                "type": "file_deleted",
                "id": file_id,
                "name": file_info.get('name')
            })
            
            self.server.log(f"Файл {file_id} удалён (название: {file_info.get('name')})", "admin")
            return True
        
        self.server.log(f"❌ Файл с ID {file_id} не найден", "error")
        return False
    
    # ========== ГРУППОВЫЕ КОМАНДЫ ==========
    
    def kick_from_group(self, args: List[str]) -> bool:
        """Кик пользователя из группы"""
        if len(args) < 2:
            self.server.log("❌ Использование: /groupkick <группа> <ник>", "error")
            return False
        
        group_name = args[0]
        nickname = args[1]
        
        group = self.server.storage.get_group_by_name(group_name)
        if not group:
            self.server.log(f"❌ Группа {group_name} не найдена", "error")
            return False
        
        member = self.server.storage.get_user_by_nickname(nickname)
        if not member:
            self.server.log(f"❌ Пользователь {nickname} не найден", "error")
            return False
        
        if self.server.storage.remove_group_member(group['id'], member['id']):
            self.server.network.broadcast_group_message(group_name, {
                "type": "group_member_removed",
                "group": group_name,
                "member": nickname,
                "reason": "Кикнут администратором"
            })
            self.server.log(f"Пользователь {nickname} кикнут из группы {group_name}", "admin")
            return True
        
        self.server.log(f"❌ Не удалось кикнуть {nickname} из группы {group_name}", "error")
        return False
    
    def ban_from_group(self, args: List[str]) -> bool:
        """Бан пользователя в группе"""
        if len(args) < 2:
            self.server.log("❌ Использование: /groupban <группа> <ник>", "error")
            return False
        
        group_name = args[0]
        nickname = args[1]
        
        # Создаём таблицу банов в группах, если её нет
        with self.server.storage.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS group_bans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    banned_by TEXT,
                    reason TEXT,
                    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (group_id) REFERENCES groups(id),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    UNIQUE(group_id, user_id)
                )
            ''')
            
            group = self.server.storage.get_group_by_name(group_name)
            if not group:
                self.server.log(f"❌ Группа {group_name} не найдена", "error")
                return False
            
            member = self.server.storage.get_user_by_nickname(nickname)
            if not member:
                self.server.log(f"❌ Пользователь {nickname} не найден", "error")
                return False
            
            # Добавляем бан
            cursor.execute('''
                INSERT OR REPLACE INTO group_bans (group_id, user_id, banned_by, reason)
                VALUES (?, ?, ?, ?)
            ''', (group['id'], member['id'], 'admin', f"Забанен в группе {group_name}"))
            
            # Удаляем из участников, если был
            self.server.storage.remove_group_member(group['id'], member['id'])
            
            self.server.network.broadcast_group_message(group_name, {
                "type": "group_notification",
                "text": f"Пользователь {nickname} забанен в группе {group_name}"
            })
            
            self.server.log(f"Пользователь {nickname} забанен в группе {group_name}", "admin")
            return True
    
    # ========== ИНФОРМАЦИОННЫЕ КОМАНДЫ ==========
    
    def show_online_users(self, args: List[str] = None) -> bool:
        """Показывает онлайн пользователей"""
        self.server.log("=" * 50, "system")
        self.server.log(f"ОНЛАЙН ПОЛЬЗОВАТЕЛИ ({len(self.server.clients)}):", "system")
        
        for client, data in self.server.client_data.items():
            nickname = data.get('nickname', 'Unknown')
            username = data.get('username', 'Unknown')
            addr = data.get('addr', 'Unknown')
            muted = "🔇" if nickname in self.server.chat.muted_users else ""
            admin = "👑" if data.get('is_admin', False) else ""
            self.server.log(f"   {muted}{admin} {nickname} (@{username}) - {addr}", "online")
        
        self.server.log("=" * 50, "system")
        return True
    
    def show_banned_ips(self, args: List[str] = None) -> bool:
        """Показывает список забаненных IP"""
        banned = self.server.storage.get_banned_ips()
        
        self.server.log("=" * 50, "system")
        self.server.log(f"ЗАБАНЕННЫЕ IP ({len(banned)}):", "system")
        
        for ip in banned:
            self.server.log(f"   ❌ {ip}", "error")
        
        self.server.log("=" * 50, "system")
        return True
    
    def show_recent_history(self, args: List[str] = None) -> bool:
        """Показывает последние сообщения"""
        count = int(args[0]) if args and args[0].isdigit() else 50
        
        messages = self.server.storage.get_chat_history(count)
        
        self.server.log("=" * 50, "system")
        self.server.log(f"ПОСЛЕДНИЕ {len(messages)} СООБЩЕНИЙ:", "system")
        self.server.log("=" * 50, "system")
        
        for msg in messages:
            sender = msg.get('sender', 'Unknown')
            text = msg.get('message', '')[:100]
            timestamp = msg.get('timestamp', '')
            if len(timestamp) > 16:
                timestamp = timestamp[11:16]
            self.server.log(f"[{timestamp}] {sender}: {text}", "system")
        
        self.server.log("=" * 50, "system")
        return True
    
    def show_server_stats(self, args: List[str] = None) -> bool:
        """Показывает подробную статистику сервера"""
        stats = self.server.storage.get_stats()
        
        self.server.log("=" * 50, "system")
        self.server.log("📊 СТАТИСТИКА СЕРВЕРА", "system")
        self.server.log("=" * 50, "system")
        self.server.log(f"👥 Всего пользователей:     {stats.get('users', 0)}", "system")
        self.server.log(f"💬 Сообщений в чате:       {stats.get('messages', 0)}", "system")
        self.server.log(f"🔒 Приватных сообщений:    {stats.get('private_messages', 0)}", "system")
        self.server.log(f"📦 Оффлайн сообщений:      {stats.get('offline_messages', 0)}", "system")
        self.server.log(f"👥 Групп:                  {stats.get('groups', 0)}", "system")
        self.server.log(f"📁 Файлов:                 {stats.get('files', 0)}", "system")
        self.server.log("-" * 50, "system")
        self.server.log(f"🟢 Онлайн (TCP):           {len(self.server.clients)}", "system")
        self.server.log(f"🌐 WebSocket (Web):        {len(self.server.api_server.active_websockets) if hasattr(self.server, 'api_server') else 0}", "system")
        
        if hasattr(self.server.auth, 'login_attempts'):
            blocked = sum(1 for d in self.server.auth.login_attempts.values() if d.get('blocked_until', 0) > time.time())
            self.server.log(f"🚫 Заблокировано IP:        {blocked}", "system")
        
        self.server.log("=" * 50, "system")
        return True
    
    # ========== СИСТЕМНЫЕ КОМАНДЫ ==========
    
    def clear_users(self, args: List[str] = None) -> bool:
        """Очистка базы пользователей (оставляет только админов)"""
        if args and args[0] == 'confirm':
            with self.server.storage.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE is_admin = 0")
                cursor.execute("DELETE FROM sessions")
                cursor.execute("DELETE FROM messages")
                cursor.execute("DELETE FROM private_messages")
                cursor.execute("DELETE FROM group_members")
                cursor.execute("DELETE FROM group_messages")
            
            self.server.log("✅ База пользователей и связанные данные очищены", "admin")
            return True
        
        self.server.log("⚠️ Для очистки базы введите /clearusers confirm", "warning")
        return False
    
    def clear_history(self, args: List[str] = None) -> bool:
        """Очистка истории чата"""
        with self.server.storage.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM private_messages")
            cursor.execute("DELETE FROM group_messages")
        
        self.server.storage.messages_history = []
        self.server.storage.private_messages = {}
        self.server.storage.message_counter = 0
        
        self.server.network.broadcast_json({
            "type": "notification",
            "text": "История чата очищена администратором"
        })
        
        self.server.log("✅ История чата очищена", "admin")
        return True
    
    def clear_groups(self, args: List[str] = None) -> bool:
        """Удаление всех групп"""
        with self.server.storage.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM group_messages")
            cursor.execute("DELETE FROM group_members")
            cursor.execute("DELETE FROM groups")
        
        self.server.network.broadcast_json({
            "type": "notification",
            "text": "Все группы удалены администратором"
        })
        
        self.server.log("✅ Все группы удалены", "admin")
        return True
    
    def send_announcement(self, args: List[str]) -> bool:
        """Отправка глобального объявления"""
        if len(args) < 1:
            self.server.log("❌ Использование: /announce <текст>", "error")
            return False
        
        text = " ".join(args)
        self.server.network.broadcast_json({
            "type": "announcement",
            "text": text,
            "from": "ADMIN"
        })
        
        self.server.log(f"📢 Объявление отправлено: {text}", "admin")
        return True
    
    def maintenance_mode(self, args: List[str] = None) -> bool:
        """Включение/выключение режима обслуживания"""
        if not hasattr(self.server, 'maintenance'):
            self.server.maintenance = False
        
        self.server.maintenance = not self.server.maintenance
        status = "включён" if self.server.maintenance else "выключен"
        
        self.server.network.broadcast_json({
            "type": "maintenance",
            "enabled": self.server.maintenance,
            "message": "Сервер на обслуживании" if self.server.maintenance else "Сервер снова доступен"
        })
        
        self.server.log(f"Режим обслуживания {status}", "admin")
        return True
    
    def save_all_data(self, args: List[str] = None) -> bool:
        """Принудительное сохранение всех данных"""
        self.server.storage.save_history()
        self.server.storage.save_private_messages()
        self.server.storage.save_bans()
        
        self.server.log("✅ Все данные сохранены", "admin")
        return True
    
    def stop_server(self, args: List[str] = None) -> bool:
        """Остановка сервера"""
        self.server.log("Остановка сервера...", "admin")
        self.server.running = False
        
        if hasattr(self.server, 'root') and self.server.root:
            self.server.root.after(1000, self.server.on_close)
        else:
            import sys
            sys.exit(0)
        
        return True