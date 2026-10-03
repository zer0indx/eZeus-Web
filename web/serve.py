"""Serves the eZeus web build with the headers WebAssembly threads need.

Usage: python web/serve.py [build_dir] [port] [--game-dir PATH]

With --game-dir the page can import the game files straight from this
server (GET /game-manifest.json and /game/<path>) instead of asking the
player to pick the folder.
"""
import argparse
import functools
import http.server
import json
import os
import urllib.parse


class Handler(http.server.SimpleHTTPRequestHandler):
    game_dir = None

    def end_headers(self):
        # SharedArrayBuffer (pthreads) requires cross-origin isolation.
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def translate_path(self, path):
        rel = urllib.parse.unquote(urllib.parse.urlsplit(path).path)
        if self.game_dir and rel.startswith("/game/"):
            full = os.path.realpath(os.path.join(self.game_dir, rel[len("/game/"):]))
            if full.startswith(os.path.realpath(self.game_dir) + os.sep):
                return full
            return os.path.join(self.game_dir, "__forbidden__")
        return super().translate_path(path)

    def do_GET(self):
        if urllib.parse.urlsplit(self.path).path == "/game-manifest.json":
            if not self.game_dir:
                self.send_error(404)
                return
            files = []
            for root, dirs, names in os.walk(self.game_dir):
                # Skip hidden folders and source checkouts (e.g. this repo).
                dirs[:] = [d for d in dirs if not d.startswith(".") and
                           not os.path.exists(os.path.join(root, d, ".git"))]
                for name in names:
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, self.game_dir).replace(os.sep, "/")
                    files.append({"path": rel, "size": os.path.getsize(full)})
            body = json.dumps({"files": files}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


Handler.extensions_map[".wasm"] = "application/wasm"

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("build_dir", nargs="?", default="build-web")
    parser.add_argument("port", nargs="?", type=int, default=8080)
    parser.add_argument("--game-dir")
    args = parser.parse_args()
    Handler.game_dir = os.path.abspath(args.game_dir) if args.game_dir else None
    handler = functools.partial(Handler, directory=args.build_dir)
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"eZeus: http://localhost:{args.port}/eZeus.html", flush=True)
        httpd.serve_forever()
