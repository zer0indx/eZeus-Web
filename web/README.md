# eZeus in the browser (WebAssembly)

eZeus can be compiled with [Emscripten](https://emscripten.org) and played in a
modern browser (Chrome, Edge, Firefox, Safari). The game files are not part of
the build: on first launch the player picks their own `Zeus and Poseidon`
folder and the files are copied into the browser's Origin Private File System
(OPFS). Saves and settings are stored there too.

## Build

```bash
git clone https://github.com/emscripten-core/emsdk.git
cd emsdk && ./emsdk install latest && ./emsdk activate latest
source ./emsdk_env.sh
cd <eZeus>
emcmake cmake -S . -B build-web -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-web
```

The output is `build-web/eZeus.html`, `eZeus.js` and `eZeus.wasm`.

## Run

The build uses WebAssembly threads, so the page has to be served with
`Cross-Origin-Opener-Policy: same-origin` and
`Cross-Origin-Embedder-Policy: require-corp`. `serve.py` does that:

```bash
python web/serve.py build-web 8080 --game-dir "/path/to/Zeus and Poseidon"
```

Open http://localhost:8080/eZeus.html. With `--game-dir` the page offers
"import from local server", which copies the game files without a folder
picker. Without it, use "choose game folder".

The game folder must contain the original game and the eZeus release folder
(`eZeus-*` with `interface.e`, `i30.e`, ...), as for the desktop build.

## How the port works

- `web/emscripten.cmake`: SDL2 libraries come from Emscripten ports, libnoise is
  built from source, WASMFS + pthreads are enabled.
- `main.cpp` mounts OPFS at `/zeus`; `eGameDir::exeDir()` returns
  `/zeus/eZeus/Bin/`, so the desktop directory layout is kept.
- `eMainWindow::exec()` runs one frame per `emscripten_set_main_loop` tick
  instead of a blocking `while` loop.
- `web/shell.html` is the page: it imports the game files into OPFS and starts
  the game.
