FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter.py .
COPY channel_map.py .

EXPOSE 8501

CMD ["python", "-u", "exporter.py"]
