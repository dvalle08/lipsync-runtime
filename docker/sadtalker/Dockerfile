FROM nvidia/cuda:11.7.1-cudnn8-devel-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_VERSION=3.10.9
ARG SADTALKER_REF=main

RUN apt-get update             && apt-get install -y --no-install-recommends                 build-essential                 ca-certificates                 curl                 ffmpeg                 git                 libbz2-dev                 libffi-dev                 libglib2.0-0                 libgl1                 liblzma-dev                 libncursesw5-dev                 libreadline-dev                 libsqlite3-dev                 libssl-dev                 llvm                 tk-dev                 unzip                 wget                 xz-utils                 zlib1g-dev             && rm -rf /var/lib/apt/lists/*

ENV PYENV_ROOT=/opt/pyenv
ENV PATH=/opt/pyenv/bin:/opt/pyenv/shims:$PATH

RUN curl https://pyenv.run | bash
RUN pyenv install ${PYTHON_VERSION} && pyenv global ${PYTHON_VERSION}

RUN git clone --depth 1 --branch ${SADTALKER_REF} https://github.com/OpenTalker/SadTalker.git /opt/SadTalker
WORKDIR /opt/SadTalker

RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir torch==1.12.1+cu113 torchvision==0.13.1+cu113 torchaudio==0.12.1 --extra-index-url https://download.pytorch.org/whl/cu113
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi httpx python-multipart uvicorn[standard]

RUN mkdir -p /srv/adapter /models/checkpoints /models/gfpgan/weights /opt/SadTalker/gfpgan
RUN rm -rf /opt/SadTalker/checkpoints             && ln -s /models/checkpoints /opt/SadTalker/checkpoints             && ln -s /models/gfpgan/weights /opt/SadTalker/gfpgan/weights

COPY docker/sadtalker/serve.py /srv/adapter/serve.py

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
ENV TORCH_HOME=/cache/torch
ENV XDG_CACHE_HOME=/cache/xdg
ENV PYTHONPATH=/opt/SadTalker

WORKDIR /srv/adapter

CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000"]
