# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /comma-tools

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir ".[api,client]"

COPY . .

RUN install -m 0755 docker/startup.py /usr/local/bin/comma-tools-startup

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/comma-tools-startup"]
