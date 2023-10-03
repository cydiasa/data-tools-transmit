FROM python:3.11.5-alpine3.18
WORKDIR /app


RUN apk update && \
    apk add make automake gcc g++ subversion python3-dev && \
    pip install salsa20 influxdb-client

RUN adduser -D nonroot \
        && mkdir -p /etc/sudoers.d \
        && echo "nonroot ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/nonroot \
        && chmod 0440 /etc/sudoers.d/nonroot
        
COPY --chown=nonroot:nonroot ./ /app

CMD ["python3", "-u", "/app/src/main.py"]