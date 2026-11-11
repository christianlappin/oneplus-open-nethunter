FROM --platform=linux/amd64 debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential flex bison libelf-dev libssl-dev libtinfo5 \
    zlib1g libxml2 bc python3 xz-utils rsync ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
