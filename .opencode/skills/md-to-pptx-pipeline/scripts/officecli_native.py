from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any


class OfficeCliError(RuntimeError):
    pass


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.upper().split())


def ensure_officecli_available() -> str:
    result = subprocess.run(["officecli", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise OfficeCliError(f"Không gọi được officecli --version: {stderr or result.stdout.strip()}")
    return result.stdout.strip()


def _run_json(*arguments: str) -> dict:
    command = ["officecli", *arguments, "--json"]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise OfficeCliError(f"OfficeCLI thất bại với lệnh {' '.join(command)}: {stderr or result.stdout.strip()}")

    stdout = result.stdout.strip()
    if not stdout:
        return {"success": True, "data": None}

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise OfficeCliError(f"Không parse được JSON từ OfficeCLI cho lệnh {' '.join(command)}") from exc

    if payload.get("success") is False:
        error = payload.get("error") or {}
        message = error.get("error") or payload.get("message") or "OfficeCLI trả về lỗi không xác định."
        raise OfficeCliError(message)

    return payload


def _stringify_prop_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def officecli_view(document: Path, mode: str) -> Any:
    return _run_json("view", str(document), mode).get("data")


def officecli_get(document: Path, path: str = "/", depth: int = 1) -> Any:
    return _run_json("get", str(document), path, "--depth", str(depth)).get("data")


def officecli_query(document: Path, selector: str, find: str | None = None) -> list[dict]:
    arguments = ["query", str(document), selector]
    if find:
        arguments.extend(["--find", find])
    payload = _run_json(*arguments).get("data") or {}
    return payload.get("results", [])


def officecli_validate(document: Path) -> dict:
    return _run_json("validate", str(document))


def officecli_open(document: Path) -> dict:
    return _run_json("open", str(document))


def officecli_save(document: Path) -> dict:
    return _run_json("save", str(document))


def officecli_close(document: Path) -> dict:
    return _run_json("close", str(document))


def officecli_add(
    document: Path,
    parent: str,
    *,
    element_type: str | None = None,
    props: dict[str, Any] | None = None,
    after: str | None = None,
    before: str | None = None,
    index: int | None = None,
    from_path: str | None = None,
) -> dict:
    arguments: list[str] = ["add", str(document), parent]
    if element_type:
        arguments.extend(["--type", element_type])
    if from_path:
        arguments.extend(["--from", from_path])
    if index is not None:
        arguments.extend(["--index", str(index)])
    if after:
        arguments.extend(["--after", after])
    if before:
        arguments.extend(["--before", before])
    for key, value in (props or {}).items():
        arguments.extend(["--prop", f"{key}={_stringify_prop_value(value)}"])
    return _run_json(*arguments)


def officecli_set(document: Path, path: str, *, props: dict[str, Any] | None = None, find: str | None = None, replace: str | None = None) -> dict:
    arguments: list[str] = ["set", str(document), path]
    for key, value in (props or {}).items():
        arguments.extend(["--prop", f"{key}={_stringify_prop_value(value)}"])
    if find is not None:
        arguments.extend(["--find", find])
    if replace is not None:
        arguments.extend(["--replace", replace])
    return _run_json(*arguments)


def officecli_remove(document: Path, path: str) -> dict:
    return _run_json("remove", str(document), path)


def extract_added_path(payload: dict) -> str | None:
    message = str(payload.get("message") or payload.get("data") or "")
    match = re.search(r'(\/[^\s]+)$', message)
    return None if match is None else match.group(1)


def to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        return None