"""Command line: doc2md.py INPUT... [-o OUT]"""
import argparse
import json
import os
import sys
import time

from . import DocError, convert_file
from .report import FEATURE_MATRIX, IGNORED_BY_DESIGN

_MARK = {'ok': 'YES ', 'part': 'PART', 'lost': 'NO  '}


def _out_path(src, out, many):
    if out is None:
        return os.path.splitext(src)[0] + '.md'
    if many or os.path.isdir(out) or out.endswith(('/', '\\')):
        os.makedirs(out, exist_ok=True)
        return os.path.join(out, os.path.splitext(os.path.basename(src))[0] + '.md')
    return out


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(
        prog='doc2md', description='Convert Word documents (.docx, .doc, .rtf, .odt, ...) to Markdown.')
    ap.add_argument('inputs', nargs='*', help='input file(s)')
    ap.add_argument('-o', '--output', help="output .md file (one input) or directory; '-' = stdout")
    ap.add_argument('--embed-images', action='store_true', help='inline images as base64 data URIs')
    ap.add_argument('-q', '--quiet', action='store_true', help='no coverage report')
    ap.add_argument('--json', action='store_true', help='print coverage report as JSON on stderr')
    ap.add_argument('--features', action='store_true', help='list supported Word features and exit')
    a = ap.parse_args(argv)

    if a.features:
        for status, text in FEATURE_MATRIX:
            print('[%s] %s' % (_MARK[status], text))
        print('Ignored by design (no Markdown equivalent): ' + IGNORED_BY_DESIGN)
        return 0
    if not a.inputs:
        ap.print_usage(sys.stderr)
        return 2
    if a.output == '-' and len(a.inputs) > 1:
        print('error: -o - needs exactly one input', file=sys.stderr)
        return 2

    failed = 0
    for src in a.inputs:
        t0 = time.perf_counter()
        try:
            to_stdout = a.output == '-'
            out = None if to_stdout else _out_path(src, a.output, len(a.inputs) > 1)
            media = (os.path.splitext(os.path.basename(out))[0] if out else 'doc') + '_media'
            res = convert_file(src, media, a.embed_images)
        except (DocError, OSError) as e:
            print('error: %s: %s' % (src, e), file=sys.stderr)
            failed += 1
            continue
        except Exception as e:  # never traceback at the user for a bad document
            print('error: %s: unexpected %s: %s' % (src, type(e).__name__, e), file=sys.stderr)
            failed += 1
            continue
        if to_stdout:
            sys.stdout.write(res.markdown)
        else:
            with open(out, 'w', encoding='utf-8', newline='\n') as f:
                f.write(res.markdown)
            if res.images:
                mdir = os.path.join(os.path.dirname(os.path.abspath(out)), media)
                os.makedirs(mdir, exist_ok=True)
                for name, data in res.images.items():
                    with open(os.path.join(mdir, name), 'wb') as f:
                        f.write(data)
        if not a.quiet:
            dest = '<stdout>' if to_stdout else out
            print('%s -> %s  (%.3fs, %d images)' % (src, dest, time.perf_counter() - t0, len(res.images)),
                  file=sys.stderr)
            print(json.dumps(res.report.as_dict()) if a.json else res.report.format(), file=sys.stderr)
    return 1 if failed else 0
