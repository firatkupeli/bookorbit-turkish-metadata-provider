# BookOrbit Turkish Metadata Provider

[Türkçe kurulum ve Field Rules rehberi](README.md)

An independent Python 3.12 / FastAPI external metadata provider for BookOrbit.
The first source is Kitapyurdu. The source adapter interface supports adding
other Turkish sources later.

**Version 0.1.1, early beta.** Tested with the official BookOrbit conformance
checker. Building and running on Synology DS224+, manual BookOrbit search and
single-book Auto-fill were confirmed by the installer. This is limited testing,
not a guarantee for every edition or library. GitHub CI passed the offline tests,
official API conformance checker, Docker build and read-only container checks.
See [verification](docs/VERIFICATION.md).

## Source access and content rights

This is an HTML adapter, not a client for an official Kitapyurdu metadata API.
Only observed search/product HTML routes and cover URLs are used. The adapter
checks robots.txt during operation and does not bypass access controls.

Explicit permission for automated metadata access, content reuse or redistribution
has **not been verified**. robots.txt does not grant these rights. The MIT license
covers project code, not third-party descriptions, metadata or cover art.
See [source access review](docs/SOURCE_ACCESS.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).

## Install with the published image

Docker Engine and Compose v2 are required. Public image:

```text
ghcr.io/firatkupeli/bookorbit-turkish-metadata-provider:0.1.1
```

Both `linux/amd64` and `linux/arm64` images are published. All image layers for
both architectures were downloaded anonymously and verified against their SHA-256
digests. Actual ARM hardware runtime testing has not been performed.

1. Download and extract this repository's files into one directory.
2. Copy `.env.example` to `.env`.
3. Set `BOOKORBIT_NETWORK` to an existing Docker network shared with the
   BookOrbit server container. The supplied name is only an example.
4. Set `PROVIDER_IMAGE` in the same `.env` file:

   ```dotenv
   PROVIDER_IMAGE=ghcr.io/firatkupeli/bookorbit-turkish-metadata-provider:0.1.1
   ```

5. Run these commands in the project directory:

   ```sh
   docker compose config --quiet
   docker compose pull
   docker compose up -d --no-build
   docker compose ps
   ```

No GHCR login or personal access token is required.
For a local source build, leave `PROVIDER_IMAGE` empty and use
`docker compose up -d --build` instead.

The general Compose file uses native architecture. The optional
[Synology macvlan example](docs/SYNOLOGY.md) targets DS224+ / amd64 and requires
the operator's own existing network and unused static IP. Set `PROVIDER_IMAGE`
to the GHCR address above when choosing the published image.

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
ISBN for a cold cache. Missing data is omitted, never fabricated.

For automatic metadata, add the provider first in **Field Rules** for supported
fields. Start with **Fill gaps** to preserve existing values. For Description,
**If provided** can replace an existing description with the Turkish result.
Review a single-book Auto-fill result before saving or applying changes broadly.

## Operation and development

In-memory bounded cache, source pacing, request deadlines, API throttling,
UTF-8, non-root/read-only container, one worker and 256 MiB memory limit.
Settings are in `.env.example`; there is no separate admin dashboard.
`/healthz` checks process health, `/docs` provides interactive API documentation.

[Development / offline tests](CONTRIBUTING.md) ·
[Security](SECURITY.md) · [Publishing](docs/PUBLISHING.md) ·
[Changelog](CHANGELOG.md)

[MIT license](LICENSE) for project code. This project is not affiliated with
or endorsed by BookOrbit or Kitapyurdu.
