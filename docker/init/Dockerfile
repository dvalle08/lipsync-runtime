FROM python:3.11-slim

RUN apt-get update             && apt-get install -y --no-install-recommends ca-certificates curl git             && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/talking-head-runtime

RUN pip install --no-cache-dir gdown huggingface_hub

COPY docker/init/download_weights.py /srv/talking-head-runtime/docker/init/download_weights.py
COPY weights /srv/talking-head-runtime/weights

ENTRYPOINT ["python", "/srv/talking-head-runtime/docker/init/download_weights.py"]
