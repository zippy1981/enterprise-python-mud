"""``azurath web``: the game in a browser, on your own computer.

A small HTTP server (standard library only) serves the page in ``static/`` and a
JSON API over :class:`azurath.session.Session`. It listens on 127.0.0.1 only,
and every API call must carry the random token from the address the game prints,
so other web pages open in your browser can't drive your game or read your files.

API (all JSON; send the token as ``X-Azurath-Token``):

=========================  =====================================================
``GET  /api/state``        the snapshot, plus map positions for every room
``POST /api/run``          ``{"line": "look"}``: run a command
``GET  /api/files``        the files in your project
``GET  /api/file?path=``   a file's text, and its STEP cards if it's a practice file
``PUT  /api/file``         ``{"path", "content"}``: save a file
``POST /api/choose``       ``{"path", "step", "index"}``: click a STEP card
=========================  =====================================================
"""

from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from azurath.content import Dungeon
from azurath.session import Session
from azurath.settings import AzurathSettings
from azurath.web import guided
from azurath.web.layout import layout

STATIC = resources.files("azurath.web") / "static"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
}
MAX_BODY = 2_000_000


class WebGame:
    """One player's game behind the web API. Requests take turns (one lock)."""

    def __init__(self, settings: AzurathSettings, dungeon: Dungeon) -> None:
        self.session = Session(settings, dungeon=dungeon, width=88, open_file=lambda *_: True)
        self.lock = threading.Lock()
        self.positions = layout(dungeon)

    @property
    def game(self):  # noqa: ANN201
        return self.session.game

    def state(self) -> dict[str, Any]:
        with self.lock:
            if not self.session.started:
                self.session.start()
            return self._state()

    def _state(self) -> dict[str, Any]:
        return {
            "snapshot": asdict(self.session.snapshot()),
            "layout": {room: list(xy) for room, xy in self.positions.items()},
        }

    def run(self, line: str) -> dict[str, Any]:
        with self.lock:
            result = self.session.run(line)
            return {
                "result": {
                    "command": result.command,
                    "html": result.html,
                    "text": result.text,
                    "opened": result.opened,
                    "quit": result.quit,
                },
                **self._state(),
            }

    # --- files ---------------------------------------------------------------------------

    def path(self, rel: str) -> Path:
        root = self.game.ws.root.resolve()
        target = (root / rel).resolve()
        if root != target and root not in target.parents:
            raise PermissionError("That's outside your project.")
        if ".git" in target.relative_to(root).parts:
            raise PermissionError("The .git folder is git's, not yours.")
        return target

    def files(self) -> list[str]:
        with self.lock:
            return self.game.ws.files()

    def starter(self, rel: str) -> str | None:
        """The room's starter text for ``rel``, if it's this room's practice file."""
        quest = self.game.room.quest
        if not quest or rel not in quest.scaffold:
            return None
        return self.game.dungeon.room_text(self.game.room.id, "scaffold", quest.scaffold[rel])

    def read(self, rel: str) -> dict[str, Any]:
        with self.lock:
            target = self.path(rel)
            content = target.read_text(encoding="utf-8") if target.is_file() else ""
            return {"path": rel, "content": content, "steps": self._steps(rel, content)}

    def _steps(self, rel: str, content: str) -> list[dict[str, Any]] | None:
        starter = self.starter(rel)
        if starter is None:
            return None
        steps = guided.with_state(starter, content)
        if not steps:
            return None
        return [
            {
                "label": s.label,
                "prompt": s.prompt,
                "choices": [{"code": c.text, "chosen": c.chosen} for c in s.choices],
            }
            for s in steps
        ]

    def write(self, rel: str, content: str) -> dict[str, Any]:
        with self.lock:
            target = self.path(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
            return {"path": rel, "saved": True, "steps": self._steps(rel, content)}

    def choose(self, rel: str, step: str, index: int) -> dict[str, Any]:
        with self.lock:
            starter = self.starter(rel)
            if starter is None:
                raise guided.ChoiceError("That file has no STEP cards in this room.")
            target = self.path(rel)
            current = target.read_text(encoding="utf-8") if target.is_file() else starter
            content = guided.choose(starter, current, step, index)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
            return {"path": rel, "content": content, "steps": self._steps(rel, content)}


def make_handler(web: WebGame, token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "Azurath"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass  # keep the terminal quiet

        # --- helpers ---------------------------------------------------------------------

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data: Any, status: int = 200) -> None:
            self._send(status, json.dumps(data).encode("utf-8"), "application/json")

        def _error(self, status: int, message: str) -> None:
            self._json({"error": message}, status)

        def _local(self) -> bool:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return host in {"127.0.0.1", "localhost", "[::1]"}  # no DNS rebinding

        def _authorised(self) -> bool:
            return self._local() and secrets.compare_digest(
                self.headers.get("X-Azurath-Token", ""), token
            )

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ValueError("That's too big.")
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("Send a JSON object.")
            return data

        def _api(self, method: str) -> None:
            if not self._authorised():
                self._error(HTTPStatus.FORBIDDEN, "Open the game from the address it printed.")
                return
            url = urlparse(self.path)
            query = parse_qs(url.query)
            try:
                if method == "GET" and url.path == "/api/state":
                    self._json(web.state())
                elif method == "POST" and url.path == "/api/run":
                    self._json(web.run(str(self._body().get("line", ""))))
                elif method == "GET" and url.path == "/api/files":
                    self._json({"files": web.files()})
                elif method == "GET" and url.path == "/api/file":
                    self._json(web.read(query.get("path", [""])[0]))
                elif method == "PUT" and url.path == "/api/file":
                    body = self._body()
                    self._json(web.write(str(body["path"]), str(body["content"])))
                elif method == "POST" and url.path == "/api/choose":
                    body = self._body()
                    self._json(web.choose(str(body["path"]), str(body["step"]), int(body["index"])))
                else:
                    self._error(HTTPStatus.NOT_FOUND, "No such API.")
            except (PermissionError, guided.ChoiceError, ValueError, KeyError) as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))

        # --- routes ----------------------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802
            if self.path.startswith("/api/"):
                self._api("GET")
                return
            if not self._local():
                self._error(HTTPStatus.FORBIDDEN, "Use http://127.0.0.1")
                return
            name = urlparse(self.path).path.lstrip("/") or "index.html"
            if "/" in name or name.startswith(".") or not (STATIC / name).is_file():
                self._error(HTTPStatus.NOT_FOUND, "Not found.")
                return
            suffix = Path(name).suffix
            self._send(200, (STATIC / name).read_bytes(), CONTENT_TYPES.get(suffix, "text/plain"))

        def do_POST(self) -> None:  # noqa: N802
            self._api("POST")

        def do_PUT(self) -> None:  # noqa: N802
            self._api("PUT")

    return Handler


def serve(
    settings: AzurathSettings,
    dungeon: Dungeon,
    *,
    port: int = 0,
    open_browser: bool = True,
) -> None:
    token = secrets.token_urlsafe(24)
    web = WebGame(settings, dungeon)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(web, token))
    url = f"http://127.0.0.1:{server.server_address[1]}/#t={token}"
    print(f"Azurath is running at {url}\n(only this computer can see it; Ctrl+C stops it)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Your progress is saved.")
    finally:
        server.server_close()
