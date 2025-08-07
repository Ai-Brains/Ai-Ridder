import openai
import tiktoken
import logging
from typing import Optional, Tuple
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_BASE, MAX_TOKENS_PER_REQUEST
from roles import ROLES

logger = logging.getLogger(__name__)

class DeepSeekAPI:
    def __init__(self):
        """Инициализация клиента DeepSeek API"""
        self.client = openai.OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_API_BASE
        )
        
        # Инициализация токенизатора для подсчета токенов
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.error(f"Ошибка инициализации токенизатора: {e}")
            self.tokenizer = None
    
    def count_tokens(self, text: str) -> int:
        """Подсчет количества токенов в тексте"""
        if not self.tokenizer:
            # Приблизительная оценка: 1 токен ≈ 4 символа для русского текста
            return len(text) // 4
        
        try:
            return len(self.tokenizer.encode(text))
        except Exception as e:
            logger.error(f"Ошибка подсчета токенов: {e}")
            return len(text) // 4
    
    def prepare_messages(self, role_key: str, user_text: str) -> list:
        """Подготовка сообщений для API"""
        if role_key not in ROLES:
            raise ValueError(f"Неизвестная роль: {role_key}")
        
        role_info = ROLES[role_key]
        
        messages = [
            {
                "role": "system",
                "content": role_info["prompt"]
            },
            {
                "role": "user", 
                "content": f"Проанализируй следующий текст:\n\n{user_text}"
            }
        ]
        
        return messages
    
    async def analyze_text(self, role_key: str, user_text: str) -> Tuple[Optional[str], int]:
        """
        Анализ текста с помощью DeepSeek API
        
        Args:
            role_key: Ключ роли (beta_reader, proofreader, editor)
            user_text: Текст для анализа
            
        Returns:
            Tuple[Optional[str], int]: (результат анализа, количество использованных токенов)
        """
        try:
            # Подготавливаем сообщения
            messages = self.prepare_messages(role_key, user_text)
            
            # Подсчитываем токены в запросе
            total_tokens = sum(self.count_tokens(msg["content"]) for msg in messages)
            
            # Проверяем лимит токенов
            if total_tokens > MAX_TOKENS_PER_REQUEST:
                logger.warning(f"Превышен лимит токенов: {total_tokens} > {MAX_TOKENS_PER_REQUEST}")
                return None, total_tokens
            
            logger.info(f"Отправка запроса к DeepSeek API. Роль: {role_key}, токенов: {total_tokens}")
            
            # Отправляем запрос к API
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=4000,
                temperature=0.7,
                stream=False
            )
            
            # Извлекаем результат
            if response.choices and len(response.choices) > 0:
                result = response.choices[0].message.content
                
                # Подсчитываем общее количество токенов (запрос + ответ)
                response_tokens = self.count_tokens(result) if result else 0
                total_used_tokens = total_tokens + response_tokens
                
                logger.info(f"Получен ответ от DeepSeek API. Токенов использовано: {total_used_tokens}")
                
                return result, total_used_tokens
            else:
                logger.error("Пустой ответ от DeepSeek API")
                return None, total_tokens
                
        except openai.RateLimitError as e:
            logger.error(f"Превышен лимит запросов к DeepSeek API: {e}")
            return "❌ Превышен лимит запросов к API. Попробуйте позже.", 0
            
        except openai.APIError as e:
            logger.error(f"Ошибка API DeepSeek: {e}")
            return "❌ Ошибка при обращении к API. Попробуйте позже.", 0
            
        except Exception as e:
            logger.error(f"Неожиданная ошибка при работе с DeepSeek API: {e}")
            return "❌ Произошла ошибка при анализе текста. Попробуйте позже.", 0
    
    def validate_text_length(self, text: str) -> Tuple[bool, str]:
        """
        Проверка длины текста и количества токенов
        
        Args:
            text: Текст для проверки
            
        Returns:
            Tuple[bool, str]: (валиден ли текст, сообщение об ошибке)
        """
        # Проверяем количество символов
        if len(text) > 200000:
            return False, f"Текст слишком длинный: {len(text):,} символов (максимум 200,000)"
        
        # Проверяем количество токенов
        tokens = self.count_tokens(text)
        if tokens > MAX_TOKENS_PER_REQUEST:
            return False, f"Слишком много токенов: {tokens:,} (максимум {MAX_TOKENS_PER_REQUEST:,})"
        
        return True, ""
    
    def get_role_description(self, role_key: str) -> str:
        """Получить описание роли"""
        if role_key in ROLES:
            return ROLES[role_key]["name"]
        return "Неизвестная роль"

# Создаем глобальный экземпляр API
deepseek_api = DeepSeekAPI()

