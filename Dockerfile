# Базовий образ з Python
FROM python:3.11-slim

# Встановлюємо змінну оточення для роботи з FastAPI
ENV PYTHONUNBUFFERED=1

# Робоча директорія в контейнері
WORKDIR /app

# Копіюємо requirements.txt і встановлюємо залежності
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копіюємо всі файли проєкту
COPY . .

# Відкриваємо порт (Fly.io сам проб'є порт)
EXPOSE 8000

# Команда запуску FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
