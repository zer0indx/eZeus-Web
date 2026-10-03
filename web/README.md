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

The start page shows the game's main menu painting and Zeus font. They come
from the game files, so they are not in git; copy them into `web/assets` once
(the build puts them next to the page):

```bash
python web/extract_assets.py "/path/to/Zeus and Poseidon/eZeus-0.8.2-beta"
```

Without them the page falls back to a drawn landscape and a serif font.

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

## Client and server folders

`make_client.py` builds two folders that can be kept apart:

```bash
python web/make_client.py "/path/to/Zeus and Poseidon" --client "/path/to/eZeus Web Client" --server "/path/to/eZeus Server"
```

- The client holds only the game files eZeus needs (~630 MB). It is the
  folder to pick with "Choose game folder" on the start page.
- The server holds the web build, the server and `start.bat`, which (with
  Python 3) starts it on port 8765 and opens the game.

Running the script again updates the folders, copying only changed files.
The client comes from your own copy of the game, so keep it to yourself.

## Self-hosting

`web/server.py` turns the build into a small private service: the game behind
a sign-in, saves kept on the server, and optionally the game files too. It is
packaged as a Docker image (`Dockerfile`, `docker-compose.yml`); the image has
no game files in it.

### What you need

- Docker, or any stack manager that takes a compose file.
- A reverse proxy with HTTPS in front of the container. Browsers only allow
  the features the game needs (threads, storage) on `https://` or `localhost`,
  so plain `http://server:8080` from another machine will not work. The proxy
  should pass `X-Forwarded-For` and `X-Forwarded-Proto`; the container sends
  the required `Cross-Origin-*` headers itself.
- Your own copy of Zeus and Poseidon with an eZeus release folder inside.

### Start

```bash
cp .env.example .env    # set EZEUS_PASSWORD, at least 12 characters
docker compose up -d
```

or paste `docker-compose.yml` into your stack manager and set the same
variables there. Then point the reverse proxy at port 8080 and open the site.

| Variable | Meaning |
|---|---|
| `EZEUS_USER` | Sign-in name (default `zeus`) |
| `EZEUS_PASSWORD` | Password, at least 12 characters. Or `EZEUS_PASSWORD_HASH`, made with `docker run --rm -it ghcr.io/zer0indx/ezeus-web python /app/server.py hash-password` |
| `EZEUS_GAME_SOURCE` | `server` or `local`, see below (default `local`) |
| `EZEUS_GAME_PATH` | Host folder mounted at `/game` (compose only) |
| `EZEUS_HTTP_PORT` | Host port (compose only, default 8080) |
| `EZEUS_SESSION_DAYS` | How long a sign-in lasts (default 30) |
| `EZEUS_TRUST_PROXY` | `1` (default) takes the client address and scheme from the proxy headers; set `0` if nothing sits in front |

The container runs as user 1000. If you mount host folders instead of the
named volume, make `/data` writable and `/game` readable for that user, or set
`user:` in the compose file.

### Game files: two modes

- `EZEUS_GAME_SOURCE=server`: mount your Zeus and Poseidon folder at `/game`
  (read-only). After signing in, each browser copies the files it needs
  (~630 MB) into its own storage, once, and again only for files that change.
  Nothing has to be chosen in the browser, and the start page shows the
  game's own art, taken from that folder.
- `EZEUS_GAME_SOURCE=local`: the server has no game files. Each browser picks
  a Zeus and Poseidon folder on its own computer, as in the standalone build.
  To have the game's art on the start page, put `menu.jpg` and `Zeus.ttf`
  (made by `web/extract_assets.py`) into `assets` inside the data volume.

### Saves

Saves are stored in the data volume (`/data/saves`) and synced with the
browser: on opening the page, right after the game writes a save, and every
20 seconds. Start a city on one computer and continue on another.

- If a save was changed in two places, the newer one wins; the other is kept
  as an older version.
- The server keeps the last 5 versions of every save in `/data/saves-history`
  and moves deleted saves to `/data/saves-trash` for 30 days, so a mistake in
  one browser does not lose anything.
- While the game runs it only sends its own saves. If another browser changed
  them meanwhile, the game says so; reload the page to get them.
- "Download saves" / "Upload saves" still work as a manual backup.

Back up the data volume to back up the saves.

### Access

Everything except the sign-in page needs a session: the game, the game files
and the API. There is one account and no default password.

- Five wrong passwords lock an address out for 30 seconds, doubling each time
  up to an hour. Sign-ins and failures are written to the container log with
  the client address.
- Sessions are signed cookies (`HttpOnly`, `SameSite=Strict`, `Secure` behind
  HTTPS). The signing key is created in the data volume on first start;
  deleting `/data/session-secret` and restarting signs everyone out.
- The game files are yours and copyrighted: keep the site private. Reaching it
  over a VPN is safer than exposing it to the internet.

### Building the image yourself

```bash
docker build -t ezeus-web .
```

The GitHub workflow in `.github/workflows/docker.yml` does the same for
version tags and publishes `ghcr.io/zer0indx/ezeus-web`.

Without Docker: build the web version as above, then

```bash
EZEUS_PASSWORD=... EZEUS_APP_DIR=build-web EZEUS_DATA_DIR=./data python web/server.py
```

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
