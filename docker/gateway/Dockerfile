FROM docker:27-cli

RUN apk add --no-cache bash curl git python3 py3-pip

WORKDIR /srv/talking-head-runtime

COPY pyproject.toml README.md ./
COPY src ./src
COPY deploy ./deploy
COPY docker ./docker
COPY weights ./weights

RUN pip3 install --no-cache-dir .

CMD ["uvicorn", "talking_head_runtime.app:app", "--host", "0.0.0.0", "--port", "8000"]
