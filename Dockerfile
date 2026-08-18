FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Reconstruct app/ if the GitHub browser upload flattened the source tree.
RUN if [ ! -d app ]; then \
      mkdir app && \
      for f in *.py; do \
        [ -f "$f" ] && mv "$f" app/; \
      done && \
      touch app/__init__.py; \
    fi

RUN python -m app.import_catalog

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
