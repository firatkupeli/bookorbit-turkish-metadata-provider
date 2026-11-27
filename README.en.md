# BookOrbit Turkish Metadata Provider

[Türkçe kurulum ve Field Rules rehberi](README.md)

An independent Python 3.12 / FastAPI external metadata provider for BookOrbit.
The first source is Kitapyurdu. The source adapter interface supports adding
other Turkish sources later.

**Version 0.1.1, early beta.** Tested with the official BookOrbit conformance
checker. Building and running on Synology DS224+, manual BookOrbit search and
single-book Auto-fill were confirmed by the installer. This is limited testing,
not a guarantee for every edition or library. See [verification](docs/VERIFICATION.md).

## Source access and content rights

This is an HTML adapter, not a client for an official Kitapyurdu metadata API.
Only observed search/product HTML routes and cover URLs are used. The adapter
checks robots.txt during operation and does not bypass access controls.

Explicit permission for automated metadata access, content reuse or redistribution
has **not been verified**. robots.txt does not grant these rights. The MIT license
covers project code, not third-party descriptions, metadata or cover art.
See [source access review](docs/SOURCE_ACCESS.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).

## Install from source

1. Extract this source package.
2. Copy `.env.example` to `.env`.
3. Set `BOOKORBIT_NETWORK` to an existing Docker network shared with the
   BookOrbit server container. The supplied name is only an example.
4. Run `docker compose config --quiet`, then `docker compose up -d --build`.
5. In BookOrbit, add an external provider at `http://turkish-metadata:8080`.
   Enable **Allow private address** and use a timeout of at least 15 seconds.
   Leave Authorization empty unless you set `AUTH_TOKEN`; then enter
   `Bearer <your-token>`.

No public registry image is assumed to exist yet. A tag-triggered GHCR workflow
is included for future publication. The general Compose file uses native
architecture; the optional [Synology macvlan example](docs/SYNOLOGY.md) targets
DS224+ / amd64 and requires the operator's own network and unused IP.
ARM64 publication is configured but has not been tested on actual ARM hardware.

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
