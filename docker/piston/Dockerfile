# ==============================================================================
# CODEGUARD / EXAMIIO — Self-Contained Piston Execution Engine
# Includes pre-installed, pre-configured runtimes: Python, C, C++, Java
# ==============================================================================

# Stage 1: Download, unpack, and prepare runtime packages
FROM alpine:latest AS package_downloader
RUN apk add --no-cache curl tar gzip bash

WORKDIR /piston/packages
RUN mkdir -p python/3.10.0 gcc/10.2.0 java/15.0.2 \
    && echo "Downloading Python package..." \
    && curl -sL https://github.com/engineer-man/piston/releases/download/pkgs/python-3.10.0.pkg.tar.gz | tar -xz -C python/3.10.0 \
    && echo "Downloading GCC (C/C++) package..." \
    && curl -sL https://github.com/engineer-man/piston/releases/download/pkgs/gcc-10.2.0.pkg.tar.gz | tar -xz -C gcc/10.2.0 \
    && echo "Downloading Java package..." \
    && curl -sL https://github.com/engineer-man/piston/releases/download/pkgs/java-15.0.2.pkg.tar.gz | tar -xz -C java/15.0.2 \
    && for d in /piston/packages/*/*; do \
         if [ -d "$d" ]; then \
           cd "$d" && \
           env -i bash -c "source environment; env" | grep -v -E '^(PWD|OLDPWD|_|SHLVL)=' > .env && \
           touch .ppman-installed; \
         fi; \
       done \
    && chmod -R 777 /piston/packages

# Stage 2: Final Piston Image
FROM ghcr.io/engineer-man/piston:latest

COPY --from=package_downloader --chown=piston:piston /piston/packages /piston/packages
COPY --chmod=755 docker/piston/docker-entrypoint.sh /piston_api/src/docker-entrypoint.sh

WORKDIR /piston_api

HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD node -e 'const req = require("http").get("http://127.0.0.1:2000/api/v2/runtimes", (res) => process.exit(res.statusCode === 200 ? 0 : 1)); req.on("error", () => process.exit(1)); req.setTimeout(4000, () => { req.destroy(); process.exit(1); });'
