"""Builds a self-contained eZeus web client folder.

Usage: python web/make_client.py <Zeus and Poseidon folder> <output folder>
                                 [--build-dir build-web]

The output holds the web build, a local server, start.bat and only the game
files eZeus needs (about 630 MB). On first launch the page imports them into
the browser automatically. Running it again updates the folder, copying only
changed files.

The game files come from your own copy of the game; keep the client for
yourself and do not publish it.
"""
import argparse
import os
import shutil
import sys

# Keep in sync with targetPath() in shell.html.
SKIP_EXT = {"exe", "dll", "pdf", "zip", "lnk", "ico", "asi", "m3d", "msg",
            "hashdb", "bik", "eng", "dat", "info", "inf", "ini"}
SKIP_DIRS = {"binks"}
# eZeus only checks that these exist; their contents are never read.
EMPTY_DIRS = ["DATA"]
APP_FILES = ["eZeus.html", "eZeus.js", "eZeus.wasm"]

START_BAT = r"""@echo off
rem Starts the local eZeus server and opens the game in the browser.
cd /d "%~dp0"
set PY=
where python >nul 2>nul && set PY=python
if not defined PY where py >nul 2>nul && set PY=py
if not defined PY (
    echo Python 3 is required: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo eZeus runs at http://localhost:%PORT%/ - keep this window open while playing.
%PY% server.py app %PORT% --game-dir game --open
pause
""".replace("%PORT%", "8765")

README = """eZeus Web client
================

Zeus: Master of Olympus (eZeus) running in the browser.

Start: double-click start.bat (needs Python 3). It starts a local server at
http://localhost:8765/ and opens the game. Keep the window open while playing.

The first launch copies the game files (~630 MB) into the browser's storage;
later launches start right away. Saves are kept in the browser: use
"Download saves" / "Upload saves" on the start page to back them up.

Use a recent Chrome, Edge or Firefox.

The game files come from your own copy of Zeus and Poseidon; do not share
this folder publicly.
"""


def find_ezeus_dir(game_dir):
    for name in os.listdir(game_dir):
        path = os.path.join(game_dir, name)
        if (name.lower().startswith("ezeus") and os.path.isdir(path)
                and os.path.isfile(os.path.join(path, "interface.e"))):
            return name
    return None


def needed(rel_parts):
    """Whether a file (path parts relative to the game folder) is needed."""
    name = rel_parts[-1]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    dirs = [d.lower() for d in rel_parts[:-1]]
    if ext in SKIP_EXT or any(d in SKIP_DIRS for d in dirs):
        return False
    if dirs and dirs[0] in (d.lower() for d in EMPTY_DIRS):
        return False
    return True


def copy_if_changed(src, dst):
    if os.path.exists(dst):
        s, d = os.stat(src), os.stat(dst)
        if s.st_size == d.st_size and int(s.st_mtime) <= int(d.st_mtime):
            return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("game_dir")
    parser.add_argument("out_dir")
    parser.add_argument("--build-dir",
                        default=os.path.join(os.path.dirname(__file__), "..", "build-web"))
    args = parser.parse_args()

    game_dir = os.path.abspath(args.game_dir)
    out_dir = os.path.abspath(args.out_dir)
    build_dir = os.path.abspath(args.build_dir)
    web_dir = os.path.dirname(os.path.abspath(__file__))

    ezeus = find_ezeus_dir(game_dir)
    if not ezeus:
        sys.exit(f"No eZeus folder with interface.e found in {game_dir}")
    if not os.path.isdir(os.path.join(game_dir, "Audio", "Wavs")):
        sys.exit(f"{game_dir} does not look like a Zeus and Poseidon installation")
    for f in APP_FILES:
        if not os.path.isfile(os.path.join(build_dir, f)):
            sys.exit(f"{f} missing in {build_dir}; build the web version first")
    if out_dir == game_dir or out_dir.startswith(game_dir + os.sep):
        sys.exit("The output folder must be outside the game folder")

    app_out = os.path.join(out_dir, "app")
    game_out = os.path.join(out_dir, "game")
    for f in APP_FILES:
        copy_if_changed(os.path.join(build_dir, f), os.path.join(app_out, f))
    copy_if_changed(os.path.join(web_dir, "serve.py"), os.path.join(out_dir, "server.py"))
    with open(os.path.join(out_dir, "start.bat"), "w", newline="\r\n") as f:
        f.write(START_BAT)
    with open(os.path.join(out_dir, "README.txt"), "w", newline="\r\n") as f:
        f.write(README)

    wanted = set()
    copied = total = 0
    for root, dirs, files in os.walk(game_dir):
        rel_root = os.path.relpath(root, game_dir)
        if rel_root == ".":
            # Other eZeus folders (e.g. a source checkout) and hidden folders.
            dirs[:] = [d for d in dirs if not d.startswith(".") and
                       not (d.lower().startswith("ezeus") and d != ezeus)]
        for name in files:
            parts = [] if rel_root == "." else rel_root.split(os.sep)
            parts.append(name)
            if not needed(parts):
                continue
            if parts[0] == ezeus:
                parts[0] = "eZeus"
            src = os.path.join(root, name)
            dst = os.path.join(game_out, *parts)
            wanted.add(os.path.normcase(dst))
            total += os.path.getsize(src)
            if copy_if_changed(src, dst):
                copied += 1
    for d in EMPTY_DIRS + [os.path.join("eZeus", "Bin"), os.path.join("eZeus", "Save")]:
        os.makedirs(os.path.join(game_out, d), exist_ok=True)

    # Drop files that are no longer needed, e.g. after a rule change.
    removed = 0
    for root, _, files in os.walk(game_out):
        for name in files:
            path = os.path.join(root, name)
            if os.path.normcase(path) not in wanted:
                os.remove(path)
                removed += 1

    print(f"Client in {out_dir}")
    print(f"Game files: {len(wanted)} ({total / 2**20:.0f} MB), "
          f"copied {copied}, removed {removed}")
    print(f"Start it with {os.path.join(out_dir, 'start.bat')}")


if __name__ == "__main__":
    main()
