FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 TRUEPILOT_DATA_DIR=/data TRUEPILOT_PORT=8080
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY web ./web
VOLUME /data
EXPOSE 8080
CMD ["python", "-m", "app"]
