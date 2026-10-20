#!/usr/bin/env python3
"""Markdown -> Word:   py md2docx.py notes.md              -> notes.docx
                       py md2docx.py a.md b.md -o out/     -> out/a.docx, out/b.docx
Requires: Python 3.9+, markdown-it-py, mdit-py-plugins (and lxml via the shared doctomd package)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mdtodoc.cli import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
