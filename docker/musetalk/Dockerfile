FROM nvidia/cuda:11.7.1-cudnn8-devel-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG PYTHON_VERSION=3.10.9
ARG MUSE_TALK_REF=main

RUN apt-get update             && apt-get install -y --no-install-recommends                 build-essential                 ca-certificates                 curl                 ffmpeg                 git                 libbz2-dev                 libffi-dev                 libglib2.0-0                 libgl1                 liblzma-dev                 libncursesw5-dev                 libreadline-dev                 libsqlite3-dev                 libssl-dev                 llvm                 tk-dev                 wget                 xz-utils                 zlib1g-dev             && rm -rf /var/lib/apt/lists/*

ENV PYENV_ROOT=/opt/pyenv
ENV PATH=/opt/pyenv/bin:/opt/pyenv/shims:$PATH

RUN curl https://pyenv.run | bash
RUN pyenv install ${PYTHON_VERSION} && pyenv global ${PYTHON_VERSION}

RUN git clone --depth 1 --branch ${MUSE_TALK_REF} https://github.com/TMElyralab/MuseTalk.git /opt/musetalk
WORKDIR /opt/musetalk

RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -U openmim fastapi httpx huggingface_hub gdown python-multipart uvicorn[standard]
RUN mim install mmengine && mim install "mmcv==2.0.1" && mim install "mmdet==3.1.0" && mim install "mmpose==1.1.0"

RUN mkdir -p /srv/adapter
RUN curl -L https://huggingface.co/marcosremar2/MuseTalk/resolve/main/musetalk_api_server.py -o /srv/adapter/musetalk_api_server.py
COPY docker/musetalk/serve.py /srv/adapter/serve.py

RUN rm -rf /opt/musetalk/models /opt/musetalk/cache             && ln -s /models /opt/musetalk/models             && ln -s /cache /opt/musetalk/cache

ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
ENV HF_HOME=/cache/hf
ENV TORCH_HOME=/cache/torch
ENV XDG_CACHE_HOME=/cache/xdg
ENV PYTHONPATH=/opt/musetalk:/srv/adapter

WORKDIR /srv/adapter

CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000"]
