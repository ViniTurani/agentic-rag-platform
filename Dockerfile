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
  VIRTUAL_ENV=${VIRTUAL_ENV} \
  PATH="${VIRTUAL_ENV}/bin:${PATH}"


# Create non-root user and install minimal tools
RUN adduser --disabled-password --gecos '' --uid ${UID} ${USERNAME} \
  && apt-get update \
  && apt-get install -y --no-install-recommends git \
  && rm -rf /var/lib/apt/lists/*
USER ${USERNAME}
WORKDIR /app

# Build dev virtualenv with project and debugpy
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

# Debug
FROM local AS debug
WORKDIR /app
EXPOSE 5678
CMD ["python", "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client", "-m", "app"]
