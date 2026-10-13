FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
ENV SERVER_VERSION=v2.0-GHAS-PQC-HARDENED
ENV PORT=8080
ENV HOST=0.0.0.0
CMD ["python", "server.py"]
