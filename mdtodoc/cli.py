"""Command line: md2docx.py INPUT.md... [-o OUT]"""
import argparse
import os
import sys
import time

from . import convert


def _out_path(src, out, many):
    stem = os.path.splitext(os.path.basename(src))[0] + '.docx'
    if out is None:
        return os.path.join(os.path.dirname(os.path.abspath(src)), stem)
    if many or os.path.isdir(out) or out.endswith(('/', '\\')):
        os.makedirs(out, exist_ok=True)
        return os.path.join(out, stem)
    return out


def main(argv=None):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog='md2docx', description='Convert Markdown files to Word (.docx).')
    ap.add_argument('inputs', nargs='+', help='markdown file(s)')
    ap.add_argument('-o', '--output', help='output .docx (one input) or directory')
    ap.add_argument('--page', choices=('a4', 'letter'), default='a4', help='page size (default a4)')
    ap.add_argument('-q', '--quiet', action='store_true', help='no coverage report')
    a = ap.parse_args(argv)

    failed = 0
    for src in a.inputs:
        t0 = time.perf_counter()
        try:
            with open(src, 'r', encoding='utf-8-sig') as f:
                text = f.read()
            out = _out_path(src, a.output, len(a.inputs) > 1)
            res = convert(text, os.path.dirname(os.path.abspath(src)), a.page)
            with open(out, 'wb') as f:
                f.write(res.data)
        except (OSError, UnicodeDecodeError) as e:
            print('error: %s: %s' % (src, e), file=sys.stderr)
            failed += 1
            continue
        except Exception as e:
            print('error: %s: unexpected %s: %s' % (src, type(e).__name__, e), file=sys.stderr)
            failed += 1
            continue
        if not a.quiet:
            print('%s -> %s  (%.3fs)' % (src, out, time.perf_counter() - t0), file=sys.stderr)
            print(res.report.format(), file=sys.stderr)
            for w in res.warnings[:10]:
                print('  warning: ' + w, file=sys.stderr)
    return 1 if failed else 0
