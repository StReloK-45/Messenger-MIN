# server/migrate_db.py
import sqlite3
import os

def migrate():
    db_path = os.path.join(os.path.dirname(__file__), "data", "database.db")
    
    if not os.path.exists(db_path):
        print(f"❌ База данных не найдена: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Добавляем колонку nickname в таблицу users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN nickname TEXT DEFAULT ''")
        print("✅ Колонка nickname добавлена в users")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️ Колонка nickname уже существует в users")
        else:
            print(f"❌ Ошибка: {e}")
    
    # Добавляем колонку sender_nickname в group_messages (если нет)
    try:
        cursor.execute("ALTER TABLE group_messages ADD COLUMN sender_nickname TEXT DEFAULT ''")
        print("✅ Колонка sender_nickname добавлена в group_messages")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("⚠️ Колонка sender_nickname уже существует в group_messages")
        else:
            print(f"❌ Ошибка: {e}")
    
    # Обновляем существующие записи: копируем username в nickname
    try:
        cursor.execute("UPDATE users SET nickname = username WHERE nickname = ''")
        print("✅ Обновлены nickname из username")
    except Exception as e:
        print(f"⚠️ Не обновлены nickname: {e}")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Миграция завершена!")

if __name__ == "__main__":
    migrate()