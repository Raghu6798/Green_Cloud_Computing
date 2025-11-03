FROM python:3.12-slim-bookworm
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY webhook.py .
EXPOSE 8443
CMD ["python", "webhook.py"]