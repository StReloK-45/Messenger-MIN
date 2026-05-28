#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для очистки файлов и папок, создаваемых сервером и клиентом

Запуск: python cleanup.py
"""

import os
import sys
import shutil
import json
from pathlib import Path


class Colors:
    """Цвета для консоли"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_ok(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")


def print_header():
    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║                    ОЧИСТКА СЕРВЕРА И КЛИЕНТА                     ║")
    print("║              Удаление временных файлов и кэша                    ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.END}\n")


def get_project_root() -> Path:
    """Получает корневую директорию проекта"""
    return Path(__file__).parent.absolute()


def get_size(path: Path) -> str:
    """Возвращает размер папки/файла в человекочитаемом формате"""
    if not path.exists():
        return "0 B"
    
    if path.is_file():
        size = path.stat().st_size
    else:
        size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def delete_path(path: Path) -> bool:
    """Удаляет файл или папку"""
    try:
        if path.is_file():
            path.unlink()
            print_ok(f"Удалён файл: {path}")
        elif path.is_dir():
            shutil.rmtree(path)
            print_ok(f"Удалена папка: {path}")
        return True
    except Exception as e:
        print_error(f"Ошибка при удалении {path}: {e}")
        return False


def list_items(path: Path, pattern: str = "*") -> list:
    """Возвращает список файлов/папок по шаблону"""
    if not path.exists():
        return []
    return list(path.glob(pattern))


class CleanupManager:
    """Управление очисткой файлов"""
    
    def __init__(self):
        self.root = get_project_root()
        self.server_dir = self.root / "server"
        self.client_dir = self.root / "client"
        
        # Папки для очистки
        self.dirs_to_clean = [
            self.server_dir / "logs",
            self.server_dir / "data" / "received_files",
            self.client_dir / "logs",
        ]
        
        # Файлы для очистки
        self.files_to_clean = [
            self.server_dir / "data" / "database.db",
            self.server_dir / "data" / "users.json",
            self.server_dir / "data" / "messages.json",
            self.server_dir / "data" / "private_messages.json",
            self.server_dir / "data" / "banned.json",
            self.server_dir / "data" / "groups.json",
            self.client_dir / "settings.json",
            self.client_dir / "chat_config.ini",
            self.client_dir / "friends.json",
            self.client_dir / "cache.json",
        ]
        
        # Настройки клиента (сохраняемые)
        self.client_settings_files = [
            self.client_dir / "settings.json",
            self.client_dir / "chat_config.ini",
            self.client_dir / "friends.json",
        ]
    
    def show_menu(self):
        """Показывает меню выбора"""
        while True:
            print_header()
            print("1. Удалить ВСЁ (БД, файлы, логи, кэш, настройки)")
            print("2. Удалить всё, КРОМЕ БД (сохранить пользователей и сообщения)")
            print("3. Удалить всё, КРОМЕ БД и настроек клиента")
            print("4. Показать информацию о файлах (без удаления)")
            print("0. Выход")
            print("-" * 60)
            
            choice = input("\nВыберите опцию (0-4): ").strip()
            
            if choice == "1":
                self.clean_all()
            elif choice == "2":
                self.clean_keep_db()
            elif choice == "3":
                self.clean_keep_db_and_settings()
            elif choice == "4":
                self.show_info()
            elif choice == "0":
                print_info("Выход...")
                sys.exit(0)
            else:
                print_error("Неверный выбор!")
                input("\nНажмите Enter для продолжения...")
    
    def show_info(self):
        """Показывает информацию о файлах без удаления"""
        print_header()
        print_info("ИНФОРМАЦИЯ О ФАЙЛАХ И ПАПКАХ:")
        print("-" * 60)
        
        total_size = 0
        
        # Папки
        for dir_path in self.dirs_to_clean:
            if dir_path.exists():
                size = get_size(dir_path)
                print(f"  📁 {dir_path.relative_to(self.root)}: {size}")
                total_size += float(size.split()[0]) if size.split()[1] == 'MB' else 0
            else:
                print(f"  📁 {dir_path.relative_to(self.root)}: не существует")
        
        # Файлы
        for file_path in self.files_to_clean:
            if file_path.exists():
                size = get_size(file_path)
                print(f"  📄 {file_path.relative_to(self.root)}: {size}")
            else:
                print(f"  📄 {file_path.relative_to(self.root)}: не существует")
        
        print("-" * 60)
        print_info(f"Общий размер: {get_size(self.root)}")
        print_info(f"Корневая директория: {self.root}")
        input("\nНажмите Enter для продолжения...")
    
    def clean_all(self):
        """Удаляет всё"""
        print_header()
        print_warning("ВНИМАНИЕ! Это действие удалит ВСЕ данные!")
        confirm = input("Вы уверены? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print_info("Отменено.")
            input("\nНажмите Enter для продолжения...")
            return
        
        print_info("Начинаю очистку...")
        
        # Удаляем папки
        for dir_path in self.dirs_to_clean:
            if dir_path.exists():
                delete_path(dir_path)
        
        # Удаляем файлы
        for file_path in self.files_to_clean:
            if file_path.exists():
                delete_path(file_path)
        
        # Очищаем содержимое корневых папок, но не удаляем их
        for dir_path in self.dirs_to_clean:
            if dir_path.exists():
                for item in dir_path.iterdir():
                    try:
                        if item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    except:
                        pass
        
        # Создаём пустые папки заново
        for dir_path in self.dirs_to_clean:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        print_ok("Очистка завершена!")
        input("\nНажмите Enter для продолжения...")
    
    def clean_keep_db(self):
        """Удаляет всё, кроме БД"""
        print_header()
        print_warning("Будут удалены: логи, файлы, кэш. БД (пользователи, сообщения) сохранена.")
        confirm = input("Продолжить? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print_info("Отменено.")
            input("\nНажмите Enter для продолжения...")
            return
        
        print_info("Начинаю очистку...")
        
        # Удаляем логи
        logs_dir = self.server_dir / "logs"
        if logs_dir.exists():
            for item in logs_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except:
                    pass
            print_ok(f"Очищена папка: {logs_dir}")
        
        # Удаляем полученные файлы
        files_dir = self.server_dir / "data" / "received_files"
        if files_dir.exists():
            for item in files_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except:
                    pass
            print_ok(f"Очищена папка: {files_dir}")
        
        # Удаляем кэш клиента
        client_cache = self.client_dir / "cache.json"
        if client_cache.exists():
            delete_path(client_cache)
        
        # Удаляем JSON файлы (кроме БД)
        json_files = [
            self.server_dir / "data" / "users.json",
            self.server_dir / "data" / "messages.json",
            self.server_dir / "data" / "private_messages.json",
            self.server_dir / "data" / "banned.json",
            self.server_dir / "data" / "groups.json",
        ]
        
        for file_path in json_files:
            if file_path.exists():
                delete_path(file_path)
        
        print_ok("Очистка завершена! БД сохранена.")
        input("\nНажмите Enter для продолжения...")
    
    def clean_keep_db_and_settings(self):
        """Удаляет всё, кроме БД и настроек клиента"""
        print_header()
        print_warning("Будут удалены: логи, файлы, кэш.")
        print_info("Сохранены: БД (пользователи, сообщения) и настройки клиента.")
        confirm = input("Продолжить? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print_info("Отменено.")
            input("\nНажмите Enter для продолжения...")
            return
        
        print_info("Начинаю очистку...")
        
        # Удаляем логи
        logs_dir = self.server_dir / "logs"
        if logs_dir.exists():
            for item in logs_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except:
                    pass
            print_ok(f"Очищена папка: {logs_dir}")
        
        # Удаляем полученные файлы
        files_dir = self.server_dir / "data" / "received_files"
        if files_dir.exists():
            for item in files_dir.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                except:
                    pass
            print_ok(f"Очищена папка: {files_dir}")
        
        # Удаляем JSON файлы, КРОМЕ настроек клиента
        json_files_to_delete = [
            self.server_dir / "data" / "users.json",
            self.server_dir / "data" / "messages.json",
            self.server_dir / "data" / "private_messages.json",
            self.server_dir / "data" / "banned.json",
            self.server_dir / "data" / "groups.json",
        ]
        
        for file_path in json_files_to_delete:
            if file_path.exists():
                delete_path(file_path)
        
        # Создаём папки заново
        for dir_path in self.dirs_to_clean:
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
        
        print_ok("Очистка завершена! БД и настройки клиента сохранены.")
        input("\nНажмите Enter для продолжения...")


def main():
    manager = CleanupManager()
    manager.show_menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        sys.exit(0)
    except Exception as e:
        print_error(f"Ошибка: {e}")
        sys.exit(1)