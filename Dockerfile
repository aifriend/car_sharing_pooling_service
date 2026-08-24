FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && useradd --create-home --shell /usr/sbin/nologin app

COPY service/ /app/

USER app

EXPOSE 9091/tcp

CMD ["python", "manage.py"]
