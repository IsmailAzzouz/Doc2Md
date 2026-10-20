# Contributing

Thank you for improving Doc2Md! Please open an issue for large or
backwards-incompatible changes before writing a substantial implementation.

## Development

1. Fork the repository and create a feature branch from `main`.
2. Install Python 3.9+ and run `python -m pip install -e '.[dev]'`.
3. Add tests for fixes and conversions, ideally with minimal synthetic DOCX
   fixtures. Do not commit documents containing personal or confidential data.
4. Run `python -m pytest` and `python -m compileall -q doctomd mdtodoc`.
5. Open a focused pull request describing behavior, limitations and tests.

Keep compatibility with supported Python versions. Prefer smaller, well-tested
changes over large rewrites; preserve existing CLI behavior unless justified.

## Reporting bugs

Include your operating system, Python version, exact command, expected/actual
behavior and a *sanitized* minimal reproducible file if needed. See
[SECURITY.md](SECURITY.md) for vulnerability reports.

## Licensing

By submitting a contribution you agree to license it under this project's
[MIT License](LICENSE). You must have the right to contribute the code; do not
submit third-party proprietary content or confidential data.
