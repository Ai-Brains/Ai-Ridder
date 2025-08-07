#!/usr/bin/env python3
"""
Тестовый скрипт для проверки импортов и инициализации модулей
"""

import sys
import os

def test_imports():
    """Тестирование импортов всех модулей"""
    print("🔄 Тестирование импортов...")
    
    try:
        # Основные библиотеки
        import sqlite3
        print("✅ sqlite3 - OK")
        
        import logging
        print("✅ logging - OK")
        
        from datetime import datetime
        print("✅ datetime - OK")
        
        # Telegram Bot
        from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
        print("✅ python-telegram-bot - OK")
        
        # OpenAI / DeepSeek
        import openai
        print("✅ openai - OK")
        
        import tiktoken
        print("✅ tiktoken - OK")
        
        # YooMoney
        try:
            from yoomoney import Quickpay, Client
            print("✅ yoomoney - OK")
        except ImportError as e:
            print(f"⚠️ yoomoney - Импорт не удался: {e}")
        
        # Другие зависимости
        import requests
        print("✅ requests - OK")
        
        from dotenv import load_dotenv
        print("✅ python-dotenv - OK")
        
        import flask
        print("✅ flask - OK")
        
        print("\n🔄 Тестирование локальных модулей...")
        
        # Локальные модули
        from database import Database
        print("✅ database - OK")
        
        from config import TELEGRAM_BOT_TOKEN, DEEPSEEK_API_KEY, TARIFFS
        print("✅ config - OK")
        
        from roles import ROLES
        print("✅ roles - OK")
        
        from deepseek_api import deepseek_api
        print("✅ deepseek_api - OK")
        
        from payment import PaymentManager
        print("✅ payment - OK")
        
        print("\n✅ Все импорты успешны!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
        return False

def test_database():
    """Тестирование базы данных"""
    print("\n🔄 Тестирование базы данных...")
    
    try:
        from database import Database
        
        # Создаем тестовую базу данных
        db = Database("test_bot.db")
        print("✅ База данных инициализирована")
        
        # Тестируем создание пользователя
        test_user_id = 123456789
        success = db.create_user(test_user_id, "test_user", "Test", "User")
        if success:
            print("✅ Пользователь создан")
        else:
            print("⚠️ Пользователь уже существует")
        
        # Тестируем получение пользователя
        user = db.get_user(test_user_id)
        if user:
            print(f"✅ Пользователь получен: {user['credits']} кредитов")
        else:
            print("❌ Пользователь не найден")
        
        # Удаляем тестовую базу данных
        os.remove("test_bot.db")
        print("✅ Тестовая база данных удалена")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования базы данных: {e}")
        return False

def test_config():
    """Тестирование конфигурации"""
    print("\n🔄 Тестирование конфигурации...")
    
    try:
        from config import TELEGRAM_BOT_TOKEN, DEEPSEEK_API_KEY, TARIFFS, MESSAGES
        
        print(f"✅ Telegram Bot Token: {'Настроен' if TELEGRAM_BOT_TOKEN else 'Не настроен'}")
        print(f"✅ DeepSeek API Key: {'Настроен' if DEEPSEEK_API_KEY else 'Не настроен'}")
        print(f"✅ Тарифы: {len(TARIFFS)} тарифов")
        print(f"✅ Сообщения: {len(MESSAGES)} сообщений")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования конфигурации: {e}")
        return False

def test_roles():
    """Тестирование ролей"""
    print("\n🔄 Тестирование ролей...")
    
    try:
        from roles import ROLES
        
        expected_roles = ['beta_reader', 'proofreader', 'editor']
        for role in expected_roles:
            if role in ROLES:
                print(f"✅ Роль '{ROLES[role]['name']}' - OK")
            else:
                print(f"❌ Роль '{role}' не найдена")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования ролей: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов AiRidder Bot\n")
    
    tests = [
        test_imports,
        test_database,
        test_config,
        test_roles
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Результаты тестирования: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены успешно! Бот готов к запуску.")
        return True
    else:
        print("⚠️ Некоторые тесты не пройдены. Проверьте конфигурацию.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

