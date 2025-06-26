FROM python:3.11-slim

WORKDIR /app

# Спочатку копіюємо тільки requirements.txt для кешування шарів
COPY requirements.txt /app/

# Встановлюємо залежності
RUN pip install --no-cache-dir -r requirements.txt

# Потім копіюємо весь проєкт
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
