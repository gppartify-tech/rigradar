# One image for the API, the Celery worker and Celery beat.
# The official Playwright image already contains Chromium and all its system libraries,
# and its version matches `playwright==1.65.2` in requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.65.2-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1

WORKDIR /app
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

COPY . .
RUN mkdir -p /app/uploads && chown -R pwuser:pwuser /app
USER pwuser

EXPOSE 8000
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
