"""WordprocessingML tree -> Markdown (single pass, lxml only)."""
import base64
import mimetypes
import posixpath
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from . import altchunk, omml
from .numbering import Numbering
from .package import DocError
from .report import Report
from .styles import Styles, parse_rpr
from .xmlns import *

# inline format bit flags
F_B, F_I, F_S, F_U, F_SUP, F_SUB, F_CODE, F_MARK = 1, 2, 4, 8, 16, 32, 64, 128
RAW = -1  # item already rendered Markdown
STRICT = False  # tests set True so converter bugs surface instead of degrading to plain text

_TRANS = str.maketrans({0xA0: ' ', 0xAD: None, 0x200B: None, 0xFEFF: None,
                        0xF0B7: '•', 0xF0A7: '▪', 0xF0D8: '➢', 0xF0FC: '✓', 0xF0A8: '☐'})
_WINGDINGS = {0xA8: '☐', 0xFE: '☑', 0xFD: '☒', 0xFC: '✓', 0xFB: '✗', 0xA7: '▪', 0x6C: '●', 0x6E: '■',
              0xD8: '➢', 0xE0: '→', 0xE8: '→', 0xF0: '⇨', 0x9F: '•', 0xA1: '○', 0x71: '❑'}
_SYMBOL = {0xB7: '•', 0xAE: '→', 0xAC: '←', 0xB1: '±', 0xB0: '°', 0xA3: '≤', 0xB3: '≥', 0xB9: '≠', 0xA5: '∞'}
_SKIP_FIELDS = frozenset(('PAGE', 'PAGEREF', 'NUMPAGES', 'NUMWORDS', 'NUMCHARS', 'SECTIONPAGES', 'SECTION',
                          'XE', 'TC', 'PRINTDATE', 'SAVEDATE', 'EDITTIME', 'LASTSAVEDBY'))
_BLOCK_PASS = frozenset((SDTCONTENT, INS, MOVETO, CUSTOMXML, SMARTTAG))
_INLINE_PASS = frozenset((INS, MOVETO, SMARTTAG, CUSTOMXML, BDO, DIR, SDTCONTENT))

_ESC = re.compile(r'[\\`*\[\]~$]|<(?=[A-Za-z/!?])|&(?=#?\w+;)|(?<![0-9A-Za-z])_|_(?![0-9A-Za-z])')
_LS = re.compile(r'(?m)^(?:(#{1,6}|[-+])(?=\s|$)|(>)|(\d{1,9})([.)])(?=\s|$)|([-=]{2,})[ \t]*$)')
_ANCHOR_PH = re.compile(r'\(#\x00([^\x00]*)\x00\)')
_PAGE_NO = re.compile(r'\t+\s*[0-9ivxlcIVXLC]+\s*$')
_TYPED_LI = re.compile(r'^(?:([•·▪●○■□◦‣▫➢\-–*])|(\d{1,3})[.)])[ \t]+(?=\S)')
_TOC_LEVELS = re.compile(r'\\o\s+"(\d)-(\d)"')
_MD_IMG_TAG = re.compile(r'!\[[^\]]*\]\([^)]*\)|<[^>]+>')
_MD_LINK = re.compile(r'\[([^\]]*)\]\([^)]*\)')
_IND = W + 'ind'
_ALIGN = {'center': 'c', 'right': 'r', 'end': 'r'}


def _int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _ls_fix(m):
    if m.group(3):
        return m.group(3) + '\\' + m.group(4)
    return '\\' + m.group()


def esc(s):
    return _ESC.sub(r'\\\g<0>', s)


def fix_line_starts(s):
    return _LS.sub(_ls_fix, s)


def _punct(c):
    return not c.isalnum() and not c.isspace()


def _code_span(s):
    s = s.replace('\n', ' ').replace('\t', ' ')
    longest = max((len(m) for m in re.findall(r'`+', s)), default=0)
    fence = '`' * (longest + 1)
    pad = ' ' if s.startswith('`') or s.endswith('`') else ''
    return fence + pad + s + pad + fence


def _fmt(text, mask, prev, nxt):
    if mask == 0:
        return esc(text)
    i = len(text) - len(text.lstrip(' \t'))
    j = len(text.rstrip(' \t'))
    core = text[i:j]
    if not core:
        return ' ' * len(text)
    if i:
        prev = ' '
    if j < len(text):
        nxt = ' '
    body = _code_span(core) if mask & F_CODE else esc(core)
    if mask & F_SUP:
        body = '<sup>' + body + '</sup>'
    elif mask & F_SUB:
        body = '<sub>' + body + '</sub>'
    if mask & F_U:
        body = '<u>' + body + '</u>'
    if mask & F_MARK:
        body = '<mark>' + body + '</mark>'
    if mask & (F_B | F_I | F_S):
        # CommonMark flanking rules: punctuation next to a letter breaks `**`; fall back to HTML tags
        bad = (_punct(body[0]) and prev.isalnum()) or (_punct(body[-1]) and nxt.isalnum())
        o = c = ''
        if mask & F_S:
            o, c = ('<del>', '</del>') if bad else ('~~', '~~')
        if mask & F_B:
            o, c = o + ('<strong>' if bad else '**'), ('</strong>' if bad else '**') + c
        if mask & F_I:
            o, c = o + ('<em>' if bad else '*'), ('</em>' if bad else '*') + c
        body = o + body + c
    return text[:i] + body + text[j:]


def render(items, br='\\\n'):
    parts = []
    n = len(items)
    for k, (t, m) in enumerate(items):
        if m == RAW:
            parts.append(t)
            continue
        prev = parts[-1][-1:] if parts and parts[-1] else ' '
        nxt = items[k + 1][0][:1] if k + 1 < n and items[k + 1][0] else ' '
        if '\t' in t and not m & F_CODE:
            t = t.replace('\t', ' ')
        if '\n' in t:
            segs = t.split('\n')
            parts.append(br.join(_fmt(s if q == 0 else s.lstrip(' '), m, prev, nxt) for q, s in enumerate(segs)))
        else:
            parts.append(_fmt(t, m, prev, nxt))
    return ''.join(parts)


def _trim(items):
    while items and items[0][1] != RAW and not items[0][0].strip(' \t\n'):
        items.pop(0)
    while items and items[-1][1] != RAW and not items[-1][0].strip(' \t\n'):
        items.pop()
    if items and items[0][1] != RAW:
        items[0][0] = items[0][0].lstrip(' \t\n')
    if items and items[-1][1] != RAW:
        items[-1][0] = items[-1][0].rstrip(' \t\n')


def _add(items, s, mask):
    if s:
        if items and items[-1][1] == mask:
            items[-1][0] += s
        else:
            items.append([s, mask])


def _url(u):
    return (u.strip().replace('\\', '/').replace(' ', '%20').replace('(', '%28').replace(')', '%29')
            .replace('<', '%3C').replace('>', '%3E').replace('\n', '').replace('\r', ''))


def plain_text(md):
    s = _MD_LINK.sub(r'\1', _MD_IMG_TAG.sub('', md))
    return re.sub(r'[*`~]', '', re.sub(r'\\(.)', r'\1', s)).strip()


def slugify(text):
    return re.sub(r'[^\w\- ]', '', text.lower().strip()).replace(' ', '-')


def _fence(text):
    text = text.strip('\n')
    longest = max((len(m) for m in re.findall(r'`+', text)), default=0)
    f = '`' * max(3, longest + 1)
    return '%s\n%s\n%s' % (f, text, f)


def _quote(text):
    return '\n'.join('> ' + l if l else '>' for l in text.split('\n'))


def join_blocks(blocks):
    merged = []
    for b in blocks:
        k = b[0]
        if k == 'skip':
            continue
        if merged and k in ('code', 'quote') and merged[-1][0] == k:
            merged[-1] = [k, merged[-1][1] + ('\n' if k == 'code' else '\n\n') + b[1], None]
        else:
            merged.append(b)
    parts, prev, top = [], None, None
    for blk in merged:
        k, text = blk[0], blk[1]
        sep = '\n\n'
        if k == 'li':
            if text[0] != ' ':                       # list type switch at top level -> new list
                kind = text[0] == '-'
                if prev == 'li' and kind == top:
                    sep = '\n'
                top = kind
            elif prev == 'li':
                sep = '\n'
        elif k == 'code':
            text = _fence(text)
        elif k == 'quote':
            text = _quote(text)
        elif k == 'hr':
            text = '---'
        if prev is not None:
            parts.append(sep)
        parts.append(text)
        prev = k
    return ''.join(parts)


class _Field:
    __slots__ = ('instr', 'sep', 'kind', 'start', 'url')

    def __init__(self):
        self.instr, self.sep, self.kind, self.start, self.url = [], False, None, 0, None


@dataclass(frozen=True)
class _ListLevel:
    """The current Markdown list item at one nesting depth."""

    depth: int
    marker_width: int
    num_id: Optional[int]
    marker_kind: str
    number: int


class Result:
    def __init__(self, markdown, images, report):
        self.markdown, self.images, self.report = markdown, images, report


class Converter:
    def __init__(self, pkg, media_dir='media', embed_images=False):
        self.pkg = pkg
        self.main = pkg.main
        self.root = pkg.xml(self.main)
        if self.root is None or self.root.tag != DOCUMENT:
            raise DocError('main document part is missing or not WordprocessingML (strict OOXML is unsupported)')
        self.rels = pkg.rels(self.main)
        self.current_part = self.main
        self.styles = Styles(pkg.xml(pkg.related(self.main, 'styles')))
        self.numbering = Numbering(pkg.xml(pkg.related(self.main, 'numbering')), self.styles)
        self._numbering_warnings = set()
        self.media_dir, self.embed = media_dir, embed_images
        self.rep = Report()
        self.images = {}
        self._img_src = {}
        self.footnotes_part, self.fn_el = self._notes('footnotes', FOOTNOTE)
        self.endnotes_part, self.en_el = self._notes('endnotes', ENDNOTE)
        self.fn_label, self.fn_queue = {}, []
        self.fields, self.suppress, self.links = [], 0, 0
        self.lstack, self.pending, self.toc_new, self.toc_cur, self.toc_all = [], [], [], None, []
        self.toc_plain = []
        self.headings, self.slugs, self.bm, self.last_slug, self.cur_bms = [], {}, {}, None, []
        self._disp = {R_: self._h_run, HYPERLINK: self._h_link, FLDSIMPLE: self._h_fldsimple,
                      SDT: self._h_sdt, BOOKMARKSTART: self._h_bookmark, M_OMATH: self._h_omath,
                      M_OMATHPARA: self._h_omathpara, MC_ALT: self._h_alt_inline, DEL: self._h_deleted,
                      MOVEFROM: self._h_deleted}

    # ------------------------------------------------------------------ driver
    def run(self):
        body = self.root.find(BODY)
        if body is None:
            raise DocError('document has no body')
        blocks = []
        self.blocks_of(body, blocks)
        self._fill_tocs()
        self._link_plain_toc_entries()
        md = join_blocks(blocks)
        notes = self._footnotes()
        if notes:
            md += '\n\n' + notes
        md = _ANCHOR_PH.sub(lambda m: '(#%s)' % self.bm.get(m.group(1), slugify(m.group(1))), md)
        c = self.pkg.xml(self.pkg.related(self.main, 'comments'))
        if c is not None:
            self.rep.lost('comments', len(c))
        return Result(md.strip('\n') + '\n', self.images, self.rep)

    def _notes(self, kind, tag):
        part = self.pkg.related(self.main, kind)
        root = self.pkg.xml(part)
        notes = {} if root is None else {note.get(ID): note for note in root.iterfind(tag)}
        return part, notes

    @contextmanager
    def _use_part(self, part):
        """Resolve links and images against the part that owns their relationship IDs."""
        previous_part, previous_relationships = self.current_part, self.rels
        self.current_part, self.rels = part, self.pkg.rels(part)
        try:
            yield
        finally:
            self.current_part, self.rels = previous_part, previous_relationships

    # ------------------------------------------------------------------ blocks
    def blocks_of(self, parent, out):
        for ch in parent:
            t = ch.tag
            if t == P:
                self.paragraph(ch, out)
            elif t == TBL:
                self.table(ch, out)
            elif t in (M_OMATH, M_OMATHPARA):
                self.lstack = []
                equation = self._equation(ch, display=True)
                if equation:
                    out.append(['p', equation, None])
            elif t == ALTCHUNK:
                self._imported_content(ch, out)
            elif t == SDT:
                c = ch.find(SDTCONTENT)
                if c is not None:
                    self.blocks_of(c, out)
            elif t in _BLOCK_PASS:
                self.blocks_of(ch, out)

    def sub_blocks(self, parent):
        saved, self.lstack = self.lstack, []
        out = []
        try:
            self.blocks_of(parent, out)
        finally:
            self.lstack = saved
        return out

    def _imported_content(self, element, out):
        """Keep imported text in place and make every unsupported import visible."""
        self.lstack = []
        relationship = self.rels.get(element.get(R_ID))
        if relationship is None:
            self._unconverted_import(out, 'The import relationship is missing.')
            return
        target, external, relationship_type = relationship
        if external or not relationship_type.lower().endswith('/afchunk'):
            self._unconverted_import(out, 'The import must reference an internal alternative-format part.')
            return
        data = self.pkg.read(target)
        if data is None:
            self._unconverted_import(out, 'The imported part is missing: %s.' % target)
            return
        content_type = self.pkg.content_type(target) or mimetypes.guess_type(target)[0] or ''
        try:
            text, approximate = altchunk.extract_text(data, content_type)
        except altchunk.ImportedContentError as error:
            self._unconverted_import(out, str(error), part=target)
            return
        if text.strip():
            out.append(['p', fix_line_starts(esc(text.strip())), None])
        if approximate:
            self.rep.part('imported HTML (text only)')
            self.rep.warn('imported-html-as-text',
                          'HTML text was preserved; formatting, link targets and embedded media were not.',
                          part=target)
        else:
            self.rep.ok('imported plain text')

    def _unconverted_import(self, out, reason, *, part=None):
        out.append(['p', '*[Imported content could not be converted]*', None])
        self.rep.lost('unconverted imported content')
        self.rep.warn('unconverted-import', reason, part=part or self.current_part)

    def paragraph(self, p, out):
        saved = self.pending
        try:
            self._paragraph(p, out)
        except Exception:
            if STRICT:
                raise
            self.pending = saved
            self._degrade(p, out)

    def _degrade(self, el, out):
        """Unexpected structure: keep the text, drop the formatting, never lose the document."""
        self.fields, self.suppress, self.links, self.lstack, self.toc_new = [], 0, 0, [], []
        text = ' '.join(''.join(el.itertext()).split())
        if text:
            out.append(['p', esc(text), None])
        self.rep.lost('blocks degraded to plain text')
        self.rep.warn('plain-text-fallback',
                      'An unexpected conversion error forced this block to plain text.',
                      part=self.current_part)

    def _paragraph(self, p, out):
        sid = numid = ilvl = outline = left = None
        border = False
        ppr = p.find(PPR)
        if ppr is not None:
            for e in ppr:
                t = e.tag
                if t == PSTYLE:
                    sid = e.get(VAL)
                elif t == NUMPR:
                    for n in e:
                        if n.tag == NUMID:
                            numid = _int(n.get(VAL), 0)
                        elif n.tag == ILVL:
                            ilvl = _int(n.get(VAL), 0)
                elif t == OUTLINELVL:
                    v = _int(e.get(VAL), 9)
                    outline = v + 1 if v < 9 else 0
                elif t == _IND:
                    left = _int(e.get(W + 'left', e.get(W + 'start')), None)
                elif t == PBDR:
                    border = e.find(W + 'bottom') is not None or e.find(W + 'top') is not None
        info = self.styles.para(sid)
        level = outline if outline is not None else info.level
        heading = bool(level)
        title = info.kind in ('title', 'tocheading') and not heading
        if numid is None:
            numid = info.numid
        if ilvl is None and numid:
            ilvl = info.ilvl if info.ilvl is not None else self.numbering.style_level(info.numstyle or sid, numid)
        ilvl = ilvl or 0

        saved_pending, self.pending = self.pending, []
        self.cur_bms = bms = []
        items = []
        self.inline(p, items, sid, (F_B if (heading or title) else 0) |
                    (F_I if info.kind == 'quote' else 0), False)
        for f in self.fields:                       # field-links never outlive their paragraph
            if f.kind == 'link' and f.sep:
                self._wrap_link(f, items)
                f.kind, self.links = 'dead', self.links - 1
        if self.suppress:                           # unterminated PAGEREF-like field: do not eat the doc
            self.fields = [f for f in self.fields if f.kind != 'skip']
            self.suppress = 0
        extras, self.pending = self.pending, saved_pending
        if self.toc_new:
            out.extend(self.toc_new)
            self.toc_new = []

        numbering = None
        if numid and not info.toc:
            numbering = self.numbering.step(numid, ilvl)
            if numbering is None:
                self._warn_numbering('missing-numbering',
                                     f'List {numid}, level {ilvl + 1} has no definition; paragraph text was retained.',
                                     numid, ilvl, lost=True)
            elif numbering.unsupported_formats:
                formats = ', '.join(numbering.unsupported_formats)
                self._warn_numbering('unsupported-numbering-format',
                                     f'Number formats {formats} were approximated with decimal values.', numid, ilvl)

        # --- code (decided on untrimmed text so indentation survives)
        if items and all(m != RAW for _, m in items) and (
                info.kind == 'code' and not heading or
                (any(m & F_CODE for _, m in items) and all(m & F_CODE or not t.strip() for t, m in items))):
            raw = ''.join(t for t, _ in items).lstrip('\n').rstrip()
            self.lstack = []
            out.append(['code', '\n'.join(l.rstrip() for l in raw.split('\n')), None])
            self.rep.ok('code blocks')
        elif not items and info.kind == 'code' and not heading and not info.toc:
            self.lstack = []
            out.append(['code', '', None])
        else:
            _trim(items)
            self._text_block(p, items, bms, out, info, level, heading, title, numbering, left, border,
                             allow_typed_list=numid is None)
        out.extend(extras)

    def _text_block(self, p, items, bms, out, info, level, heading, title, numbering, left, border,
                   *, allow_typed_list=True):
        toc_level = info.toc or (1 if self.toc_cur is not None and not heading else 0)
        if toc_level:
            if items and items[-1][1] != RAW:
                items[-1][0] = _PAGE_NO.sub('', items[-1][0])
            text = re.sub(r'\s+', ' ', render(items, ' ')).strip()
            if text:
                prefix = '  ' * (min(toc_level, 9) - 1)
                blk = ['li', prefix + '- ' + text, text]
                out.append(blk)
                if '](' not in text:                       # TOC without \h: link by matching heading text
                    self.toc_plain.append((blk, prefix, text))
                if self.toc_cur is not None:
                    self.toc_cur[3] = True
                self.rep.ok('toc entries')
            return
        if not items:
            if border:
                self.lstack = []
                out.append(['hr', '', None])
                self.rep.ok('horizontal rules')
            return

        if heading:
            text = re.sub(r'\s+', ' ', render(items, ' ')).strip()
            if numbering is not None and numbering.label:
                text = esc(numbering.label) + ' ' + text
            lvl = min(level, 6)
            slug = self._unique_slug(slugify(plain_text(text)))
            self.headings.append((level, plain_text(text), slug))
            for name in bms:
                self.bm[name] = slug
            self.last_slug = slug
            self.lstack = []
            out.append(['h', '#' * lvl + ' ' + text, lvl])
            self.rep.ok('headings')
            return
        for name in bms:
            if self.last_slug:
                self.bm[name] = self.last_slug

        if title:
            text = re.sub(r'\s+', ' ', render(items, ' ')).strip()
            self.lstack = []
            out.append(['h', '# ' + text, 1])
            self.rep.ok('headings')
            return

        typed = None
        if allow_typed_list and numbering is None and info.kind is None and items[0][1] != RAW:
            m = _TYPED_LI.match(items[0][0])
            if m:
                items[0][0] = items[0][0][m.end():]
                typed = (True, 0) if m.group(1) else (False, int(m.group(2)))
        text = fix_line_starts(render(items))
        if numbering is not None and numbering.has_marker:
            self._word_list_item(out, text, numbering)
            return
        if typed:
            bullet, number = typed
            self._li(out, text, bullet, number, left if left is not None else 360)
            return
        self.lstack = []
        if info.kind == 'quote':
            out.append(['quote', text, None])
            self.rep.ok('block quotes')
        elif info.kind == 'subtitle' and not text.startswith('*'):
            out.append(['p', '*' + text + '*', None])
        else:
            out.append(['p', text, None])

    def _warn_numbering(self, code, message, num_id, level, *, lost=False):
        """Report each affected definition once per document part, not once per item."""
        key = (code, num_id, level, self.current_part)
        if key in self._numbering_warnings:
            return
        self._numbering_warnings.add(key)
        if lost:
            self.rep.lost('list numbering')
        else:
            self.rep.part('list numbering')
        self.rep.warn(code, message, part=self.current_part)

    def _word_list_item(self, out, text, numbering):
        bullet = numbering.is_bullet
        delimiter = '.'
        if not bullet:
            decimal_labels = (f'{numbering.value}.', f'{numbering.value})')
            if numbering.label in decimal_labels and 0 <= numbering.value <= 999999999:
                delimiter = numbering.label[-1]
            else:
                # CommonMark only supports decimal list markers. Keep other labels
                # visible as text inside bullet items instead of silently changing them.
                text = fix_line_starts(esc(numbering.label)) + ' ' + text
                bullet = True
                self._warn_numbering('numbering-label-as-text',
                                     'List labels unsupported by Markdown were retained as text in bullet items.',
                                     numbering.num_id, numbering.level)
        self._li(out, text, bullet, numbering.value, numbering.level,
                 num_id=numbering.num_id, delimiter=delimiter)

    def _li(self, out, text, bullet, number, depth, *, num_id=None, delimiter='.'):
        stack = self.lstack
        # Typed bullets use physical indentation; Word lists use their logical ilvl.
        source_changed = bool(stack) and (stack[-1].num_id is None) != (num_id is None)
        if source_changed:
            stack.clear()
        while stack and stack[-1].depth > depth:
            stack.pop()
        previous = stack.pop() if stack and stack[-1].depth == depth else None
        indent = sum(level.marker_width for level in stack)
        marker_kind = '-' if bullet else delimiter
        separate = False
        if previous is not None and previous.marker_kind == marker_kind:
            different_list = previous.num_id != num_id
            number_jumped = not bullet and number != previous.number + 1
            separate = different_list or number_jumped
        # Without a separator, Markdown merges adjacent lists and ignores restarts.
        # A nested ordered list starting above/below 1 also needs a paragraph break.
        nested_start = previous is None and bool(stack) and not bullet and number != 1
        if source_changed or separate or nested_start:
            out.append(['list_break', ' ' * indent + '<!-- -->', None])
        if (not stack and previous is None) or separate:
            self.rep.ok('lists')
        marker = '- ' if bullet else f'{number}{delimiter} '
        stack.append(_ListLevel(depth, len(marker), num_id, marker_kind, number))
        body = text.replace('\n', '\n' + ' ' * (indent + len(marker)))
        cell_text = text if bullet else marker + text
        out.append(['li', ' ' * indent + marker + body, cell_text])

    def _unique_slug(self, base):
        n = self.slugs.get(base, 0)
        self.slugs[base] = n + 1
        return base if n == 0 else '%s-%d' % (base, n)

    # ------------------------------------------------------------------ TOC
    def _link_plain_toc_entries(self):
        by = {}
        for _, plain, slug in self.headings:
            by.setdefault(' '.join(plain.lower().split()), []).append(slug)
        for blk, prefix, text in self.toc_plain:
            slugs = by.get(' '.join(plain_text(text).lower().split()))
            if slugs:
                blk[1] = '%s- [%s](#%s)' % (prefix, text, slugs.pop(0))

    def _fill_tocs(self):
        for blk in self.toc_all:
            if blk[3] or blk[1]:
                blk[0] = 'skip'
                continue
            lo, hi = blk[2]
            lines = ['%s- [%s](#%s)' % ('  ' * (l - lo), t, s) for l, t, s in self.headings if lo <= l <= hi and t]
            if lines:
                blk[0], blk[1] = 'li', '\n'.join(lines)
                self.rep.ok('toc generated from headings')
            else:
                blk[0] = 'skip'

    # ------------------------------------------------------------------ tables
    def table(self, tbl, out):
        saved = self.pending
        try:
            self._table(tbl, out)
        except Exception:
            if STRICT:
                raise
            self.pending = saved
            self._degrade(tbl, out)

    def _table(self, tbl, out):
        trs = [r for r in tbl if r.tag == TR]
        if not trs:
            return
        if len(trs) == 1:
            tcs = [c for c in trs[0] if c.tag == TC]
            if len(tcs) == 1:
                self.rep.ok('single-cell boxes (unwrapped)')
                self.lstack = []
                out.extend(self.sub_blocks(tcs[0]))
                return
        rows, aligns = [], []
        body_row = 1 if len(trs) > 1 else 0
        for ri, tr in enumerate(trs):
            cells = []
            for tc in tr:
                if tc.tag != TC:
                    continue
                span, cont, vm = 1, False, None
                pr = tc.find(TCPR)
                if pr is not None:
                    gs = pr.find(GRIDSPAN)
                    if gs is not None:
                        span = max(1, _int(gs.get(VAL), 1))
                    vm = pr.find(VMERGE)
                    cont = vm is not None and vm.get(VAL) != 'restart'
                if span > 1 or vm is not None:
                    self.rep.part('merged table cells')
                cells.append('' if cont else self._cell(tc))
                cells.extend([''] * (span - 1))
                if ri == body_row:
                    aligns.append(self._align(tc))
                    aligns.extend([''] * (span - 1))
            rows.append(cells)
        ncols = max(len(r) for r in rows)
        if not ncols or not any(c for r in rows for c in r):
            return
        for r in rows:
            r.extend([''] * (ncols - len(r)))
        aligns.extend([''] * (ncols - len(aligns)))
        widths = []
        for j in range(ncols):
            w = max(len(r[j]) for r in rows)
            widths.append(max(w, 3) if w <= 40 else 0)

        def row(cells):
            return '| ' + ' | '.join(c.ljust(widths[j]) for j, c in enumerate(cells)) + ' |'

        sep = []
        for j in range(ncols):
            w = max(widths[j], 3)
            a = aligns[j]
            sep.append((':' + '-' * (w - 2) + ':') if a == 'c' else ('-' * (w - 1) + ':') if a == 'r' else '-' * w)
        md = '\n'.join([row(rows[0]), '| ' + ' | '.join(sep) + ' |'] + [row(r) for r in rows[1:]])
        flat = '<br>'.join(' · '.join(c for c in r if c) for r in rows)
        self.lstack = []
        out.append(['table', md, flat])
        self.rep.ok('tables')

    @staticmethod
    def _align(tc):
        p = tc.find(P)
        ppr = p.find(PPR) if p is not None else None
        jc = ppr.find(JC) if ppr is not None else None
        return _ALIGN.get(jc.get(VAL), '') if jc is not None else ''

    def _cell(self, tc):
        lines = []
        for k, text, aux in self.sub_blocks(tc):
            if k == 'h':
                lines.append('**%s**' % text.lstrip('#').strip())
            elif k == 'li':
                lines.append('• ' + aux)
            elif k == 'code':
                if text.strip():
                    lines.append(_code_span(text.strip('\n')))
            elif k == 'table':
                lines.append(aux)
            elif k not in ('hr', 'list_break'):
                lines.append(text)
        s = '<br>'.join(lines).replace('\\\n', '<br>').replace('\n', '<br>')
        return s.replace('|', '\\|')

    # ------------------------------------------------------------------ inline
    def inline(self, el, items, ps, drop, in_link):
        disp = self._disp
        for ch in el:
            t = ch.tag
            h = disp.get(t)
            if h is not None:
                h(ch, items, ps, drop, in_link)
            elif t in _INLINE_PASS:
                self.inline(ch, items, ps, drop, in_link)

    def _h_bookmark(self, el, items, ps, drop, in_link):
        n = el.get(NAME)
        if n:
            self.cur_bms.append(n)

    def _h_deleted(self, el, items, ps, drop, in_link):
        self.rep.ok('tracked changes (accepted)')

    def _h_sdt(self, el, items, ps, drop, in_link):
        c = el.find(SDTCONTENT)
        if c is not None:
            self.inline(c, items, ps, drop, in_link)

    def _h_omath(self, el, items, ps, drop, in_link):
        equation = self._equation(el)
        if equation:
            items.append([equation, RAW])

    def _h_omathpara(self, el, items, ps, drop, in_link):
        equation = self._equation(el, display=True)
        if equation:
            self.pending.append(['p', equation, None])

    def _equation(self, element, *, display=False):
        """Share math rendering and loss accounting between inline and block content."""
        equations = element.iter(M_OMATH) if element.tag == M_OMATHPARA else [element]
        parts = [omml.to_latex(equation) for equation in equations]
        latex = ' \\\\\n'.join(part for part in parts if part)
        unsupported = omml.unsupported_elements(element)
        if unsupported:
            if latex:
                self.rep.part('equations')
            else:
                self.rep.lost('equations')
            self.rep.warn('unsupported-math',
                          'Unsupported equation constructs: %s. Only convertible content was retained.' %
                          ', '.join(unsupported), part=self.current_part)
        elif latex:
            self.rep.ok('equations')
        if not latex:
            return '*[Equation could not be converted]*' if unsupported else ''
        return '$$\n' + latex + '\n$$' if display else '$' + latex + '$'

    def _h_alt_inline(self, el, items, ps, drop, in_link):
        self._alt(el, items)

    def _h_fldsimple(self, el, items, ps, drop, in_link):
        instr = el.get(INSTR) or ''
        k = instr.split(None, 1)[0].upper() if instr.strip() else ''
        if k in _SKIP_FIELDS:
            return
        if k == 'HYPERLINK':
            inner = []
            self.inline(el, inner, ps, drop, True)
            self._link(items, inner, self._hyper_url(instr))
        else:
            self.inline(el, items, ps, drop, in_link)

    def _h_link(self, el, items, ps, drop, in_link):
        rid, anc = el.get(R_ID), el.get(ANCHOR)
        url = None
        if rid:
            rel = self.rels.get(rid)
            if rel and rel[0]:
                url = _url(rel[0]) + ('#' + anc if anc else '')
            else:
                self.rep.part('hyperlinks with missing targets')
                self.rep.warn('missing-hyperlink-target',
                              'Hyperlink %s has no target; its display text was retained.' % rid,
                              part=self.current_part)
        elif anc:
            url = '#\x00' + anc + '\x00'
        inner = []
        self.inline(el, inner, ps, drop, True)
        self._link(items, inner, url)

    def _link(self, items, inner, url):
        lead = inner and inner[0][1] != RAW and inner[0][0][:1] in ' \t\n'
        trail = inner and inner[-1][1] != RAW and inner[-1][0][-1:] in ' \t\n'
        _trim(inner)
        if not inner:
            return
        if lead:
            _add(items, ' ', 0)                    # whitespace belongs outside the [link]
        if not url:
            items.extend(inner)
        else:
            text = render(inner, ' ')
            if text.strip():
                items.append(['[%s](%s)' % (text, url), RAW])
                self.rep.ok('hyperlinks')
        if trail:
            _add(items, ' ', 0)

    def _wrap_link(self, f, items):
        inner = items[f.start:]
        del items[f.start:]
        self._link(items, inner, f.url)

    @staticmethod
    def _hyper_url(instr):
        q = re.findall(r'"([^"]*)"', instr)
        if '\\l' in instr:
            anchor = q[-1] if q else ''
            base = _url(q[0]) if len(q) > 1 else ''
            return base + '#' + anchor if base else '#\x00' + anchor + '\x00'
        if q:
            return _url(q[0])
        parts = instr.split()
        return _url(parts[1]) if len(parts) > 1 else None

    # --- runs
    def _h_run(self, r, items, ps, drop, in_link):
        direct = None
        if len(r):
            first = r[0]
            if first.tag == RPR:
                direct = parse_rpr(first)
        base = self.styles.rpr(ps, direct.get('rstyle') if direct else None)
        d = base if direct is None else {**base, **direct}
        hidden = d.get('vanish')
        m = 0
        if d.get('b'):
            m |= F_B
        if d.get('i'):
            m |= F_I
        if d.get('s'):
            m |= F_S
        if d.get('u') and not (in_link or self.links):
            m |= F_U
        va = d.get('va')
        if va == 'superscript':
            m |= F_SUP
        elif va == 'subscript':
            m |= F_SUB
        if d.get('mono'):
            m |= F_CODE
        if d.get('hl'):
            m |= F_MARK
        m &= ~drop
        buf = []
        for c in r:
            t = c.tag
            if t == T:
                if not (self.suppress or hidden) and c.text:
                    buf.append(c.text)
            elif t == TAB or t == PTAB:
                buf.append('\t')
            elif t == BR:
                buf.append('\n')                    # line, page and column breaks all become a line break
            elif t == CR:
                buf.append('\n')
            elif t == NOBREAKHYPHEN:
                buf.append('-')
            elif t == SYM:
                if not (self.suppress or hidden):
                    buf.append(self._sym(c))
            elif t == FLDCHAR or t == INSTRTEXT:
                if buf:
                    _add(items, ''.join(buf).translate(_TRANS), m)
                    buf = []
                if t == FLDCHAR:
                    self._fldchar(c, items)
                elif self.fields and not self.fields[-1].sep:
                    self.fields[-1].instr.append(c.text or '')
            elif t == DRAWING or t == PICT or t == OBJECT or t == MC_ALT:
                if self.suppress or hidden:
                    continue
                if buf:
                    _add(items, ''.join(buf).translate(_TRANS), m)
                    buf = []
                if t == MC_ALT:
                    self._alt(c, items)
                else:
                    self._graphic(c, items)
            elif t == FOOTNOTEREF or t == ENDNOTEREF:
                if self.suppress or hidden:
                    continue
                if buf:
                    _add(items, ''.join(buf).translate(_TRANS), m)
                    buf = []
                items.append(['[^%s]' % self._note_label(t == FOOTNOTEREF, c.get(ID)), RAW])
            elif t == COMMENTREF:
                pass
        if buf:
            _add(items, ''.join(buf).translate(_TRANS), m)

    @staticmethod
    def _sym(c):
        try:
            code = int(c.get(W + 'char'), 16)
        except (TypeError, ValueError):
            return ''
        font = (c.get(W + 'font') or '').lower()
        base = code & 0xFF if 0xF000 <= code <= 0xF0FF else code
        if 'wingdings' in font:
            return _WINGDINGS.get(base, '')
        if font == 'symbol':
            return _SYMBOL.get(base, '')
        return chr(code) if code < 0xF000 else ''

    # --- fields
    def _fldchar(self, c, items):
        ty = c.get(FLDCHARTYPE)
        if ty == 'begin':
            self.fields.append(_Field())
            cb = c.find(FFDATA)
            cb = cb.find(CHECKBOX) if cb is not None else None
            if cb is not None:
                st = cb.find(CHECKED)
                dft = cb.find(DEFAULT)
                on_ = (st is not None and st.get(VAL) != '0') or (st is None and dft is not None and dft.get(VAL) != '0')
                items.append(['☒' if on_ else '☐', RAW])
                self.rep.ok('checkboxes')
        elif ty == 'separate':
            if self.fields and not self.fields[-1].sep:
                self._open_result(self.fields[-1], items)
        elif ty == 'end' and self.fields:
            f = self.fields.pop()
            if not f.sep:
                self._open_result(f, items)
            if f.kind == 'skip':
                self.suppress -= 1
            elif f.kind == 'link':
                self._wrap_link(f, items)
                self.links -= 1
            elif f.kind == 'toc':
                self.toc_cur = None

    def _open_result(self, f, items):
        instr = ''.join(f.instr).strip()
        f.sep = True
        parts = instr.split(None, 1)
        k = parts[0].upper() if parts else ''
        if k in _SKIP_FIELDS:
            f.kind = 'skip'
            self.suppress += 1
        elif k == 'HYPERLINK':
            f.kind, f.url, f.start = 'link', self._hyper_url(instr), len(items)
            self.links += 1
        elif k == 'REF' and len(parts) > 1 and '\\h' in instr:
            f.kind, f.url, f.start = 'link', '#\x00' + parts[1].split()[0] + '\x00', len(items)
            self.links += 1
        elif k == 'TOC':
            f.kind = 'toc'
            m = _TOC_LEVELS.search(instr)
            blk = ['toc', '', (int(m.group(1)), int(m.group(2))) if m else (1, 3), False]
            self.toc_cur = blk
            self.toc_new.append(blk)
            self.toc_all.append(blk)
            self.rep.ok('table of contents')

    # --- footnotes
    def _note_label(self, is_fn, nid):
        key = (is_fn, nid)
        lab = self.fn_label.get(key)
        if lab is None:
            lab = self.fn_label[key] = str(len(self.fn_label) + 1)
            self.fn_queue.append((key, lab))
        return lab

    def _footnotes(self):
        definitions = []
        index = 0
        while index < len(self.fn_queue):
            (is_footnote, note_id), label = self.fn_queue[index]
            index += 1
            notes = self.fn_el if is_footnote else self.en_el
            part = self.footnotes_part if is_footnote else self.endnotes_part
            element = notes.get(note_id)
            if element is None:
                body = '*[Note content is missing]*'
                self.rep.lost('footnotes/endnotes with missing content')
                self.rep.warn('missing-note', 'Note %s has no readable definition.' % note_id,
                              part=part or self.main)
            else:
                with self._use_part(part):
                    body = join_blocks(self.sub_blocks(element)).strip()
                self.rep.ok('footnotes/endnotes')
            lines = body.split('\n')
            rest = ['    ' + line if line else '' for line in lines[1:]]
            definitions.append('[^%s]: %s' % (label, '\n'.join([lines[0]] + rest)))
        return '\n\n'.join(definitions)

    # ------------------------------------------------------------------ graphics
    def _alt(self, el, items):
        choice = el.find(MC_CHOICE)
        if choice is None:
            choice = el.find(MC_FALLBACK)
        if choice is not None:
            for g in choice:
                if g.tag in (DRAWING, PICT, OBJECT):
                    self._graphic(g, items)

    def _graphic(self, el, items):
        t = el.tag
        if t == DRAWING:
            alt = ''
            for d in el.iter(WP_DOCPR):
                alt = d.get('descr') or d.get('title') or ''
                break
            anchored = el.find(WP_ANCHOR) is not None      # floating: own block, not glued to text
            tmp = [] if anchored else items
            found = self._walk_draw(el, tmp, alt)
            if anchored:
                self.pending.extend(['p', i[0], None] for i in tmp)
            if not found:
                self.rep.lost('drawing shapes without text/image')
        else:
            if t == OBJECT:
                self.rep.part('embedded objects (preview image only)')
            self._walk_vml(el, items, '')

    def _walk_draw(self, el, items, alt):
        found = False
        for ch in el:
            t = ch.tag
            if t == A_BLIP:
                if ch.getparent().tag == PIC_BLIPFILL:
                    self._image(ch.get(R_EMBED) or ch.get(R_LINK), alt, items)
                    found = True
            elif t == TXBXCONTENT:
                self.pending.extend(self.sub_blocks(ch))
                self.rep.ok('text boxes')
                found = True
            elif t == C_CHART:
                items.append(['*[Chart%s]*' % (': ' + esc(alt) if alt else ''), RAW])
                self.rep.lost('charts')
                found = True
            elif t == DGM_RELIDS:
                self._smartart(ch, items)
                found = True
            elif t == MC_ALT:
                choice = ch.find(MC_CHOICE)
                if choice is not None:
                    found |= self._walk_draw(choice, items, alt)
            elif isinstance(t, str) and len(ch):
                found |= self._walk_draw(ch, items, alt)
        return found

    def _smartart(self, el, items):
        rel = self.rels.get(el.get(R + 'dm'))
        texts = []
        if rel and not rel[1]:
            root = self.pkg.xml(rel[0])
            if root is not None:
                texts = [t.text.strip() for t in root.iter(A + 't') if t.text and t.text.strip()]
        if texts:
            items.append(['*[Diagram: %s]*' % esc('; '.join(texts)), RAW])
            self.rep.part('SmartArt (text only)')
        else:
            items.append(['*[Diagram]*', RAW])
            self.rep.lost('SmartArt')

    def _walk_vml(self, el, items, alt):
        for ch in el:
            t = ch.tag
            if t == V_IMAGEDATA:
                self._image(ch.get(R_ID) or ch.get(O_RELID), ch.get(O_TITLE) or alt, items)
            elif t == TXBXCONTENT:
                self.pending.extend(self.sub_blocks(ch))
                self.rep.ok('text boxes')
            elif isinstance(t, str) and len(ch):
                if ch.get(O_HR):
                    self.pending.append(['hr', '', None])
                    self.rep.ok('horizontal rules')
                self._walk_vml(ch, items, ch.get('alt') or alt)
            elif isinstance(t, str) and ch.get(O_HR):
                self.pending.append(['hr', '', None])
                self.rep.ok('horizontal rules')

    def _image(self, rid, alt, items):
        rel = self.rels.get(rid) if rid else None
        if rel is None:
            self.rep.lost('images with missing data')
            self.rep.warn('missing-image', 'Image relationship %s is missing.' % rid,
                          part=self.current_part)
            return
        target, external, _ = rel
        src = _url(target) if external else self._save_image(target)
        if src is None:
            self.rep.lost('images with missing data')
            self.rep.warn('missing-image', 'Image data is missing: %s.' % target,
                          part=self.current_part)
            return
        alt = re.sub(r'[\[\]\r\n]+', ' ', alt or '').strip() or 'image'
        items.append(['![%s](%s)' % (alt, src), RAW])
        self.rep.ok('images')

    def _save_image(self, target):
        src = self._img_src.get(target)
        if src is not None:
            return src
        data = self.pkg.read(target)
        if data is None:
            return None
        name = posixpath.basename(target)
        ext = posixpath.splitext(name)[1].lower()
        if ext in ('.emf', '.wmf'):
            data, name = self._raster(data, name)
        if self.embed:
            mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
            src = 'data:%s;base64,%s' % (mime, base64.b64encode(data).decode('ascii'))
        else:
            base, ext = posixpath.splitext(name)
            n = 1
            while name in self.images:
                n += 1
                name = '%s_%d%s' % (base, n, ext)
            self.images[name] = data
            src = quote(self.media_dir + '/' + name)
        self._img_src[target] = src
        return src

    @staticmethod
    def _raster(data, name):
        """EMF/WMF -> PNG when Pillow can (Windows only); otherwise keep the original bytes."""
        try:
            import io
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            im.load()
            buf = io.BytesIO()
            im.save(buf, 'PNG')
            return buf.getvalue(), posixpath.splitext(name)[0] + '.png'
        except Exception:
            return data, name


def convert_package(pkg, media_dir='media', embed_images=False):
    return Converter(pkg, media_dir, embed_images).run()
