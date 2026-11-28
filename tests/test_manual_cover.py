import io
import json

import pytest
from PIL import Image

from app.epub import EpubDocument, EpubError, EpubMetadata
from app.epub_structure import cover_pages
from app.images import image_info
from tests.test_epub_editor import HEADERS, contents, repack
from tests.test_epub_upgrade import sample_epub


def cover_image(width=120, height=180, kind="JPEG", orientation=None):
    output = io.BytesIO()
    image = Image.new("RGB", (width, height), (23, 99, 78))
    options = {}
    if orientation:
        exif = Image.Exif()
        exif[274] = orientation
        options["exif"] = exif
    image.save(output, format=kind, **options)
    return output.getvalue()


def test_dimensions_format_bytes_and_exif_rotation():
    image = cover_image(120, 180)
    info = image_info(image)
    assert (info["width"], info["height"], info["bytes"], info["ratio"]) == (
        120,
        180,
        len(image),
        "2:3",
    )
    assert image_info(cover_image(180, 120, orientation=6))["width"] == 120


@pytest.mark.parametrize("image", [b"not an image", b"\xff\xd8\xffbroken"])
def test_bad_image_is_not_accepted_by_magic_alone(image):
    with pytest.raises(EpubError):
        image_info(image)


def test_pixel_limit_is_checked_before_decoding(monkeypatch):
    monkeypatch.setattr("app.images.MAX_PIXELS", 100)
    with pytest.raises(EpubError, match="piksel"):
        image_info(cover_image())


def test_animated_png_is_rejected():
    output = io.BytesIO()
    first = Image.new("RGB", (2, 3), "red")
    first.save(
        output, format="PNG", save_all=True, append_images=[Image.new("RGB", (2, 3), "blue")]
    )
    with pytest.raises(EpubError, match="Hareketli"):
        image_info(output.getvalue())


def test_upload_inspection_and_export_use_identical_image_without_extra_cover_page(client):
    api, _ = client
    image = cover_image()
    inspected = api.post("/web/cover/inspect", files={"cover": ("my.jpg", image)}, headers=HEADERS)
    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["info"]["width"] == 120
    original = sample_epub()
    with EpubDocument(original) as book:
        data = book.metadata_dict()
    result = api.post(
        "/web/epub/export",
        files={"file": ("book.epub", original), "cover": ("my.jpg", image)},
        data={
            "options": json.dumps(
                {"metadata": data, "expected_cover_sha256": inspected.json()["sha256"]}
            )
        },
        headers=HEADERS,
    )
    assert result.status_code == 200, result.text
    with EpubDocument(result.content) as book:
        assert book.cover_data() == image
        assert len(cover_pages(book)) == 1
    assert contents(original)["OPS/chapter.xhtml"] == contents(result.content)["OPS/chapter.xhtml"]
    checked = api.post(
        "/web/epub/check", files={"file": ("out.epub", result.content)}, headers=HEADERS
    )
    assert checked.json()["cover_info"] == inspected.json()["info"]


def test_two_cover_origins_and_oversized_cover_are_rejected(client):
    api, _ = client
    image = cover_image()
    with EpubDocument(sample_epub()) as book:
        data = book.metadata_dict()
    response = api.post(
        "/web/epub/export",
        files={"file": ("book.epub", sample_epub()), "cover": ("my.jpg", image)},
        data={"options": json.dumps({"metadata": data, "cover_provider_id": "kitapyurdu:51855"})},
        headers=HEADERS,
    )
    assert response.status_code == 422
    assert api.post(
        "/web/cover/inspect",
        files={"cover": ("big.png", b"x" * (5 * 1024 * 1024 + 1))},
        headers=HEADERS,
    ).status_code in (413, 422)


def test_image_upload_keeps_authentication_and_same_origin_checks(client):
    api, _ = client
    assert (
        api.post("/web/cover/inspect", files={"cover": ("x.png", cover_image())}).status_code == 403
    )


def test_changed_image_format_updates_cover_links_and_keeps_other_resources():
    entries = contents(sample_epub())
    entries["OPS/style.css"] += b' .cover { background-image: url("images/cover.png"); }'
    entries["OPS/titlepage.xhtml"] = entries["OPS/titlepage.xhtml"].replace(
        b'<img src="images/cover.png" alt="Kapak"/>',
        b'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'
        b'<image xlink:href="images/cover.png"/></svg>',
    )
    image = cover_image()
    with EpubDocument(repack(entries)) as book:
        result = book.write(EpubMetadata(**book.metadata_dict()), image)
    after = contents(result)
    with EpubDocument(result) as book:
        item = book.current_cover()
        assert item.getAttribute("href") == "images/cover.jpg"
        assert item.getAttribute("media-type") == "image/jpeg"
        assert book.cover_data() == image
        assert len(cover_pages(book)) == 1
    assert b"images/cover.jpg" in after["OPS/style.css"]
    assert b"images/cover.jpg" in after["OPS/titlepage.xhtml"]
    assert after["OPS/chapter.xhtml"] == entries["OPS/chapter.xhtml"]
    assert after["OPS/images/cover.png"] == entries["OPS/images/cover.png"]
    assert after["OPS/images/old.png"] == entries["OPS/images/old.png"]
