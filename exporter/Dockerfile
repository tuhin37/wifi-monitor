FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    iw wireless-tools net-tools iproute2 wpasupplicant isc-dhcp-client \
    nmcli network-manager \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py database.py scanner.py wifi_connector.py speedtest.py metrics.py scheduler.py main.py ./

EXPOSE 8501

CMD ["python", "-u", "-m", "main"]
