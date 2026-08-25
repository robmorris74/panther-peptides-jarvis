FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 JARVIS3_DATA_DIR=/app/data JARVIS_COOKIE_SECURE=1
COPY jarvis3/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY jarvis3 /app/jarvis3
RUN mkdir -p /app/data && python -m py_compile /app/jarvis3/app.py /app/jarvis3/ops.py /app/jarvis3/operator.py /app/jarvis3/store.py /app/jarvis3/ui.py
EXPOSE 8000
CMD ["uvicorn","jarvis3.app:app","--host","0.0.0.0","--port","8000"]
