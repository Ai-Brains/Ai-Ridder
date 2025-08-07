import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from database import Database
from config import TELEGRAM_BOT_TOKEN, ADMIN_USER_ID, MESSAGES, TARIFFS, MAX_TEXT_LENGTH, YOOMONEY_TOKEN, YOOMONEY_WALLET
from roles import ROLES
from deepseek_api import deepseek_api
from payment import PaymentManager
import tiktoken

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()

# Инициализация менеджера платежей
payment_manager = PaymentManager(YOOMONEY_TOKEN, YOOMONEY_WALLET)

# Состояния пользователей
user_states = {}

# Главное меню
MAIN_MENU = [
    ['👤 Роли', '💳 Купить анализы'],
    ['💰 Мой баланс', '🆘 Поддержка'],
    ['ℹ️ О сервисе']
]

# Меню ролей
ROLES_MENU = [
    ['📖 Бета-ридер', '✏️ Корректор'],
    ['📝 Редактор', '🔙 Назад']
]

class BotStates:
    MAIN_MENU = "main_menu"
    ROLE_SELECTION = "role_selection"
    WAITING_FOR_TEXT = "waiting_for_text"
    WAITING_FOR_SUPPORT_MESSAGE = "waiting_for_support_message"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    # Обновляем активность пользователя
    db.update_user_activity(user_id)
    
    # Проверяем, есть ли пользователь в базе
    existing_user = db.get_user(user_id)
    if not existing_user:
        # Создаем нового пользователя с 1 бесплатным кредитом
        db.create_user(
            user_id=user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        logger.info(f"Создан новый пользователь: {user_id}")
    
    # Устанавливаем состояние главного меню
    user_states[user_id] = BotStates.MAIN_MENU
    
    # Отправляем приветствие с главным меню
    reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
    await update.message.reply_text(
        MESSAGES['welcome'],
        reply_markup=reply_markup
    )

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик главного меню"""
    user_id = update.effective_user.id
    text = update.message.text
    
    db.update_user_activity(user_id)
    
    if text == '👤 Роли':
        # Переходим к выбору роли
        user_states[user_id] = BotStates.ROLE_SELECTION
        reply_markup = ReplyKeyboardMarkup(ROLES_MENU, resize_keyboard=True)
        await update.message.reply_text(
            MESSAGES['choose_role'],
            reply_markup=reply_markup
        )
    
    elif text == '💳 Купить анализы':
        await show_purchase_menu(update, context)
    
    elif text == '💰 Мой баланс':
        credits = db.get_user_credits(user_id)
        purchase_suggestion = MESSAGES['purchase_suggestion'] if credits < 3 else ""
        await update.message.reply_text(
            MESSAGES['balance'].format(
                credits=credits,
                purchase_suggestion=purchase_suggestion
            )
        )
    
    elif text == '🆘 Поддержка':
        user_states[user_id] = BotStates.WAITING_FOR_SUPPORT_MESSAGE
        await update.message.reply_text(MESSAGES['support_request'])
    
    elif text == 'ℹ️ О сервисе':
        await update.message.reply_text(MESSAGES['about'])

async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора роли"""
    user_id = update.effective_user.id
    text = update.message.text
    
    db.update_user_activity(user_id)
    
    if text == '🔙 Назад':
        # Возвращаемся в главное меню
        user_states[user_id] = BotStates.MAIN_MENU
        reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=reply_markup
        )
        return
    
    # Определяем выбранную роль
    role_key = None
    if text == '📖 Бета-ридер':
        role_key = 'beta_reader'
    elif text == '✏️ Корректор':
        role_key = 'proofreader'
    elif text == '📝 Редактор':
        role_key = 'editor'
    
    if role_key:
        # Сохраняем выбранную роль в контексте пользователя
        context.user_data['selected_role'] = role_key
        user_states[user_id] = BotStates.WAITING_FOR_TEXT
        
        # Убираем клавиатуру и просим отправить текст
        await update.message.reply_text(
            MESSAGES['role_selected'].format(
                role=ROLES[role_key]['name'],
                max_length=MAX_TEXT_LENGTH
            ),
            reply_markup=ReplyKeyboardMarkup([['🔙 Назад в меню']], resize_keyboard=True)
        )

async def handle_text_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик анализа текста"""
    user_id = update.effective_user.id
    text = update.message.text
    
    db.update_user_activity(user_id)
    
    if text == '🔙 Назад в меню':
        # Возвращаемся в главное меню
        user_states[user_id] = BotStates.MAIN_MENU
        reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
        await update.message.reply_text(
            "Главное меню:",
            reply_markup=reply_markup
        )
        return
    
    # Проверяем длину текста и токены
    is_valid, error_message = deepseek_api.validate_text_length(text)
    if not is_valid:
        await update.message.reply_text(f"❌ {error_message}")
        return
    
    # Проверяем баланс пользователя
    credits = db.get_user_credits(user_id)
    if credits < 1:
        await update.message.reply_text(
            MESSAGES['no_credits'].format(credits=credits)
        )
        return
    
    # Получаем выбранную роль
    selected_role = context.user_data.get('selected_role')
    if not selected_role:
        await update.message.reply_text(
            "Ошибка: роль не выбрана. Пожалуйста, выберите роль заново."
        )
        user_states[user_id] = BotStates.ROLE_SELECTION
        reply_markup = ReplyKeyboardMarkup(ROLES_MENU, resize_keyboard=True)
        await update.message.reply_text(
            MESSAGES['choose_role'],
            reply_markup=reply_markup
        )
        return
    
    # Отправляем сообщение о начале анализа
    await update.message.reply_text(
        MESSAGES['analyzing'].format(
            role=ROLES[selected_role]['name'],
            length=len(text)
        )
    )
    
    # Выполняем анализ через DeepSeek API
    try:
        analysis_result, tokens_used = await deepseek_api.analyze_text(selected_role, text)
        
        if analysis_result is None:
            await update.message.reply_text(
                "❌ Не удалось выполнить анализ. Возможно, текст слишком длинный или произошла ошибка API."
            )
            return
        
        # Списываем кредит только при успешном анализе
        if db.spend_credit(user_id):
            # Сохраняем информацию об анализе
            db.save_analysis(user_id, selected_role, len(text), tokens_used)
            
            # Отправляем результат анализа
            # Разбиваем длинный результат на части, если необходимо
            max_message_length = 4096
            if len(analysis_result) <= max_message_length:
                await update.message.reply_text(analysis_result)
            else:
                # Разбиваем на части
                parts = []
                current_part = ""
                lines = analysis_result.split('\n')
                
                for line in lines:
                    if len(current_part + line + '\n') <= max_message_length:
                        current_part += line + '\n'
                    else:
                        if current_part:
                            parts.append(current_part.strip())
                        current_part = line + '\n'
                
                if current_part:
                    parts.append(current_part.strip())
                
                # Отправляем части
                for i, part in enumerate(parts):
                    if i == 0:
                        await update.message.reply_text(f"📝 Анализ (часть {i+1}/{len(parts)}):\n\n{part}")
                    else:
                        await update.message.reply_text(f"📝 Продолжение (часть {i+1}/{len(parts)}):\n\n{part}")
            
            # Отправляем информацию о завершении
            remaining_credits = db.get_user_credits(user_id)
            await update.message.reply_text(
                MESSAGES['analysis_complete'].format(credits=remaining_credits)
            )
            
            # Возвращаемся в главное меню
            user_states[user_id] = BotStates.MAIN_MENU
            reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
            await update.message.reply_text(
                "Главное меню:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "Ошибка при списании кредита. Попробуйте позже."
            )
            
    except Exception as e:
        logger.error(f"Ошибка при анализе текста: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при анализе текста. Попробуйте позже."
        )

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик сообщений поддержки"""
    user_id = update.effective_user.id
    message = update.message.text
    
    db.update_user_activity(user_id)
    
    # Сохраняем сообщение в базу данных
    if db.save_support_message(user_id, message):
        # Пересылаем сообщение администратору
        try:
            user = update.effective_user
            admin_message = f"🆘 Сообщение поддержки от пользователя:\n\n"
            admin_message += f"ID: {user_id}\n"
            admin_message += f"Имя: {user.first_name or 'Не указано'} {user.last_name or ''}\n"
            admin_message += f"Username: @{user.username or 'Не указан'}\n\n"
            admin_message += f"Сообщение:\n{message}"
            
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=admin_message
            )
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения администратору: {e}")
        
        await update.message.reply_text(MESSAGES['support_sent'])
    else:
        await update.message.reply_text(
            "Ошибка при отправке сообщения. Попробуйте позже."
        )
    
    # Возвращаемся в главное меню
    user_states[user_id] = BotStates.MAIN_MENU
    reply_markup = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)
    await update.message.reply_text(
        "Главное меню:",
        reply_markup=reply_markup
    )

async def show_purchase_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать меню покупки анализов"""
    keyboard = []
    for key, tariff in TARIFFS.items():
        keyboard.append([InlineKeyboardButton(
            tariff['label'], 
            callback_data=f"buy_{key}"
        )])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        MESSAGES['purchase_menu'],
        reply_markup=reply_markup
    )

async def handle_purchase_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback'ов покупки"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    if callback_data.startswith('buy_'):
        tariff_key = callback_data.replace('buy_', '')
        if tariff_key in TARIFFS:
            tariff = TARIFFS[tariff_key]
            
            # Создаем ссылку на оплату
            payment_info = payment_manager.create_payment_link(user_id, tariff_key)
            
            if payment_info:
                # Создаем клавиатуру с кнопками
                keyboard = [
                    [InlineKeyboardButton("💳 Оплатить", url=payment_info['payment_url'])],
                    [InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{payment_info['payment_id']}")],
                    [InlineKeyboardButton("❌ Отмена", callback_data="cancel_payment")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                message_text = f"""💳 Оплата тарифа: {tariff['label']}

💰 Сумма: {tariff['price']}₽
🎯 Кредитов: {tariff['credits']}

Нажмите "Оплатить" для перехода к оплате, затем "Проверить оплату" для подтверждения.

⚠️ Внимание: после оплаты обязательно нажмите "Проверить оплату" для начисления кредитов!"""
                
                await query.edit_message_text(
                    message_text,
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    "❌ Ошибка создания платежа. Попробуйте позже или обратитесь в поддержку."
                )
    
    elif callback_data.startswith('check_'):
        # Проверка статуса платежа
        payment_id = callback_data.replace('check_', '')
        
        await query.edit_message_text("🔄 Проверяю статус платежа...")
        
        # Проверяем статус платежа
        is_paid, operation_info = payment_manager.check_payment_status(payment_id)
        
        if is_paid:
            # Обрабатываем успешный платеж
            if payment_manager.process_successful_payment(payment_id):
                # Получаем информацию о платеже из метки
                payment_info = payment_manager.get_payment_info_from_label(payment_id)
                if payment_info and payment_info['tariff_key'] in TARIFFS:
                    tariff = TARIFFS[payment_info['tariff_key']]
                    credits_added = tariff['credits']
                    
                    current_credits = db.get_user_credits(user_id)
                    
                    success_message = f"""✅ Платеж успешно обработан!

💰 Начислено кредитов: {credits_added}
🎯 Текущий баланс: {current_credits} кредитов

Спасибо за покупку! Теперь вы можете использовать анализы."""
                    
                    await query.edit_message_text(success_message)
                    
                    # Отправляем уведомление администратору
                    try:
                        admin_message = f"💰 Новый платеж!\n\n"
                        admin_message += f"Пользователь: {user_id}\n"
                        admin_message += f"Тариф: {tariff['label']}\n"
                        admin_message += f"Сумма: {tariff['price']}₽\n"
                        admin_message += f"Кредитов: {credits_added}"
                        
                        await context.bot.send_message(
                            chat_id=ADMIN_USER_ID,
                            text=admin_message
                        )
                    except Exception as e:
                        logger.error(f"Ошибка отправки уведомления администратору: {e}")
                else:
                    await query.edit_message_text("✅ Платеж обработан, но возникла ошибка при начислении кредитов. Обратитесь в поддержку.")
            else:
                await query.edit_message_text("❌ Ошибка обработки платежа. Обратитесь в поддержку.")
        else:
            # Платеж еще не прошел
            keyboard = [
                [InlineKeyboardButton("🔄 Проверить еще раз", callback_data=f"check_{payment_id}")],
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel_payment")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "⏳ Платеж еще не поступил.\n\nПожалуйста, завершите оплату и нажмите 'Проверить еще раз'.",
                reply_markup=reply_markup
            )
    
    elif callback_data == "cancel_payment":
        await query.edit_message_text("❌ Оплата отменена.")

async def check_payments_periodically():
    """Периодическая проверка платежей (можно запускать в фоне)"""
    try:
        processed = payment_manager.check_pending_payments()
        if processed:
            logger.info(f"Автоматически обработано {len(processed)} платежей")
    except Exception as e:
        logger.error(f"Ошибка автоматической проверки платежей: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик сообщений"""
    user_id = update.effective_user.id
    current_state = user_states.get(user_id, BotStates.MAIN_MENU)
    
    if current_state == BotStates.MAIN_MENU:
        await handle_main_menu(update, context)
    elif current_state == BotStates.ROLE_SELECTION:
        await handle_role_selection(update, context)
    elif current_state == BotStates.WAITING_FOR_TEXT:
        await handle_text_analysis(update, context)
    elif current_state == BotStates.WAITING_FOR_SUPPORT_MESSAGE:
        await handle_support_message(update, context)

def main():
    """Основная функция запуска бота"""
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_purchase_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("Запуск бота...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

