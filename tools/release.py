"""Verify and package only the explicitly selected public tree.

No parent directory is read. ZIP timestamps are fixed for reproducible output.
Checks are a narrow publication regression gate, not a universal secret scanner.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {".venv", "__pycache__", ".pytest_cache", ".test-tmp", "dist", ".git"}
PRIVATE_IMPORTS = {"imaplib", "smtplib", "sqlite3", "cryptography", "dotenv"}
EXTERNAL_IMPORTS = {"pydantic", "fastapi", "uvicorn", "httpx", "pytest"}
MEDIA_SUFFIXES = {".png", ".gif"}


def check_media(name, data):
    """Bound static README assets; this is not a full media-content audit."""
    if PurePosixPath(name).parent != PurePosixPath("docs/assets"):
        raise ValueError(f"media outside docs/assets: {name}")
    if len(data) > 2_000_000:
        raise ValueError(f"media exceeds size limit: {name}")
    if name.endswith(".png") and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR":
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    elif name.endswith(".gif") and data[:6] in {b"GIF87a", b"GIF89a"}:
        width, height = int.from_bytes(data[6:8], "little"), int.from_bytes(data[8:10], "little")
    else:
        raise ValueError(f"invalid media header: {name}")
    if not (1 <= width <= 4096 and 1 <= height <= 4096):
        raise ValueError(f"invalid media dimensions: {name}")


def audit(root=ROOT):
    files = json.loads((root / "public-files.json").read_text(encoding="utf-8"))
    if len(files) != len(set(files)):
        raise ValueError("duplicate public manifest entries")
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
            raise ValueError(f"unsafe manifest path: {name}")
        if (any(part in IGNORED or part in {".runtime", "Заметки", "logs", "run-data"} for part in path.parts)
                or path.name.startswith(".env")
                or path.suffix.lower() in {".sqlite", ".db", ".log", ".eml", ".zip", ".exe", ".dll", ".pem"}):
            raise ValueError(f"forbidden public file: {name}")
        target = root / name
        if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"missing or unsafe public file: {name}")
    actual = set()
    for file in root.rglob("*"):
        relative = file.relative_to(root)
        if any(part in IGNORED for part in relative.parts):
            continue
        if file.is_symlink():
            raise ValueError(f"symlink in public tree: {relative}")
        if file.is_file():
            actual.add(relative.as_posix())
    if actual != set(files):
        raise ValueError(f"unlisted or missing public files: {sorted(actual.symmetric_difference(files))}")
    local_packages = {"server", "mail_connector", "bitrix_connector", "openwebui_tools", "tools"}
    for name in files:
        if PurePosixPath(name).suffix.lower() in MEDIA_SUFFIXES:
            check_media(name, (root / name).read_bytes())
            continue
        text = (root / name).read_text(encoding="utf-8")
        if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text):
            raise ValueError(f"private key marker: {name}")
        if re.search(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,})\b", text):
            raise ValueError(f"token-like string: {name}")
        # Actual email-shaped literals must use reserved synthetic domains.
        for domain in re.findall(r"[\w.+-]+@([\w.-]+\.[A-Za-z]{2,})", text):
            if not domain.endswith((".test", ".invalid")):
                raise ValueError(f"non-synthetic email literal: {name}")
        if not name.endswith(".py"):
            continue
        tree = ast.parse(text, filename=name)
        for node in ast.walk(tree):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for module in modules:
                top = module.split(".")[0]
                if isinstance(node, ast.ImportFrom) and node.level:
                    package = list(PurePosixPath(name).parent.parts)
                    package = package[:len(package) - node.level + 1]
                    relative_module = "/".join(package + module.split("."))
                    if not (root / (relative_module + ".py")).is_file() and not (root / relative_module).is_dir():
                        raise ValueError(f"unresolved relative import: {name}:{module}")
                    continue
                if top in PRIVATE_IMPORTS:
                    raise ValueError(f"private transport/storage import: {name}:{top}")
                if top in local_packages:
                    relative_module = module.replace(".", "/")
                    if not (root / (relative_module + ".py")).is_file() and not (root / relative_module).is_dir():
                        raise ValueError(f"missing local import: {name}:{module}")
                elif top not in EXTERNAL_IMPORTS and top not in sys.stdlib_module_names:
                    raise ValueError(f"unreviewed import: {name}:{module}")
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    for name, expected in provenance.items():
        if name not in files or hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"original source drift: {name}")
    return sorted(files)


def build(files):
    destination = ROOT / "dist" / "mail-agent-showcase.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (ROOT / name).read_bytes())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None or sorted(archive.namelist()) != files:
            raise ValueError("ZIP verification failed")
        for name in files:
            if archive.read(name) != (ROOT / name).read_bytes():
                raise ValueError(f"ZIP content mismatch: {name}")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(f"{digest}  {destination.name}\n", encoding="utf-8")
    print(f"Built {destination.name}: {len(files)} files, SHA256 {digest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    selected = audit()
    print(f"PUBLIC CHECK PASSED: {len(selected)} allowlisted files")
    if args.build:
        build(selected)
