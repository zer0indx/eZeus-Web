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
About 630 MB is imported: the contents of `DATA` (eZeus only checks that the
folder exists), installers, Windows binaries, manuals and videos are skipped.

Saves stay in the browser. "Download saves" on the start page packs them into
a ZIP; "Upload saves" adds the saves from such a ZIP. Re-importing the game
folder never replaces saves already in the browser.

## Standalone client

`make_client.py` builds a folder with the web build, the server, `start.bat`
and only the game files eZeus needs:

```bash
python web/make_client.py "/path/to/Zeus and Poseidon" "/path/to/eZeus Web"
```

Double-clicking `start.bat` in it (Python 3 required) starts the server on
port 8765 and opens the game; the first launch imports the files into the
browser by itself. Running the script again updates the folder and copies
only changed files. The game files come from your own copy of the game, so
keep the client to yourself.

## How the port works

- `web/emscripten.cmake`: SDL2 libraries come from Emscripten ports, libnoise is
  built from source, WASMFS + pthreads are enabled.
- `main.cpp` mounts OPFS at `/zeus`; `eGameDir::exeDir()` returns
  `/zeus/eZeus/Bin/`, so the desktop directory layout is kept.
- `eMainWindow::exec()` runs one frame per `emscripten_set_main_loop` tick
  instead of a blocking `while` loop.
- `web/shell.html` is the page: it imports the game files into OPFS and starts
  the game.
- Every file operation on OPFS is proxied to another thread, so files are read
  in large blocks: `QFile` (pak files) and saves are read into memory at once,
  texture data with a single `fread`.
- SDL feeds audio from the main thread. Around work that blocks it (reading an
  adventure, starting an episode, loading screens) the game calls
  `eMainWindow::runBusy`/`sSetBusy`, which suspend the AudioContext and show a
  busy indicator, instead of letting the browser loop the last audio buffer.

## Window size and fullscreen

The resolution follows the browser window (at least 800x600, and no narrower
than 4:3). Widgets are laid out once, so the resolution only changes while the
main menu is shown; on other screens the page scales the canvas to fit the
window, keeping its aspect ratio. "Full screen" in the game options switches
the browser to fullscreen on the next click or key press. The resolution list
in the options has no lasting effect: the main menu always refits the window.
