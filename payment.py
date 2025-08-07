import logging
import uuid
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import time

try:
    from yoomoney import Quickpay, Client
except ImportError:
    # Заглушка для случая, если библиотека не установлена
    class Quickpay:
        def __init__(self, **kwargs):
            self.redirected_url = "https://example.com/payment"
    
    class Client:
        def __init__(self, token):
            pass
        
        def operation_history(self, **kwargs):
            return type('obj', (object,), {'operations': []})

from config import TARIFFS
from database import Database

logger = logging.getLogger(__name__)

class PaymentManager:
    def __init__(self, yoomoney_token: str = None, receiver_wallet: str = None):
        """
        Инициализация менеджера платежей
        
        Args:
            yoomoney_token: Токен YooMoney API
            receiver_wallet: Номер кошелька получателя
        """
        self.yoomoney_token = yoomoney_token
        self.receiver_wallet = receiver_wallet
        self.db = Database()
        
        # Инициализация клиента YooMoney
        if yoomoney_token:
            try:
                self.client = Client(yoomoney_token)
                logger.info("YooMoney клиент инициализирован")
            except Exception as e:
                logger.error(f"Ошибка инициализации YooMoney клиента: {e}")
                self.client = None
        else:
            self.client = None
            logger.warning("YooMoney токен не предоставлен")
    
    def generate_payment_label(self, user_id: int, tariff_key: str) -> str:
        """Генерация уникальной метки для платежа"""
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        return f"airidder_{user_id}_{tariff_key}_{timestamp}_{unique_id}"
    
    def create_payment_link(self, user_id: int, tariff_key: str) -> Optional[Dict[str, Any]]:
        """
        Создание ссылки на оплату
        
        Args:
            user_id: ID пользователя
            tariff_key: Ключ тарифа (one, three, ten)
            
        Returns:
            Dict с информацией о платеже или None при ошибке
        """
        if tariff_key not in TARIFFS:
            logger.error(f"Неизвестный тариф: {tariff_key}")
            return None
        
        if not self.receiver_wallet:
            logger.error("Номер кошелька получателя не настроен")
            return None
        
        tariff = TARIFFS[tariff_key]
        payment_label = self.generate_payment_label(user_id, tariff_key)
        
        try:
            # Создаем быстрый платеж
            quickpay = Quickpay(
                receiver=self.receiver_wallet,
                quickpay_form="shop",
                targets=f"Покупка анализов в AiRidder Bot - {tariff['label']}",
                paymentType="SB",  # Способ оплаты: банковская карта
                sum=tariff['price'],
                label=payment_label
            )
            
            # Сохраняем информацию о платеже в базу данных
            payment_info = {
                'user_id': user_id,
                'payment_id': payment_label,
                'amount': tariff['price'],
                'credits': tariff['credits'],
                'tariff_key': tariff_key,
                'payment_url': quickpay.redirected_url,
                'created_at': datetime.now()
            }
            
            # Сохраняем в базу данных
            success = self.db.create_payment(
                user_id=user_id,
                payment_id=payment_label,
                amount=tariff['price'],
                credits=tariff['credits']
            )
            
            if success:
                logger.info(f"Создан платеж для пользователя {user_id}: {payment_label}")
                return payment_info
            else:
                logger.error(f"Ошибка сохранения платежа в БД: {payment_label}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка создания платежа: {e}")
            return None
    
    def check_payment_status(self, payment_label: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Проверка статуса платежа
        
        Args:
            payment_label: Метка платежа
            
        Returns:
            Tuple[bool, Optional[Dict]]: (оплачен ли, информация об операции)
        """
        if not self.client:
            logger.error("YooMoney клиент не инициализирован")
            return False, None
        
        try:
            # Получаем историю операций по метке
            history = self.client.operation_history(label=payment_label)
            
            # Проверяем, есть ли успешные операции
            for operation in history.operations:
                if (operation.status == "success" and 
                    operation.direction == "in" and 
                    operation.label == payment_label):
                    
                    operation_info = {
                        'operation_id': operation.operation_id,
                        'status': operation.status,
                        'datetime': operation.datetime,
                        'amount': operation.amount,
                        'label': operation.label,
                        'title': operation.title
                    }
                    
                    logger.info(f"Найден успешный платеж: {payment_label}")
                    return True, operation_info
            
            logger.info(f"Платеж не найден или не оплачен: {payment_label}")
            return False, None
            
        except Exception as e:
            logger.error(f"Ошибка проверки статуса платежа: {e}")
            return False, None
    
    def process_successful_payment(self, payment_label: str) -> bool:
        """
        Обработка успешного платежа - начисление кредитов
        
        Args:
            payment_label: Метка платежа
            
        Returns:
            bool: Успешно ли обработан платеж
        """
        try:
            # Завершаем платеж в базе данных и начисляем кредиты
            payment_info = self.db.complete_payment(payment_label)
            
            if payment_info:
                logger.info(f"Платеж {payment_label} успешно обработан, начислено {payment_info['credits']} кредитов")
                return True
            else:
                logger.error(f"Не удалось обработать платеж: {payment_label}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка обработки платежа: {e}")
            return False
    
    def check_pending_payments(self) -> list:
        """
        Проверка всех ожидающих платежей
        
        Returns:
            list: Список успешно обработанных платежей
        """
        if not self.client:
            return []
        
        processed_payments = []
        
        try:
            # Получаем все ожидающие платежи из базы данных
            # Это упрощенная версия - в реальности нужно добавить метод в Database
            # Пока что проверим последние операции
            
            # Получаем историю операций за последние 24 часа
            history = self.client.operation_history()
            
            for operation in history.operations:
                if (operation.status == "success" and 
                    operation.direction == "in" and 
                    operation.label and 
                    operation.label.startswith("airidder_")):
                    
                    # Проверяем, не обработан ли уже этот платеж
                    if self.process_successful_payment(operation.label):
                        processed_payments.append({
                            'label': operation.label,
                            'amount': operation.amount,
                            'datetime': operation.datetime
                        })
            
            if processed_payments:
                logger.info(f"Обработано {len(processed_payments)} платежей")
            
            return processed_payments
            
        except Exception as e:
            logger.error(f"Ошибка проверки ожидающих платежей: {e}")
            return []
    
    def get_payment_info_from_label(self, payment_label: str) -> Optional[Dict[str, Any]]:
        """
        Извлечение информации из метки платежа
        
        Args:
            payment_label: Метка платежа
            
        Returns:
            Dict с информацией или None
        """
        try:
            # Формат: airidder_{user_id}_{tariff_key}_{timestamp}_{unique_id}
            parts = payment_label.split('_')
            if len(parts) >= 5 and parts[0] == "airidder":
                return {
                    'user_id': int(parts[1]),
                    'tariff_key': parts[2],
                    'timestamp': int(parts[3]),
                    'unique_id': parts[4]
                }
        except Exception as e:
            logger.error(f"Ошибка парсинга метки платежа: {e}")
        
        return None

# Создаем глобальный экземпляр менеджера платежей
# Токен и кошелек будут настроены позже через переменные окружения
payment_manager = PaymentManager()

