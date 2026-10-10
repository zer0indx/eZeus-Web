# Self-hosted eZeus Web: the game compiled to WebAssembly plus web/server.py.
# It contains no game files; see web/README.md.

ARG EMSDK_VERSION=6.0.11

# The WebAssembly build is the same for every target platform.
FROM --platform=$BUILDPLATFORM emscripten/emsdk:${EMSDK_VERSION} AS build
WORKDIR /src
COPY . .
RUN emcmake cmake -S . -B build-web -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build-web -j "$(nproc)"

FROM python:3.13-alpine
RUN adduser -D -u 1000 ezeus \
 && mkdir /data /game \
 && chown ezeus:ezeus /data
COPY --from=build /src/build-web/eZeus.html /src/build-web/eZeus.js \
     /src/build-web/eZeus.wasm /app/web/
COPY web/static /app/web/static
COPY web/server.py web/gamefiles.py web/login.html /app/
ENV EZEUS_APP_DIR=/app/web \
    EZEUS_DATA_DIR=/data \
    EZEUS_GAME_DIR=/game \
    EZEUS_PORT=8080 \
    PYTHONUNBUFFERED=1
USER ezeus
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
CMD ["python", "/app/server.py"]
