"""Serve the built page, and the edits a reader makes on it.

The page is a static file and stays one: everything outside `/api/` is a file under the site
directory. `/api/edits` reads and writes the edit store. The server checks nobody's identity,
so a deployment puts it behind a login.

An icon's name is a digest of its picture, and a board file's of its content, so a browser may
keep either for good. The page names
the icons of its own build, so a browser asks whether the page changed each time it loads it.

    GET /api/edits/<set>              every edit of the set: {comp id: {field: text}}
    PUT /api/edits/<set>/<comp id>    {field: text, ...}; an empty text removes the field
    GET /api/health                   200 once the site has a page, 503 before

A probe asks `/api/health`, not the page. The page is megabytes, and a prober that reads the
first kilobytes and hangs up leaves the server writing to a closed connection.
"""

from __future__ import annotations

import json
import re
import sys
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from tft_assistant.edits import Edits
from tft_assistant.explorer import EXPLORER_DIR
from tft_assistant.icons import ICON_DIR

_SET_EDITS = re.compile(r"/api/edits/(\d{1,4})")
_COMP_EDITS = re.compile(r"/api/edits/(\d{1,4})/([0-9a-f]{10})")
_LARGEST_BODY = 64 * 1024


class _Handler(SimpleHTTPRequestHandler):
    # A page shows some two hundred icons, and a proxy in front asks for them over one connection.
    protocol_version = "HTTP/1.1"

    def __init__(self, *args: Any, edits: Edits, **kwargs: Any) -> None:
        self._edits = edits
        super().__init__(*args, **kwargs)

    def _reply(self, status: HTTPStatus, document: Any = None) -> None:
        body = b"" if document is None else json.dumps(document, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_response(self, code: int, message: str | None = None) -> None:
        super().send_response(code, message)
        if self.path.startswith("/api/"):
            return
        named_by_content = code == HTTPStatus.OK and self.path.startswith((f"/{ICON_DIR}/", f"/{EXPLORER_DIR}/"))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable" if named_by_content else "no-cache")

    def do_GET(self) -> None:
        if not self.path.startswith("/api/"):
            super().do_GET()
            return
        if self.path == "/api/health":
            built = (Path(self.directory) / "index.html").exists()
            self._reply(HTTPStatus.OK if built else HTTPStatus.SERVICE_UNAVAILABLE, {"page": built})
            return
        asked = _SET_EDITS.fullmatch(self.path)
        if asked:
            self._reply(HTTPStatus.OK, self._edits.of_set(int(asked[1])))
        else:
            self._reply(HTTPStatus.NOT_FOUND, {"error": f"no such resource: {self.path}"})

    def do_PUT(self) -> None:
        asked = _COMP_EDITS.fullmatch(self.path)
        if not asked:
            self._reply(HTTPStatus.NOT_FOUND, {"error": f"no such resource: {self.path}"})
            return
        # A page of another site can send a form to this server with the reader's login, and it
        # cannot send JSON without the browser asking this server first, which answers no.
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._reply(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "send application/json"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > _LARGEST_BODY:
            self._reply(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": f"a body is {_LARGEST_BODY} bytes at most"})
            return
        try:
            fields = json.loads(self.rfile.read(length))
            if not isinstance(fields, dict) or not all(isinstance(text, str) for text in fields.values()):
                raise ValueError("send one object of field names and texts")
            for field, text in fields.items():
                self._edits.put(int(asked[1]), asked[2], field, text)
        except ValueError as error:
            self._reply(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        self._reply(HTTPStatus.NO_CONTENT)


class _Server(ThreadingHTTPServer):
    def handle_error(self, request: Any, client_address: Any) -> None:
        """Say in one line that a client hung up; anything else keeps its traceback."""
        if isinstance(sys.exception(), ConnectionError):
            print(f"{client_address[0]} hung up before the answer was sent", file=sys.stderr)
        else:
            super().handle_error(request, client_address)


def server(site: Path, edits: Edits, port: int) -> ThreadingHTTPServer:
    """A server of the page under `site` and of `edits`, bound to `port` and not yet serving.

    Port 0 takes any free port, and `server_address` then names it.
    """
    return _Server(("", port), partial(_Handler, directory=str(site), edits=edits))
