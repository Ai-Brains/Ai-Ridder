import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    credits INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица платежей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    payment_id TEXT UNIQUE,
                    amount REAL,
                    credits INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица сообщений поддержки
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS support_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'new',
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица анализов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    text_length INTEGER,
                    tokens_used INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()
            logger.info("База данных инициализирована")
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить пользователя по ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_user(self, user_id: int, username: str = None, 
                   first_name: str = None, last_name: str = None) -> bool:
        """Создать нового пользователя с 1 бесплатным кредитом"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (user_id, username, first_name, last_name, credits)
                    VALUES (?, ?, ?, ?, 1)
                ''', (user_id, username, first_name, last_name))
                conn.commit()
                logger.info(f"Создан новый пользователь: {user_id}")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"Пользователь {user_id} уже существует")
            return False
    
    def update_user_activity(self, user_id: int):
        """Обновить время последней активности пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_activity = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
    
    def get_user_credits(self, user_id: int) -> int:
        """Получить количество кредитов пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else 0
    
    def spend_credit(self, user_id: int) -> bool:
        """Списать 1 кредит у пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET credits = credits - 1 
                WHERE user_id = ? AND credits > 0
            ''', (user_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def add_credits(self, user_id: int, credits: int) -> bool:
        """Добавить кредиты пользователю"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET credits = credits + ? 
                    WHERE user_id = ?
                ''', (credits, user_id))
                conn.commit()
                logger.info(f"Добавлено {credits} кредитов пользователю {user_id}")
                return True
        except Exception as e:
            logger.error(f"Ошибка добавления кредитов: {e}")
            return False
    
    def create_payment(self, user_id: int, payment_id: str, 
                      amount: float, credits: int) -> bool:
        """Создать запись о платеже"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO payments (user_id, payment_id, amount, credits)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, payment_id, amount, credits))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            return False
    
    def complete_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Завершить платеж и начислить кредиты"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Получить информацию о платеже
                cursor.execute('''
                    SELECT * FROM payments 
                    WHERE payment_id = ? AND status = 'pending'
                ''', (payment_id,))
                payment = cursor.fetchone()
                
                if not payment:
                    return None
                
                # Обновить статус платежа
                cursor.execute('''
                    UPDATE payments 
                    SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                    WHERE payment_id = ?
                ''', (payment_id,))
                
                # Начислить кредиты
                cursor.execute('''
                    UPDATE users SET credits = credits + ?
                    WHERE user_id = ?
                ''', (payment['credits'], payment['user_id']))
                
                conn.commit()
                logger.info(f"Платеж {payment_id} завершен, начислено {payment['credits']} кредитов")
                return dict(payment)
                
        except Exception as e:
            logger.error(f"Ошибка завершения платежа: {e}")
            return None
    
    def save_support_message(self, user_id: int, message: str) -> bool:
        """Сохранить сообщение в поддержку"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO support_messages (user_id, message)
                    VALUES (?, ?)
                ''', (user_id, message))
                conn.commit()
                logger.info(f"Сохранено сообщение поддержки от пользователя {user_id}")
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения поддержки: {e}")
            return False
    
    def save_analysis(self, user_id: int, role: str, text_length: int, tokens_used: int) -> bool:
        """Сохранить информацию об анализе"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO analyses (user_id, role, text_length, tokens_used)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, role, text_length, tokens_used))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка сохранения анализа: {e}")
            return False

