"""CI-only HTTP roundtrip against an already running container."""

import json
import sys

import httpx

from app.epub import EpubDocument
from tests.test_epub_editor import contents, make_epub


def main():
    original = make_epub(cover=False)
    headers = {"X-BookOrbit-Web": "1"}
    with httpx.Client(base_url=sys.argv[1], timeout=30) as client:
        assert client.get("/").status_code == 200
        assert client.get("/assets/app.js").status_code == 200
        read = client.post("/web/epub/read", files={"file": ("ci.epub", original)}, headers=headers)
        read.raise_for_status()
        metadata = read.json()["metadata"]
        metadata["title"] = "Türkçe — EPUB denemesi"
        result = client.post(
            "/web/epub/export",
            files={"file": ("ci.epub", original)},
            data={"options": json.dumps({"metadata": metadata})},
            headers=headers,
        )
        result.raise_for_status()
    before, after = contents(original), contents(result.content)
    with EpubDocument(result.content) as book:
        assert book.metadata_dict()["title"] == metadata["title"]
        assert all(before[name] == after[name] for name in before if name != book.opf_path)
    print("Web upload/export roundtrip passed; book content preserved.")


if __name__ == "__main__":
    main()
