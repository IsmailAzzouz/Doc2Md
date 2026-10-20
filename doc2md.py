#!/usr/bin/env python3
"""Single entry point:  py doc2md.py report.docx            -> report.md (+ report_media/)
                        py doc2md.py a.docx b.doc -o out/    -> out/a.md, out/b.md
                        py doc2md.py --features              -> what is supported
Requires: Python 3.9+, lxml."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from doctomd.cli import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main())
