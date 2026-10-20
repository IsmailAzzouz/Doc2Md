# Doc2Md

[![CI (main)](https://github.com/IsmailAzzouz/Doc2Md/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/IsmailAzzouz/Doc2Md/actions/workflows/ci.yml?query=branch%3Amain)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A Python toolkit for converting **Word → Markdown** and **Markdown → DOCX**. It
handles common document structure, lists, tables, links, images and a subset of
math without requiring Microsoft Word for normal `.docx` files.

> **Status:** early-stage, `0.x` software. Check [limitations](LIMITATIONS.md)
> before relying on it for legally significant documents or lossless round trips.

## Requirements

- Python 3.9 or newer.
- `lxml`, `markdown-it-py`, and `mdit-py-plugins` (installed automatically).
- Optional **LibreOffice** or Microsoft Word (Windows) for legacy formats such
  as `.doc`, `.rtf`, `.odt`, `.wps`; not needed for ordinary `.docx` files.
- Optional `Pillow` for conversion of some image types.

## Install

From the repository checkout:

```bash
python -m pip install .
# Optional image format support:
python -m pip install '.[images]'
```

For development:

```bash
python -m pip install -e '.[dev]'
python -m pytest
```

## Usage

### Word → Markdown

```bash
doc2md report.docx                   # report.md and report_media/ if needed
doc2md a.docx b.docx -o output/     # batch conversion
doc2md report.docx --embed-images   # embed images as data URIs
doc2md report.docx -o -             # Markdown on stdout
doc2md report.docx --json           # coverage report on stderr
# Supported feature overview:
doc2md --features
```

Also works from source without installation of entry points:

```bash
python doc2md.py report.docx
```

### Markdown → Word

```bash
md2docx notes.md                   # notes.docx
md2docx notes.md --page letter    # Letter rather than A4
md2docx a.md b.md -o output/
# Or from the checkout:
python md2docx.py notes.md
```

Relative image paths in Markdown are resolved against the Markdown file's
directory. Remote images are linked rather than downloaded.

### Python API

```python
from doctomd import convert_file
from mdtodoc import convert

result = convert_file("report.docx")
print(result.markdown)
print(result.report.format())

word = convert("# Hello\n\nA paragraph.")
with open("hello.docx", "wb") as file:
    file.write(word.data)
```

## Supported formats and fidelity

Native DOCX-family/Flat OPC Word XML inputs are handled by the Word → Markdown
converter; other Word-like formats require a separately installed desktop
conversion backend. Markdown → DOCX outputs `.docx` only. See
[LIMITATIONS.md](LIMITATIONS.md) for an explicit fidelity matrix and edge cases.

Conversion is **best effort**, not reversible. The feature coverage report
counts converted/approximated/unsupported feature instances, **not** a numerical
measure of document quality.

## Releases

Pull requests and pushes to `main` run one CI job in a small
`python:3.11-alpine` container: tests, wheel/sdist build and metadata check.
Version tags (`vX.Y.Z`) run one Alpine release job that validates and publishes
GitHub Release artifacts. **No GitHub Release has been published yet**; the
`0.1.0` version in `pyproject.toml` is not a published release or tag. Until the
first release, install from the repository source as described above. Releases
are not automatically published to PyPI. Maintainers should follow
[RELEASING.md](RELEASING.md) to publish a versioned tag.

## Community

- [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security policy](SECURITY.md) · [Roadmap](ROADMAP.md)
- [Changelog](CHANGELOG.md) · [Issues](https://github.com/IsmailAzzouz/Doc2Md/issues)

Licensed under the [MIT License](LICENSE).
