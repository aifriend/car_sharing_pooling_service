FROM python:3.7-slim-buster

ENV PYTHONUNBUFFERED=1

RUN set -ex \
    && buildDeps=" \
       build-essential \
       libpq-dev \
    " \
    apt-get update -qq && \
    apt-get install -y $buildDeps $deps --no-install-recommends \
    build-essential wget openssh-client graphviz-dev pkg-config \
    git-core openssl libssl-dev libffi6 libffi-dev libpng-dev curl vim && \
    apt-get purge -y --auto-remove $buildDeps $(! command -v gpg > /dev/null || echo 'gnupg dirmngr') && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    mkdir /app/

COPY service/ /app/

RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt --no-cache-dir

WORKDIR /app

EXPOSE 9091/tcp

CMD ["python", "manage.py"]
