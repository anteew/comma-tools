# syntax=docker/dockerfile:1

# Stage 1: Fetch OpenPilot vendor dependencies
FROM python:3.12-slim as vendor-fetch

# OpenPilot version configuration (easy to update)
ARG OPENPILOT_VERSION=v0.10.0
ARG OPENPILOT_COMMIT=c085b8af19438956c1559

# Install minimal git for sparse checkout
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Use sparse checkout to fetch only required OpenPilot components
# Note: Cannot use --depth=1 because we need to checkout a specific commit
# The filter=blob:none still minimizes download by skipping file contents until checkout
# Include common for shared utilities and initialize opendbc_repo for car.capnp
RUN git clone --no-checkout --filter=blob:none \
        https://github.com/commaai/openpilot /tmp/openpilot && \
    cd /tmp/openpilot && \
    git sparse-checkout init --cone && \
    git sparse-checkout set tools/lib cereal common system && \
    git checkout ${OPENPILOT_COMMIT} && \
    git submodule update --init --depth=1 opendbc_repo

# Stage 2: Main application build
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /comma-tools

# Copy vendored OpenPilot dependencies from fetch stage
# Copy entire tools/lib directory as logreader might have dependencies
COPY --from=vendor-fetch /tmp/openpilot/tools/lib /comma-tools/vendor/openpilot/tools/lib/
COPY --from=vendor-fetch /tmp/openpilot/cereal /comma-tools/vendor/openpilot/cereal/
COPY --from=vendor-fetch /tmp/openpilot/common /comma-tools/vendor/openpilot/common/
COPY --from=vendor-fetch /tmp/openpilot/system /comma-tools/vendor/openpilot/system/
COPY --from=vendor-fetch /tmp/openpilot/opendbc_repo /comma-tools/vendor/openpilot/opendbc_repo/

# Create __init__.py files for proper Python module structure
RUN touch /comma-tools/vendor/__init__.py && \
    touch /comma-tools/vendor/openpilot/__init__.py && \
    touch /comma-tools/vendor/openpilot/tools/__init__.py && \
    touch /comma-tools/vendor/openpilot/tools/lib/__init__.py && \
    touch /comma-tools/vendor/openpilot/common/__init__.py && \
    touch /comma-tools/vendor/openpilot/system/__init__.py && \
    touch /comma-tools/vendor/openpilot/system/hardware/__init__.py

# Copy application code
COPY . /comma-tools

# Install application and all optional dependency groups
RUN pip install --no-cache-dir -e ".[api,client,connect]"

RUN install -m 0755 docker/startup.py /usr/local/bin/comma-tools-startup

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/comma-tools-startup"]
