"""Builds the eZeus web client and server folders.

Usage: python web/make_client.py <Zeus and Poseidon folder>
                                 [--client DIR] [--server DIR]
                                 [--build-dir build-web]

The client folder holds only the game files eZeus needs (about 630 MB); it
can be kept anywhere and is the folder to choose with "Choose game folder" on
the start page. The server folder holds the web build, the local server and
start.bat. Running the script again updates the folders, copying only
changed files.

The game files come from your own copy of the game; keep the client for
yourself and do not publish it.
"""
import argparse
import os
import shutil
import sys

from gamefiles import EMPTY_DIRS, find_ezeus_dir, walk_needed

APP_FILES = ["eZeus.html", "eZeus.js", "eZeus.wasm"]
PORT = 8765

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
%PY% server.py app %PORT% --open
pause
""".replace("%PORT%", str(PORT))

SERVER_README = f"""eZeus Web server
================

Runs Zeus: Master of Olympus (eZeus) in the browser.

Start: double-click start.bat (needs Python 3). It starts a local server at
http://localhost:{PORT}/ and opens the game. Keep the window open while
playing.

On the first launch click "Choose game folder" and pick the eZeus Web
Client folder; its files are copied into the browser's storage (~630 MB), so later
launches start right away. Saves are kept in the browser: use
"Download saves" / "Upload saves" on the start page to back them up.

Use a recent Chrome, Edge or Firefox.
"""

# Not README.txt: the game has its own Readme.txt and Windows ignores case.
CLIENT_README_NAME = "README-eZeus-Web-Client.txt"
CLIENT_README = """eZeus Web Client
=================

The game files eZeus needs, taken from your copy of Zeus and Poseidon.
Pick this folder with "Choose game folder" on the eZeus start page.

Do not share this folder publicly.
"""


def copy_if_changed(src, dst):
    if os.path.exists(dst):
        s, d = os.stat(src), os.stat(dst)
        if s.st_size == d.st_size and int(s.st_mtime) <= int(d.st_mtime):
            return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return True


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\r\n") as f:
        f.write(text)


def make_server(server_dir, build_dir, web_dir):
    for f in APP_FILES:
        if not os.path.isfile(os.path.join(build_dir, f)):
            sys.exit(f"{f} missing in {build_dir}; build the web version first")
    for f in APP_FILES:
        copy_if_changed(os.path.join(build_dir, f), os.path.join(server_dir, "app", f))
    copy_if_changed(os.path.join(web_dir, "serve.py"), os.path.join(server_dir, "server.py"))
    for folder in ("static", "assets"):
        source = os.path.join(web_dir, folder)
        if os.path.isdir(source):
            for name in os.listdir(source):
                copy_if_changed(os.path.join(source, name),
                                os.path.join(server_dir, "app", folder, name))
    write_text(os.path.join(server_dir, "start.bat"), START_BAT)
    write_text(os.path.join(server_dir, "README.txt"), SERVER_README)
    print(f"Server in {server_dir}; start it with start.bat")


def make_client(client_dir, game_dir):
    ezeus = find_ezeus_dir(game_dir)
    if not ezeus:
        sys.exit(f"No eZeus folder with interface.e found in {game_dir}")
    if not os.path.isdir(os.path.join(game_dir, "Audio", "Wavs")):
        sys.exit(f"{game_dir} does not look like a Zeus and Poseidon installation")

    wanted = {os.path.normcase(os.path.join(client_dir, CLIENT_README_NAME))}
    copied = total = 0
    for parts, src in walk_needed(game_dir):
        if parts[0] == ezeus:
            parts[0] = "eZeus"
        dst = os.path.join(client_dir, *parts)
        wanted.add(os.path.normcase(dst))
        total += os.path.getsize(src)
        if copy_if_changed(src, dst):
            copied += 1
    for d in EMPTY_DIRS + [os.path.join("eZeus", "Bin"), os.path.join("eZeus", "Save")]:
        os.makedirs(os.path.join(client_dir, d), exist_ok=True)
    write_text(os.path.join(client_dir, CLIENT_README_NAME), CLIENT_README)

    # Drop files that are no longer needed, e.g. after a rule change.
    removed = 0
    for root, _, files in os.walk(client_dir):
        for name in files:
            path = os.path.join(root, name)
            if os.path.normcase(path) not in wanted:
                os.remove(path)
                removed += 1
    print(f"Client in {client_dir}: {len(wanted) - 1} game files "
          f"({total / 2**20:.0f} MB), copied {copied}, removed {removed}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("game_dir")
    parser.add_argument("--client", help="folder for the game files")
    parser.add_argument("--server", help="folder for the web build and server")
    parser.add_argument("--build-dir",
                        default=os.path.join(os.path.dirname(__file__), "..", "build-web"))
    args = parser.parse_args()
    if not args.client and not args.server:
        parser.error("give --client, --server or both")

    game_dir = os.path.abspath(args.game_dir)
    web_dir = os.path.dirname(os.path.abspath(__file__))
    for out in (args.client, args.server):
        if out:
            out = os.path.abspath(out)
            if out == game_dir or out.startswith(game_dir + os.sep):
                sys.exit("Output folders must be outside the game folder")

    if args.server:
        make_server(os.path.abspath(args.server), os.path.abspath(args.build_dir), web_dir)
    if args.client:
        make_client(os.path.abspath(args.client), game_dir)


if __name__ == "__main__":
    main()
