# Dockerfile
FROM python:3.12.10-slim

LABEL owner="StReloK-45"
LABEL description="Messenger-MIN Server"

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости 
# COPY server/requirements.txt . 2>/dev/null || true
# RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true

# Копируем серверную часть
COPY ../server/ .

# Создаём папку для данных
RUN mkdir -p /app/data /app/data/received_files

# Открываем порты
EXPOSE 5555 5556

CMD ['python', 'server/main.py']