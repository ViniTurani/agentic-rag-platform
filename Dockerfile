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
  # Tesseract tessdata path (default for Debian packages)
  TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata

# Create non-root user and install system deps (incl. Tesseract + langs)
RUN adduser --disabled-password --gecos '' --uid ${UID} ${USERNAME} \
  && apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
     git \
     tesseract-ocr \
     tesseract-ocr-eng \
     tesseract-ocr-por \
     tesseract-ocr-spa \
     # runtime libs used by PyMuPDF/Pillow in many setups
     libglib2.0-0 \
     libgl1 \
  && rm -rf /var/lib/apt/lists/*

USER ${USERNAME}
WORKDIR /app


# Build dev virtualenv
FROM base AS build-development
RUN python -m venv "${VIRTUAL_ENV}" \
  && "${VIRTUAL_ENV}/bin/python" -m pip install --upgrade pip setuptools wheel
COPY --chown=${USERNAME}:${USERNAME} ./pyproject.toml ./pyproject.toml
COPY --chown=${USERNAME}:${USERNAME} ./app ./app
RUN "${VIRTUAL_ENV}/bin/python" -m pip install -e . \
  && "${VIRTUAL_ENV}/bin/python" -m pip install debugpy

# Local runtime image
FROM base AS local
COPY --from=build-development --chown=${USERNAME}:${USERNAME} ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --chown=${USERNAME}:${USERNAME} ./pyproject.toml ./pyproject.toml
COPY --chown=${USERNAME}:${USERNAME} ./app ./app

# Debug image
FROM local AS debug
WORKDIR /app
EXPOSE 5678
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "-m", "app"]