# Используем официальный Python образ
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY . .

# Создаем директорию для базы данных
RUN mkdir -p /app/data

# Устанавливаем переменную окружения для базы данных
ENV DATABASE_PATH=/app/data/bot.db

# Открываем порт для Flask (если понадобится)
EXPOSE 5000

# Команда запуска бота
CMD ["python", "bot.py"]

