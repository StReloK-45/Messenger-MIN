# server/admin.py
import json
import time
from datetime import datetime, timedelta

class AdminManager:
    def __init__(self, server):
        self.server = server
    
    def get_help_text(self):
        return (
            "/kick <ник> - кикнуть\n"
            "/ban <ник> - забанить\n"
            "/unban <IP> - разбанить\n"
            "/mute <ник> <мин> - мут\n"
            "/unmute <ник> - снять мут\n"
            "/delmsg <id> - удалить сообщ.\n"
            "/delfile <id> - удалить файл\n"
            "/users - онлайн\n"
            "/banned - список банов\n"
            "/history - последние 50\n"
            "/clearusers - очистить БД\n"
            "/clearhistory - очистить\n"
            "/stop - остановить\n"
            "/help - помощь"
        )
    
    def execute(self, command, args):
        cmd = command.replace('/', '').lower()
        
        if cmd == "kick" and len(args) >= 1:
            nickname = args[0]
            reason = " ".join(args[1:]) if len(args) > 1 else "Кикнут администратором"
            self.kick_user(nickname, reason)
        
        elif cmd == "ban" and len(args) >= 1:
            nickname = args[0]
            reason = " ".join(args[1:]) if len(args) > 1 else "Забанен администратором"
            self.ban_user(nickname, reason)
        
        elif cmd == "unban" and len(args) >= 1:
            self.unban_ip(args[0])
        
        elif cmd == "mute" and len(args) >= 2:
            try:
                self.mute_user(args[0], int(args[1]))
            except:
                self.server.log("❌ Укажите количество минут числом!", "error")
        
        elif cmd == "unmute" and len(args) >= 1:
            self.unmute_user(args[0])
        
        elif cmd == "delmsg" and len(args) >= 1:
            self.delete_message(args[0])
        
        elif cmd == "delfile" and len(args) >= 1:
            self.delete_file(args[0])
        
        elif cmd == "users":
            self.show_online_users()
        
        elif cmd == "banned":
            self.show_banned_ips()
        
        elif cmd == "history":
            count = int(args[0]) if args else 50
            self.show_recent_history(count)
        
        elif cmd == "clearusers":
            self.server.storage.users_db = {}
            self.server.storage.save_users()
            self.server.log("✅ База пользователей очищена", "system")
        
        elif cmd == "clearhistory":
            self.server.storage.messages_history = []
            self.server.storage.files_list = []
            self.server.storage.private_messages = {}
            self.server.storage.message_counter = 0
            self.server.storage.save_history()
            self.server.storage.save_private_messages()
            self.server.log("✅ История чата очищена", "system")
        
        elif cmd == "stop":
            self.server.log("🛑 Остановка сервера...", "error")
            self.server.running = False
            self.server.root.after(1000, self.server.on_close)
        
        else:
            self.server.log(f"❌ Неизвестная команда: {command}", "error")
    
    def kick_user(self, nickname, reason="Кикнут администратором"):
        for client, data in list(self.server.client_data.items()):
            if data['nickname'] == nickname:
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(
                    {"type": "kicked", "reason": reason}, ensure_ascii=False))
                time.sleep(0.1)
                self.server.network.remove_client(client)
                self.server.log(f"🛡️ Пользователь {nickname} кикнут. Причина: {reason}", "admin")
                return True
        self.server.log(f"❌ Пользователь {nickname} не найден в онлайне", "error")
        return False
    
    def ban_user(self, nickname, reason="Забанен администратором"):
        for client, data in list(self.server.client_data.items()):
            if data['nickname'] == nickname:
                ip = data['addr']
                self.server.storage.banned_ips.add(ip)
                self.server.storage.save_bans()
                self.server.network.send_to_client(client, "JSON_PAYLOAD:" + json.dumps(
                    {"type": "banned", "reason": reason}, ensure_ascii=False))
                time.sleep(0.1)
                self.server.network.remove_client(client)
                self.server.log(f"🛡️ Пользователь {nickname} забанен (IP: {ip})", "admin")
                return True
        self.server.log(f"❌ Пользователь {nickname} не найден в онлайне", "error")
        return False
    
    def unban_ip(self, ip):
        if ip in self.server.storage.banned_ips:
            self.server.storage.banned_ips.remove(ip)
            self.server.storage.save_bans()
            self.server.log(f"✅ IP {ip} разбанен", "system")
            return True
        self.server.log(f"❌ IP {ip} не найден в списке банов", "error")
        return False
    
    def mute_user(self, nickname, minutes):
        until = datetime.now() + timedelta(minutes=minutes)
        self.server.chat.muted_users[nickname] = until
        self.server.network.broadcast(json.dumps(
            {"type": "notification", "text": f"🔇 {nickname} получил мут на {minutes} мин."}, ensure_ascii=False))
        self.server.log(f"🛡️ Пользователь {nickname} замучен на {minutes} минут", "admin")
        self.server.root.after(0, self.server.update_online_display)
    
    def unmute_user(self, nickname):
        if nickname in self.server.chat.muted_users:
            del self.server.chat.muted_users[nickname]
            self.server.network.broadcast(json.dumps(
                {"type": "notification", "text": f"🔈 Мут с {nickname} снят."}, ensure_ascii=False))
            self.server.log(f"🛡️ Мут с пользователя {nickname} снят", "admin")
            self.server.root.after(0, self.server.update_online_display)
            return True
        self.server.log(f"❌ Пользователь {nickname} не в муте", "error")
        return False
    
    def delete_message(self, msg_id):
        for i, msg in enumerate(self.server.storage.messages_history):
            if msg.get('id') == msg_id:
                deleted_msg = self.server.storage.messages_history.pop(i)
                self.server.storage.save_history()
                self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps(
                    {"type": "message_deleted", "id": msg_id}, ensure_ascii=False))
                self.server.log(f"🛡️ Сообщение {msg_id} удалено (автор: {deleted_msg.get('sender')})", "admin")
                return True
        self.server.log(f"❌ Сообщение с ID {msg_id} не найдено", "error")
        return False
    
    def delete_file(self, file_id):
        for i, f in enumerate(self.server.storage.files_list):
            if f['id'] == file_id:
                try:
                    os.remove(f['path'])
                except:
                    pass
                deleted_file = self.server.storage.files_list.pop(i)
                self.server.storage.save_history()
                self.server.network.broadcast("JSON_PAYLOAD:" + json.dumps(
                    {"type": "file_deleted", "id": file_id}, ensure_ascii=False))
                self.server.log(f"🛡️ Файл {file_id} удалён (название: {deleted_file.get('name')})", "admin")
                return True
        self.server.log(f"❌ Файл с ID {file_id} не найден", "error")
        return False
    
    def show_online_users(self):
        self.server.log("="*50, "system")
        self.server.log(f"👥 ОНЛАЙН ПОЛЬЗОВАТЕЛИ ({len(self.server.clients)}):", "system")
        for client, data in self.server.client_data.items():
            nickname = data.get('nickname', 'Unknown')
            username = data.get('username', 'Unknown')
            addr = data.get('addr', 'Unknown')
            muted = "🔇" if nickname in self.server.chat.muted_users else ""
            self.server.log(f"   {muted} {nickname} (@{username}) - {addr}", "online")
        self.server.log("="*50, "system")
    
    def show_banned_ips(self):
        self.server.log("="*50, "system")
        self.server.log(f"🚫 ЗАБАНЕННЫЕ IP ({len(self.server.storage.banned_ips)}):", "system")
        for ip in self.server.storage.banned_ips:
            self.server.log(f"   ❌ {ip}", "error")
        self.server.log("="*50, "system")
    
    def show_recent_history(self, count=10):
        self.server.log("="*50, "system")
        self.server.log(f"📜 ПОСЛЕДНИЕ {min(count, len(self.server.storage.messages_history))} СООБЩЕНИЙ:", "system")
        for msg in self.server.storage.messages_history[-count:]:
            sender = msg.get('sender', 'Unknown')
            text = msg.get('text', '')[:50]
            msg_id = msg.get('id', '')
            self.server.log(f"   [{msg_id}] {sender}: {text}...", "system")
        self.server.log("="*50, "system")