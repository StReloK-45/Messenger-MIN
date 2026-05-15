# server/migrate_db.py
import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")
    
    print(f"🔧 Миграция БД для групп...")
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        print("Сначала запустите сервер для создания БД")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Проверяем и обновляем таблицу groups
    try:
        cursor.execute("ALTER TABLE groups ADD COLUMN encrypted BOOLEAN DEFAULT 0")
        print("✅ Добавлена колонка encrypted в groups")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE groups ADD COLUMN encryption_key TEXT")
        print("✅ Добавлена колонка encryption_key в groups")
    except:
        pass
    
    # Проверяем и обновляем таблицу group_members
    try:
        cursor.execute("ALTER TABLE group_members ADD COLUMN is_admin BOOLEAN DEFAULT 0")
        print("✅ Добавлена колонка is_admin в group_members")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE group_members ADD COLUMN is_banned BOOLEAN DEFAULT 0")
        print("✅ Добавлена колонка is_banned в group_members")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE group_members ADD COLUMN banned_at TIMESTAMP")
        print("✅ Добавлена колонка banned_at в group_members")
    except:
        pass
    
    # Проверяем и обновляем таблицу group_messages
    try:
        cursor.execute("ALTER TABLE group_messages ADD COLUMN is_deleted BOOLEAN DEFAULT 0")
        print("✅ Добавлена колонка is_deleted в group_messages")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE group_messages ADD COLUMN deleted_by INTEGER")
        print("✅ Добавлена колонка deleted_by в group_messages")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE group_messages ADD COLUMN encrypted BOOLEAN DEFAULT 0")
        print("✅ Добавлена колонка encrypted в group_messages")
    except:
        pass
    
    # Создаём таблицу group_files если её нет
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
    print("✅ Таблица group_files создана")
    
    # Обновляем существующих участников групп - делаем создателей админами
    cursor.execute('''
        UPDATE group_members 
        SET is_admin = 1 
        WHERE (group_id, user_id) IN (
            SELECT id, creator_id FROM groups
        )
    ''')
    print("✅ Создатели групп назначены админами")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Миграция завершена!")

if __name__ == "__main__":
    migrate()