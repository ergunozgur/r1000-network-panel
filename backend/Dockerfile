FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    modemmanager \
    network-manager \
    procps \
    nftables \
    samba-common-bin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts/service-lan-ra.py /usr/local/bin/service-lan-ra.py
COPY scripts/service-lan-inet-on.sh /usr/local/bin/service-lan-inet-on.sh
COPY scripts/service-lan-inet-off.sh /usr/local/bin/service-lan-inet-off.sh
RUN chmod +x /usr/local/bin/service-lan-ra.py /usr/local/bin/service-lan-inet-on.sh /usr/local/bin/service-lan-inet-off.sh

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
