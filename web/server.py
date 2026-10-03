"""Self-hosted eZeus Web server.

Serves the game behind a sign-in, optionally provides the game files, and
keeps the saves so they follow the player between browsers. It needs only the
Python standard library and expects to sit behind a reverse proxy that
terminates HTTPS (browsers require a secure context for the game).

Configuration (environment variables):
  EZEUS_USER            sign-in name (default "zeus")
  EZEUS_PASSWORD        password, at least 12 characters, or
  EZEUS_PASSWORD_HASH   a hash made by `python server.py hash-password`
  EZEUS_GAME_SOURCE     "server": game files are taken from EZEUS_GAME_DIR
                        "local" (default): each browser picks a game folder
  EZEUS_GAME_DIR        Zeus and Poseidon folder (default /game)
  EZEUS_DATA_DIR        saves, session secret, start page art (default /data)
  EZEUS_APP_DIR         folder with eZeus.html, eZeus.js, eZeus.wasm
  EZEUS_PORT            port to listen on (default 8080)
  EZEUS_SESSION_DAYS    how long a sign-in lasts (default 30)
  EZEUS_TRUST_PROXY     "1" (default): take the client address and scheme
                        from X-Forwarded-For / X-Forwarded-Proto
"""
import base64
import datetime
import email.utils
import hashlib
import hmac
import http.server
import json
import mimetypes
import os
import secrets
import shutil
import signal
import sys
import threading
import time
import urllib.parse

import gamefiles

VERSION = "1"
COOKIE = "ezeus_session"
MIN_PASSWORD_LENGTH = 12
MAX_SAVE_BYTES = 128 * 2**20
SAVE_VERSIONS_KEPT = 5
TRASH_DAYS = 30
SCRYPT = {"n": 2**15, "r": 8, "p": 1}

# The game is an Emscripten page: inline scripts, WebAssembly and workers.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'",
    "worker-src 'self' blob:",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
    "form-action 'self'",
])


def env(name, default=None):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


# --- Passwords and sessions -------------------------------------------------

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32,
                            maxmem=128 * 2**20, **SCRYPT)
    return "scrypt${n}${r}${p}${salt}${digest}".format(
        salt=base64.b64encode(salt).decode(),
        digest=base64.b64encode(digest).decode(), **SCRYPT)


def verify_password(password, stored):
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt)
        digest = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=salt, dklen=len(digest),
                                n=int(n), r=int(r), p=int(p), maxmem=128 * 2**20)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, digest)


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class Sessions:
    def __init__(self, secret, days):
        self.secret = secret
        self.lifetime = days * 86400

    def _sign(self, payload):
        return b64url(hmac.new(self.secret, payload.encode(), hashlib.sha256).digest())

    def issue(self, user):
        payload = b64url(json.dumps({"u": user, "e": int(time.time()) + self.lifetime}).encode())
        return payload + "." + self._sign(payload)

    def user(self, token):
        try:
            payload, signature = token.split(".")
            if not hmac.compare_digest(signature, self._sign(payload)):
                return None
            data = json.loads(b64url_decode(payload))
            if data["e"] < time.time():
                return None
            return data["u"]
        except (ValueError, KeyError, TypeError):
            return None


class LoginLimiter:
    """Locks an address out for a growing time after repeated failures."""
    FREE_ATTEMPTS = 5
    BASE_LOCK = 30
    MAX_LOCK = 3600
    FORGET_AFTER = 86400

    def __init__(self):
        self.lock = threading.Lock()
        self.entries = {}  # address -> [failures, locked_until, last_failure]

    def wait_time(self, address):
        with self.lock:
            entry = self.entries.get(address)
            return max(0, int(entry[1] - time.time()) + 1) if entry and entry[1] > time.time() else 0

    def failed(self, address):
        now = time.time()
        with self.lock:
            for key in [k for k, e in self.entries.items() if now - e[2] > self.FORGET_AFTER]:
                del self.entries[key]
            entry = self.entries.setdefault(address, [0, 0, now])
            entry[0] += 1
            entry[2] = now
            over = entry[0] - self.FREE_ATTEMPTS
            if over >= 0:
                entry[1] = now + min(self.MAX_LOCK, self.BASE_LOCK * 2**over)

    def succeeded(self, address):
        with self.lock:
            self.entries.pop(address, None)


# --- Saves ------------------------------------------------------------------

class SaveError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def save_parts(path):
    """Validates a save path ("Leader/name.ez") and returns its parts."""
    if len(path) > 400:
        raise SaveError(400, "path too long")
    parts = [p for p in path.split("/") if p != ""]
    if not parts or len(parts) > 4:
        raise SaveError(400, "bad path")
    for part in parts:
        if (part in (".", "..") or part.startswith(".") or len(part) > 120
                or any(c in part for c in '\\:\0*?"<>|') or part != part.strip()):
            raise SaveError(400, "bad path")
    return parts


class Saves:
    """Saves on disk, with previous versions and a trash instead of deletion."""

    def __init__(self, data_dir):
        self.root = os.path.join(data_dir, "saves")
        self.history = os.path.join(data_dir, "saves-history")
        self.trash = os.path.join(data_dir, "saves-trash")
        self.lock = threading.Lock()
        self.hashes = {}  # full path -> (size, mtime_ns, sha256)
        for d in (self.root, self.history, self.trash):
            os.makedirs(d, exist_ok=True)
        self._empty_old_trash()

    def _empty_old_trash(self):
        limit = time.time() - TRASH_DAYS * 86400
        for name in os.listdir(self.trash):
            path = os.path.join(self.trash, name)
            if os.path.getmtime(path) < limit:
                shutil.rmtree(path, ignore_errors=True)

    def _sha256(self, full):
        st = os.stat(full)
        cached = self.hashes.get(full)
        if cached and cached[0] == st.st_size and cached[1] == st.st_mtime_ns:
            return cached[2]
        digest = hashlib.sha256()
        with open(full, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        self.hashes[full] = (st.st_size, st.st_mtime_ns, digest.hexdigest())
        return digest.hexdigest()

    def list(self):
        entries = []
        with self.lock:
            for root, dirs, files in os.walk(self.root):
                dirs.sort()
                rel = os.path.relpath(root, self.root).replace(os.sep, "/")
                prefix = "" if rel == "." else rel + "/"
                if prefix:
                    entries.append({"path": prefix, "dir": True})
                for name in sorted(files):
                    full = os.path.join(root, name)
                    if name.endswith(".part"):
                        continue
                    st = os.stat(full)
                    entries.append({"path": prefix + name, "size": st.st_size,
                                    "mtime": st.st_mtime_ns // 10**6,
                                    "sha256": self._sha256(full)})
        return entries

    def file(self, path):
        full = os.path.join(self.root, *save_parts(path))
        if not os.path.isfile(full):
            raise SaveError(404, "no such save")
        return full

    def _stamp(self):
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    def _keep_version(self, parts, full):
        folder = os.path.join(self.history, *parts)
        os.makedirs(folder, exist_ok=True)
        shutil.move(full, os.path.join(folder, self._stamp()))
        versions = sorted(os.listdir(folder))
        for old in versions[:-SAVE_VERSIONS_KEPT]:
            os.remove(os.path.join(folder, old))

    def make_dir(self, path):
        parts = save_parts(path)
        with self.lock:
            os.makedirs(os.path.join(self.root, *parts), exist_ok=True)

    def put(self, path, stream, length, mtime_ms=None, version_only=False):
        """Stores a save. With version_only it goes to the history only."""
        parts = save_parts(path)
        if length > MAX_SAVE_BYTES:
            raise SaveError(413, "save too large")
        full = os.path.join(self.root, *parts)
        with self.lock:
            if os.path.isdir(full):
                raise SaveError(409, "a folder has this name")
            os.makedirs(os.path.dirname(full), exist_ok=True)
            part = full + ".part"
            digest = hashlib.sha256()
            left = length
            with open(part, "wb") as f:
                while left > 0:
                    chunk = stream.read(min(left, 1 << 20))
                    if not chunk:
                        break
                    f.write(chunk)
                    digest.update(chunk)
                    left -= len(chunk)
            if left:
                os.remove(part)
                raise SaveError(400, "incomplete upload")
            if mtime_ms is not None:
                os.utime(part, (mtime_ms / 1000, mtime_ms / 1000))
            if version_only:
                self._keep_version(parts, part)
            else:
                if os.path.isfile(full):
                    self._keep_version(parts, full)
                os.replace(part, full)
            st = os.stat(full) if os.path.isfile(full) else None
        return {"sha256": digest.hexdigest(),
                "mtime": st.st_mtime_ns // 10**6 if st else None}

    def delete(self, path):
        parts = save_parts(path)
        full = os.path.join(self.root, *parts)
        with self.lock:
            if not os.path.exists(full):
                return
            target = os.path.join(self.trash, self._stamp(), *parts)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.move(full, target)


# --- Game files -------------------------------------------------------------

class GameFiles:
    """The needed files of the game folder, for the server game source."""
    CACHE_SECONDS = 30

    def __init__(self, game_dir):
        self.game_dir = os.path.realpath(game_dir)
        self.lock = threading.Lock()
        self.built = 0
        self.files = {}  # relative path -> full path
        self.manifest = b""

    def _build(self):
        files, listing = {}, []
        digest = hashlib.sha256()
        for parts, full in gamefiles.walk_needed(self.game_dir):
            st = os.stat(full)
            rel = "/".join(parts)
            files[rel] = full
            listing.append({"path": rel, "size": st.st_size})
            digest.update(f"{rel}|{st.st_size}|{st.st_mtime_ns}\n".encode())
        self.files = files
        self.manifest = json.dumps({"version": digest.hexdigest()[:16],
                                    "files": listing}).encode()
        self.built = time.time()

    def refresh(self):
        with self.lock:
            if time.time() - self.built > self.CACHE_SECONDS:
                self._build()

    def path(self, rel):
        self.refresh()
        return self.files.get(rel)


def extract_start_page_art(game_dir, app_dir, data_dir):
    """Copies the menu painting and font from the game files to data/assets."""
    ezeus = gamefiles.find_ezeus_dir(game_dir)
    index_path = os.path.join(app_dir, "assets-index.json")
    if not ezeus or not os.path.isfile(index_path):
        return
    out_dir = os.path.join(data_dir, "assets")
    os.makedirs(out_dir, exist_ok=True)
    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)
    for name, entry in index.items():
        try:
            with open(os.path.join(game_dir, ezeus, entry["file"]), "rb") as src:
                src.seek(entry["pos"])
                data = src.read(entry["size"])
            if data[:3] != b"\xff\xd8\xff":
                continue  # another eZeus version; the page falls back
            with open(os.path.join(out_dir, name), "wb") as dst:
                dst.write(data)
        except OSError as e:
            print(f"Start page art {name} not extracted: {e}", flush=True)
    font = os.path.join(game_dir, ezeus, "Fonts", "Zeus.ttf")
    if os.path.isfile(font):
        shutil.copyfile(font, os.path.join(out_dir, "Zeus.ttf"))


# --- HTTP -------------------------------------------------------------------

class App:
    def __init__(self):
        self.user = env("EZEUS_USER", "zeus")
        password = env("EZEUS_PASSWORD")
        self.password_hash = env("EZEUS_PASSWORD_HASH")
        if password:
            if len(password) < MIN_PASSWORD_LENGTH:
                sys.exit(f"EZEUS_PASSWORD must have at least {MIN_PASSWORD_LENGTH} characters")
            self.password_hash = hash_password(password)
        if not self.password_hash:
            sys.exit("Set EZEUS_PASSWORD or EZEUS_PASSWORD_HASH")

        here = os.path.dirname(os.path.abspath(__file__))
        self.app_dir = os.path.realpath(env("EZEUS_APP_DIR", os.path.join(here, "app")))
        self.data_dir = os.path.realpath(env("EZEUS_DATA_DIR", "/data"))
        self.login_page = os.path.join(here, "login.html")
        if not os.path.isfile(os.path.join(self.app_dir, "eZeus.html")):
            sys.exit(f"eZeus.html not found in {self.app_dir}")
        os.makedirs(self.data_dir, exist_ok=True)

        self.mode = env("EZEUS_GAME_SOURCE", "local").lower()
        if self.mode not in ("server", "local"):
            sys.exit("EZEUS_GAME_SOURCE must be 'server' or 'local'")
        self.game = None
        if self.mode == "server":
            game_dir = env("EZEUS_GAME_DIR", "/game")
            if not gamefiles.find_ezeus_dir(game_dir):
                sys.exit(f"No eZeus folder with interface.e in {game_dir}; mount your "
                         "Zeus and Poseidon folder there or set EZEUS_GAME_SOURCE=local")
            self.game = GameFiles(game_dir)
            extract_start_page_art(game_dir, self.app_dir, self.data_dir)

        secret = env("EZEUS_SECRET")
        if secret:
            secret = secret.encode()
        else:
            secret_path = os.path.join(self.data_dir, "session-secret")
            if not os.path.isfile(secret_path):
                with open(secret_path, "wb") as f:
                    f.write(secrets.token_bytes(32))
                os.chmod(secret_path, 0o600)
            with open(secret_path, "rb") as f:
                secret = f.read()
        self.sessions = Sessions(secret, int(env("EZEUS_SESSION_DAYS", "30")))
        self.limiter = LoginLimiter()
        # scrypt takes memory; do not let sign-in attempts pile up.
        self.login_slots = threading.BoundedSemaphore(2)
        self.saves = Saves(self.data_dir)
        self.trust_proxy = env("EZEUS_TRUST_PROXY", "1") == "1"
        self.port = int(env("EZEUS_PORT", "8080"))


class Handler(http.server.BaseHTTPRequestHandler):
    app = None
    server_version = "eZeusWeb"
    sys_version = ""
    timeout = 120

    # --- helpers ---

    def log_message(self, format, *args):
        pass  # only sign-in events and errors are logged, see log_event

    def log_event(self, text):
        print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {self.client_ip()} {text}", flush=True)

    def client_ip(self):
        if self.app.trust_proxy:
            forwarded = self.headers.get("X-Forwarded-For")
            if forwarded:
                # The last entry is the one our own proxy added.
                return forwarded.split(",")[-1].strip()
        return self.client_address[0]

    def is_https(self):
        return (self.app.trust_proxy and
                self.headers.get("X-Forwarded-Proto", "").split(",")[0].strip() == "https")

    def session_user(self):
        for item in self.headers.get("Cookie", "").split(";"):
            name, _, value = item.strip().partition("=")
            if name == COOKIE:
                return self.app.sessions.user(value)
        return None

    def end_headers(self):
        # SharedArrayBuffer (pthreads) requires cross-origin isolation.
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def send_bytes(self, status, body, content_type, headers=()):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, status, data, headers=()):
        self.send_bytes(status, json.dumps(data).encode(), "application/json", headers)

    def send_error_json(self, status, message):
        self.send_json(status, {"error": message})

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def send_file(self, full, cache="no-cache"):
        try:
            f = open(full, "rb")
        except OSError:
            return self.send_error_json(404, "not found")
        with f:
            st = os.fstat(f.fileno())
            since = self.headers.get("If-Modified-Since")
            if since:
                try:
                    if int(st.st_mtime) <= email.utils.parsedate_to_datetime(since).timestamp():
                        self.send_response(304)
                        self.send_header("Cache-Control", cache)
                        self.end_headers()
                        return
                except (TypeError, ValueError):
                    pass
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if full.endswith(".wasm"):
                ctype = "application/wasm"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(st.st_size))
            self.send_header("Last-Modified", email.utils.formatdate(st.st_mtime, usegmt=True))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            if self.command != "HEAD":
                shutil.copyfileobj(f, self.wfile, 1 << 20)

    def read_body(self, limit):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return None
        if length < 0 or length > limit:
            return None
        return self.rfile.read(length)

    def same_origin(self):
        """Rejects state-changing requests sent from another site."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("X-Forwarded-Host") if self.app.trust_proxy else None
        host = (host or self.headers.get("Host") or "").split(",")[0].strip()
        return urllib.parse.urlsplit(origin).netloc == host

    def route(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        return path, query

    # --- routing ---

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path, _ = self.route()
        if path == "/healthz":
            return self.send_bytes(200, b"ok", "text/plain")
        user = self.session_user()
        if path == "/login":
            if user:
                return self.redirect("/")
            return self.send_file(self.app.login_page)
        if not user:
            if path.startswith("/api/") or "text/html" not in self.headers.get("Accept", ""):
                return self.send_error_json(401, "sign in required")
            return self.redirect("/login")

        if path == "/":
            return self.redirect("/eZeus.html")
        if path == "/api/config":
            return self.send_json(200, {"user": user, "mode": self.app.mode,
                                        "sync": True, "version": VERSION})
        if path == "/api/saves":
            return self.send_json(200, {"saves": self.app.saves.list()})
        if path.startswith("/api/saves/"):
            try:
                return self.send_file(self.app.saves.file(path[len("/api/saves/"):]), "no-store")
            except SaveError as e:
                return self.send_error_json(e.status, str(e))
        if path == "/game-manifest.json":
            if not self.app.game:
                return self.send_error_json(404, "not found")
            self.app.game.refresh()
            return self.send_bytes(200, self.app.game.manifest, "application/json")
        if path.startswith("/game/"):
            full = self.app.game.path(path[len("/game/"):]) if self.app.game else None
            if not full:
                return self.send_error_json(404, "not found")
            return self.send_file(full)
        if path.startswith("/assets/"):
            name = path[len("/assets/"):]
            if "/" in name or name.startswith("."):
                return self.send_error_json(404, "not found")
            for base in (os.path.join(self.app.data_dir, "assets"),
                         os.path.join(self.app.app_dir, "assets")):
                if os.path.isfile(os.path.join(base, name)):
                    return self.send_file(os.path.join(base, name))
            return self.send_error_json(404, "not found")
        # Only files directly in the app folder; no listings, no subfolders.
        name = path.lstrip("/")
        if name and "/" not in name and not name.startswith("."):
            full = os.path.join(self.app.app_dir, name)
            if os.path.isfile(full) and name != "assets-index.json":
                return self.send_file(full)
        return self.send_error_json(404, "not found")

    def do_POST(self):
        path, _ = self.route()
        if not self.same_origin():
            return self.send_error_json(403, "cross-site request")
        if path == "/api/login":
            return self.login()
        if path == "/api/logout":
            return self.send_json(200, {"ok": True}, [("Set-Cookie", self.cookie("", 0))])
        return self.send_error_json(404, "not found")

    def do_PUT(self):
        path, query = self.route()
        if not self.session_user():
            return self.send_error_json(401, "sign in required")
        if not self.same_origin():
            return self.send_error_json(403, "cross-site request")
        if not path.startswith("/api/saves/"):
            return self.send_error_json(404, "not found")
        rel = path[len("/api/saves/"):]
        try:
            if rel.endswith("/"):
                self.app.saves.make_dir(rel)
                return self.send_json(200, {"ok": True})
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self.send_error_json(411, "length required")
            mtime = self.headers.get("X-Mtime")
            result = self.app.saves.put(
                rel, self.rfile, length,
                mtime_ms=int(mtime) if mtime and mtime.isdigit() else None,
                version_only=query.get("version") == ["1"])
            return self.send_json(200, result)
        except SaveError as e:
            return self.send_error_json(e.status, str(e))

    def do_DELETE(self):
        path, _ = self.route()
        if not self.session_user():
            return self.send_error_json(401, "sign in required")
        if not self.same_origin():
            return self.send_error_json(403, "cross-site request")
        if not path.startswith("/api/saves/"):
            return self.send_error_json(404, "not found")
        try:
            self.app.saves.delete(path[len("/api/saves/"):])
            return self.send_json(200, {"ok": True})
        except SaveError as e:
            return self.send_error_json(e.status, str(e))

    # --- sign-in ---

    def cookie(self, value, max_age):
        parts = [f"{COOKIE}={value}", "Path=/", "HttpOnly", "SameSite=Strict",
                 f"Max-Age={max_age}"]
        if self.is_https():
            parts.append("Secure")
        return "; ".join(parts)

    def login(self):
        ip = self.client_ip()
        wait = self.app.limiter.wait_time(ip)
        if wait:
            self.log_event(f"sign-in refused, locked for {wait}s")
            return self.send_json(429, {"error": "too many attempts", "retry_after": wait},
                                  [("Retry-After", str(wait))])
        body = self.read_body(4096)
        try:
            data = json.loads(body or b"")
            username, password = str(data["username"]), str(data["password"])
        except (ValueError, KeyError, TypeError):
            return self.send_error_json(400, "bad request")
        if not self.app.login_slots.acquire(timeout=10):
            return self.send_error_json(503, "busy, try again")
        try:
            # Always run the hash so the answer time does not reveal the name.
            good = verify_password(password, self.app.password_hash)
            good = hmac.compare_digest(username.encode(), self.app.user.encode()) and good
        finally:
            self.app.login_slots.release()
        if not good:
            self.app.limiter.failed(ip)
            self.log_event("sign-in failed")
            time.sleep(0.5)
            return self.send_error_json(401, "wrong name or password")
        self.app.limiter.succeeded(ip)
        self.log_event("signed in")
        token = self.app.sessions.issue(self.app.user)
        return self.send_json(200, {"ok": True},
                              [("Set-Cookie", self.cookie(token, self.app.sessions.lifetime))])


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "hash-password":
        import getpass
        password = getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            sys.exit(f"Use at least {MIN_PASSWORD_LENGTH} characters")
        print(hash_password(password))
        return

    Handler.app = App()
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", Handler.app.port), Handler)
    httpd.daemon_threads = True
    # As PID 1 in a container Python ignores SIGTERM unless it is handled.
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=httpd.shutdown).start())
    print(f"eZeus Web on port {Handler.app.port}, game source: {Handler.app.mode}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
