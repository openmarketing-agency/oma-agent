"""Call a fixed set of Open WebUI API operations for the bundled integration."""

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import requests

from hermes_cli.config import get_env_value


_OPERATIONS = {
    "models": ("GET", "/api/models", False),
    "chat": ("POST", "/api/chat/completions", True),
    "ollama-models": ("GET", "/ollama/api/tags", False),
    "ollama-running": ("GET", "/ollama/api/ps", False),
    "embed": ("POST", "/ollama/api/embed", True),
    "knowledge": ("GET", "/api/v1/knowledge/", False),
    "knowledge-show": ("GET", "/api/v1/knowledge/{id}", False),
    "knowledge-create": ("POST", "/api/v1/knowledge/create", True),
    "upload": ("POST", "/api/v1/files/", False),
    "file-status": ("GET", "/api/v1/files/{id}/process/status", False),
    "knowledge-add": ("POST", "/api/v1/knowledge/{id}/file/add", True),
}


def _base_url(value):
    url = (value or "").strip()
    parts = urlsplit(url)
    loopback = parts.hostname in {"localhost", "127.0.0.1", "::1"}
    if (not parts.hostname or parts.username is not None or parts.password is not None
            or parts.query or parts.fragment or re.search(r"[\s\\]", url)
            or not (parts.scheme == "https" or (loopback and parts.scheme == "http"))):
        raise ValueError("Set OPENWEBUI_URL to an HTTPS instance or an HTTP loopback URL")
    return url.rstrip("/")


def call(http, operation, base_url, token, *, item_id=None, body=None, file=None):
    method, path, has_body = _OPERATIONS[operation]
    if "{id}" in path:
        if not item_id or not re.fullmatch(r"[a-zA-Z0-9_-]+", item_id):
            raise ValueError("An exact file or collection ID is required")
        path = path.format(id=item_id)
    if not token or not token.strip() or re.search(r"\s", token.strip()):
        raise ValueError("Configure a valid OPENWEBUI_TOKEN in the default profile")
    if has_body and not isinstance(body, dict):
        raise ValueError("Provide a JSON object on stdin")
    if body is not None and operation == "chat":
        body = {**body, "stream": False}
    if (file is not None) != (operation == "upload"):
        raise ValueError("Upload requires exactly one explicitly selected file")
    if file is not None and not file.is_file():
        raise ValueError("The selected upload must be a regular file")
    with file.open("rb") if file is not None else nullcontext() as handle:
        with http.request(method, _base_url(base_url) + path, headers={"Authorization": f"Bearer {token.strip()}"},
                          json=body if has_body else None, files={"file": handle} if handle else None,
                          allow_redirects=False, timeout=(5, 120)) as response:
            if not 200 <= response.status_code < 300:
                raise ValueError(f"Open WebUI returned HTTP {response.status_code} for {operation}")
            return response.json() if response.content else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for operation, (_, path, _) in _OPERATIONS.items():
        command = commands.add_parser(operation)
        if "{id}" in path:
            command.add_argument("--id", required=True)
        if operation == "upload":
            command.add_argument("--file", required=True, type=Path)
    args = parser.parse_args()
    try:
        body = json.load(sys.stdin) if _OPERATIONS[args.operation][2] else None
        with requests.Session() as http:
            http.trust_env = False  # Do not inherit proxies or alternate authentication.
            result = call(http, args.operation, get_env_value("OPENWEBUI_URL"), get_env_value("OPENWEBUI_TOKEN"),
                          item_id=getattr(args, "id", None), body=body, file=getattr(args, "file", None))
    except requests.exceptions.InvalidJSONError:
        parser.exit(1, "Open WebUI did not return valid JSON\n")
    except (requests.RequestException, OSError, json.JSONDecodeError):
        parser.exit(1, "Could not complete the Open WebUI request; check connectivity, input, and saved configuration\n")
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
