"""Build an allowlisted, reproducible public source archive; never publish it."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import runpy
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "bookorbit-turkish-metadata-provider"
ROOT_FILES = (
    ".dockerignore",
    ".env.example",
    ".env.synology.example",
    ".gitattributes",
    ".gitignore",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "README.en.md",
    "SECURITY.md",
    "THIRD_PARTY_NOTICES.md",
    "compose.yaml",
    "compose.synology.yaml",
    "main.py",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "uv.lock",
)
DIRECTORIES = ("app", "tests", "docs", "tools", ".github")
SUFFIXES = {
    ".py",
    ".md",
    ".go",
    ".mod",
    ".sum",
    ".txt",
    ".json",
    ".html",
    ".yaml",
    ".yml",
    ".js",
    ".mjs",
    ".css",
}
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "node_modules",
}
PATTERNS = (
    ("GitHub credential", re.compile(r"\b(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{20,}\b")),
    ("private key", re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")),
    ("Windows user path", re.compile(r"[A-Z]:[\\/]+Users[\\/]+", re.IGNORECASE)),
    ("Unix user path", re.compile(r"/(?:home|Users)/[A-Za-z0-9_.-]+/")),
)
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
KEPUB_WASM_DIGEST = "a5e368c41fed87fe3c6ebd5f9f8641e4fdc2a9123ee42d4c315317b6e101c2d9"
BINARY_INPUTS = {"app/static/vendor/kepubify/kepubify.wasm": KEPUB_WASM_DIGEST}


def check_text(name: str, content: str) -> list[str]:
    """Detect selected public-package hazards without printing matched secrets."""
    problems = []
    for label, pattern in PATTERNS:
        if pattern.search(content):
            problems.append(f"{name}: {label}")
    for match in IPV4.finditer(content):
        try:
            address = ipaddress.ip_address(match.group())
        except ValueError:
            continue
        # Local development and binding examples are deliberate.
        if address.is_private and not (address.is_loopback or address.is_unspecified):
            problems.append(f"{name}: private IPv4 address")
            break
    return problems


def collect_files() -> dict[str, bytes]:
    candidates = [ROOT / name for name in ROOT_FILES]
    for folder in DIRECTORIES:
        for path in sorted((ROOT / folder).rglob("*")):
            relative = path.relative_to(ROOT)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if path.is_file() and (
                path.suffix in SUFFIXES
                or path.name == "LICENSE"
                or relative.as_posix() in BINARY_INPUTS
            ):
                candidates.append(path)

    files = {}
    for path in candidates:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
            raise ValueError(f"Missing or unsafe release input: {path.relative_to(ROOT)}")
        name = path.relative_to(ROOT).as_posix()
        if path.name.startswith(".env") and name not in {".env.example", ".env.synology.example"}:
            raise ValueError(f"Unexpected environment file: {name}")
        if ".local." in path.name or path.name in {"compose.override.yaml", "compose.override.yml"}:
            continue
        data = path.read_bytes()
        if name in BINARY_INPUTS:
            if hashlib.sha256(data).hexdigest() != BINARY_INPUTS[name]:
                raise ValueError(f"Unexpected binary release input: {name}")
            files[name] = data
        else:
            data.decode("utf-8")
            files[name] = data.replace(b"\r\n", b"\n")
    return dict(sorted(files.items()))


def validate(files: dict[str, bytes]) -> str:
    version = runpy.run_path(str(ROOT / "app" / "__init__.py"))["__version__"]
    project = tomllib.loads(files["pyproject.toml"].decode("utf-8"))["project"]
    if project["version"] != version:
        raise ValueError("Application and project versions differ")
    problems = []
    for name, data in files.items():
        if name in BINARY_INPUTS:
            continue
        problems.extend(check_text(name, data.decode("utf-8")))
    if problems:
        raise ValueError("Public package check failed:\n" + "\n".join(problems))
    if "tools/conformance/LICENSE" not in files:
        raise ValueError("Upstream conformance license must be included")
    if ".github/workflows/test.yml" not in files:
        raise ValueError("Test workflow must be included")
    vendor = "app/static/vendor/kepubify/"
    vendor_manifest = json.loads(files[vendor + "VENDOR.json"])
    for entry in vendor_manifest["files"]:
        payload = files.get(vendor + entry["path"], b"")
        if len(payload) != entry["bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise ValueError(f"Kepubify vendor integrity mismatch: {entry['path']}")
    return version


def add_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    entry.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(entry, data)


def build_archive(files: dict[str, bytes], version: str) -> tuple[Path, str]:
    output_dir = ROOT / "dist"
    output_dir.mkdir(exist_ok=True)
    destination = output_dir / f"{PROJECT}-{version}-source.zip"
    manifest = {
        "project": PROJECT,
        "version": version,
        "files": [
            {"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for name, data in files.items()
        ],
    }
    with zipfile.ZipFile(destination, "w") as archive:
        for name, data in files.items():
            add_entry(archive, f"{PROJECT}/{name}", data)
        add_entry(
            archive,
            f"{PROJECT}/RELEASE-MANIFEST.json",
            (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive integrity check failed")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(
        f"{digest}  {destination.name}\n", encoding="utf-8"
    )
    return destination, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Validate without writing a ZIP")
    args = parser.parse_args()
    try:
        files = collect_files()
        version = validate(files)
        print(f"Public release inputs OK: {len(files)} files, version {version}")
        if not args.check_only:
            destination, digest = build_archive(files, version)
            print(f"Created: dist/{destination.name}")
            print(f"SHA-256: {digest}")
    except (OSError, UnicodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
