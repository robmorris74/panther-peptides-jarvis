FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JARVIS3_DATA_DIR=/app/data JARVIS_COOKIE_SECURE=1
COPY jarvis3/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY jarvis3/app.py /app/app.py
RUN mkdir -p /app/data && python -m py_compile /app/app.py
EXPOSE 8000
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000"]
