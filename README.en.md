# Künye — EPUB & KEPUB Workshop

[Türkçe kurulum ve Field Rules rehberi](README.md)

> **0.4.0 / early beta release candidate.**
> Upload JPG/PNG covers, compare actual image dimensions, format and size,
> and select a web metadata source. 1000Kitap is experimental. Optional EPUB 3,
> KEPUB and review before download remain available.
> BookOrbit searches Kitapyurdu and 1000Kitap through the same provider address.
> See [usage and limitations](docs/KUNYE_PREVIEW.md).
> The BookOrbit provider identity and API remain compatible. The installer
> completed the NAS installation and acceptance tests. Before pulling 0.4.0,
> verify that its **Publish container** workflow succeeded and the package is Public.

> The older **0.1.2** image contains the previous provider. Künye's web editor
> and 1000Kitap support require 0.4.0. [Historical audit](docs/REVIEW-AUDIT-0.1.2.md).

An independent Python 3.12 / FastAPI external metadata provider for BookOrbit.

In 0.4.0, `/search` queries Kitapyurdu and experimental 1000Kitap
within the same deadline, interleaving their ranked results. If one source
fails, available matches are returned with `partial: true`. Existing
`kitapyurdu:<id>` records remain valid; `1000kitap:<id>` lookup is supported
too. The provider key, address and Field Rules stay the same. Single-source
selection in the web editor remains independent.

The first source is Kitapyurdu. The source adapter interface supports adding
other Turkish sources later.

**0.4.0 validation:** 189 automated tests, Ruff and the official BookOrbit
conformance checker passed. EPUBCheck 5.4.0 reported no errors or warnings
for generated EPUB 3 and KEPUB samples. The installer reported completing
NAS installation and acceptance tests. This is limited testing, not a
guarantee for every book or device; physical ARM64 testing has not been performed.
See [test scope](docs/KUNYE_PREVIEW.md) and
[machine-readable results](docs/preview-verification-0.4.0.json).

## Source access and content rights

This is an HTML adapter, not a client for an official Kitapyurdu metadata API.
Only observed search/product HTML routes and cover URLs are used. The adapter
checks robots.txt during operation and does not bypass access controls.

Explicit permission for automated metadata access, content reuse or redistribution
has **not been verified**. robots.txt does not grant these rights. The MIT license
covers project code, not third-party descriptions, metadata or cover art.
See [source access review](docs/SOURCE_ACCESS.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).

## Installation — 0.4.0

Docker Engine and Compose v2 are required. Network/IP fields are supplied by
the operator; no personal network settings or credentials are included.

### Build from source

1. Extract the source files into one directory; `Dockerfile`, `app` and
   `main.py` must share the same root.
2. Copy `.env.example` to `.env`.
3. Fill the empty `BOOKORBIT_NETWORK` field with an existing Docker network
   reachable from the BookOrbit server container.
4. Leave `PROVIDER_IMAGE` empty and run:

   ```sh
   docker compose config --quiet
   docker compose up -d --build
   docker compose ps
   ```

The service exposes port 8080 to its Docker network. The web editor is at `/`
on the same service as the BookOrbit API.

### Use the 0.4.0 registry image

Use this method after the **v0.4.0 Publish container** workflow has succeeded
and its package is Public. Set this value in your own `.env` file:

```dotenv
PROVIDER_IMAGE=ghcr.io/firatkupeli/bookorbit-turkish-metadata-provider:0.4.0
```

Then run:

```sh
docker compose config --quiet
docker compose pull
docker compose up -d --no-build
docker compose ps
```

A published Public image can be pulled without GHCR login or a personal token.
The general Compose file uses native architecture. The optional
[Synology macvlan example](docs/SYNOLOGY.md) targets DS224+ / amd64 and requires
the operator's own existing network and unused static IP. Keep only the
selected configuration as `docker-compose.yml` in the NAS installation copy.
The publishing workflow targets amd64/arm64; physical ARM64 runtime testing
has not been performed.

## Connect to BookOrbit

In BookOrbit, add an external provider at `http://turkish-metadata:8080`
on the shared Docker network. For macvlan, use the static IP chosen for
your own installation with port 8080.

Enable **Allow private address** and use a timeout of at least 15 seconds.
Leave Authorization empty unless you set `AUTH_TOKEN`; then enter
`Bearer <your-token>`. Test the connection and review the correct ISBN/edition
in a manual single-book search before configuring automatic metadata.

## Fields and matching

Supported: title, authors, Turkish description, cover, publisher, publication
date/year, page count, source language, ISBN-13 and ISBN-10.
`translators` is an extension that BookOrbit currently does not import.
Subtitle, first publication, series, genres, ratings and audiobook fields
are not advertised.

Search accepts title, author and ISBN. Supplied ISBNs require an exact match.
Without ISBN, known different authors are excluded before and after detail
lookup. The source's ISBN index is incomplete: send title and author alongside
ISBN for a cold cache. An invalid ISBN falls back to supplied title/author text;
invalid ISBN-only requests return 400. Without ISBN, author aliases in another
language may not match; use a validated ISBN in that case. Missing data is
omitted, never fabricated.

For automatic metadata, add the provider first in **Field Rules** for supported
fields. Start with **Fill gaps** to preserve existing values. For Description,
**If provided** can replace an existing description with the Turkish result.
Review a single-book Auto-fill result before saving or applying changes broadly.

## Operation and development

In-memory bounded cache, source pacing, request deadlines, API throttling,
UTF-8, non-root/read-only container, one worker and 256 MiB memory limit.
Settings are in `.env.example`; the EPUB web editor is at `/`.
`/healthz` checks process health, `/docs` provides interactive API documentation.

[Development / offline tests](CONTRIBUTING.md) ·
[Security](SECURITY.md) · [Publishing](docs/PUBLISHING.md) ·
[Changelog](CHANGELOG.md)

[MIT license](LICENSE) for project code. This project is not affiliated with
or endorsed by BookOrbit or Kitapyurdu.
