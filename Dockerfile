# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.13
ARG PYTHON_IMAGE_TAG=python:${PYTHON_VERSION}-slim
ARG UID=1000
ARG USERNAME=agentic_rag_vinicius_turani
ARG VIRTUAL_ENV=/home/${USERNAME}/.venv

FROM ${PYTHON_IMAGE_TAG} AS base
ARG USERNAME
ARG VIRTUAL_ENV
ARG UID

ENV \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=${VIRTUAL_ENV} \
    PATH="${VIRTUAL_ENV}/bin:${PATH}" \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# deps de sistema (inclui curl pro instalador do uv)
RUN adduser --disabled-password --gecos '' --uid ${UID} ${USERNAME} \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    ca-certificates curl git \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-por tesseract-ocr-spa \
    libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

USER ${USERNAME}

# instala uv (binário em ~/.cargo/bin/uv)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"
# evita hardlinks/symlinks problemáticos em overlayfs
ENV UV_LINK_MODE=copy

# diretório de projeto dedicado (sem varrer /)
WORKDIR /project

# ---------- Build dev com uv ----------
FROM base AS build-development

# copie manifesto + lock + código
COPY --chown=${USERNAME}:${USERNAME} ./pyproject.toml /project/pyproject.toml
COPY --chown=${USERNAME}:${USERNAME} ./uv.lock        /project/uv.lock
COPY --chown=${USERNAME}:${USERNAME} ./app            /project/app
COPY --chown=${USERNAME}:${USERNAME} ./resources /project/resources


# cria/atualiza a venv em /project/.venv e instala deps + o próprio projeto (editable)
RUN uv sync --frozen --no-dev --project /project

# instala debugpy NA MESMA VENV
RUN uv pip install --python /project/.venv/bin/python --system debugpy

# ---------- Runtime local ----------
FROM base AS local
COPY --from=build-development --chown=${USERNAME}:${USERNAME} /project /project

# garanta que usamos a venv do projeto por padrão
ENV PATH="/project/.venv/bin:${PATH}"


# ---------- no debug ----------
FROM local AS no-debug
WORKDIR /project
ENV TERM=xterm-256color
EXPOSE 5678
CMD ["python", "-X", "frozen_modules=off", "-m", "app"]


# ---------- Debug ----------
FROM local AS debug
WORKDIR /project
ENV TERM=xterm-256color
EXPOSE 5678
CMD ["python", "-X", "frozen_modules=off", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "-m", "app"]

