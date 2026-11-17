FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY run.py .

ENV DB_PATH=/data/salone.db \
    TZ_NAME=Europe/Rome

CMD ["python", "-u", "run.py"]
