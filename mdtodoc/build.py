"""Markdown (markdown-it-py tokens) -> .docx package, written directly as OOXML."""
import hashlib
import html
import io
import re
import zipfile
from urllib.parse import unquote
from xml.sax.saxutils import escape

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

from doctomd.convert import slugify
from doctomd.report import Report

from . import images, latex, parts

B, I, S, U, SUP, SUB, CODE, MARK, LINK = 1, 2, 4, 8, 16, 32, 64, 128, 256
_HTML_FMT = {'u': U, 'ins': U, 'sup': SUP, 'sub': SUB, 'mark': MARK, 'strong': B, 'b': B, 'em': I, 'i': I,
             'del': S, 's': S, 'strike': S, 'code': CODE, 'kbd': CODE, 'tt': CODE}
_TAG = re.compile(r'<\s*(/?)\s*([A-Za-z][A-Za-z0-9]*)')
_BAD = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]')
_PLAIN_TAGS = re.compile(r'<[^>]+>')
_CHECK = re.compile(r'^\[([ xX])\]\s+')
_BR = '<w:r><w:br/></w:r>'


def esc(s):
    return escape(_BAD.sub('', s))


def attr(s):
    return esc(s).replace('"', '&quot;')


def _parser():
    md = MarkdownIt('commonmark', {'html': True}).enable(['table', 'strikethrough'])
    md.use(front_matter_plugin).use(footnote_plugin).use(dollarmath_plugin, allow_space=True, double_inline=True)
    return md


_MD = _parser()


class Result:
    def __init__(self, data, report, warnings):
        self.data, self.report, self.warnings = data, report, warnings


class Builder:
    def __init__(self, base_dir='.', page='a4'):
        self.base_dir = base_dir
        pw, _ = parts.PAGES[page]
        self.page = page
        self.text_twips = pw - 2 * parts.MARGIN
        self.text_w = self.text_twips * 635                     # EMU
        self.maxw = self.text_w
        self.rep, self.warnings = Report(), []
        self.rels, self._rel_ids = [], {}
        self.media, self._media_ids, self.exts = {}, {}, set()
        self.nums, self.next_num = [], 2
        self.fn_defs, self.fn_used = [], set()
        self.in_note, self.prefix = False, ''
        self.bm_id, self.docpr_id = 0, 0
        self.anchors, self.heading_bm = {}, {}
        self.title = ''

    # ------------------------------------------------------------------ driver
    def build(self, text):
        self.toks = toks = _MD.parse(text)
        self.match, stack = {}, []
        for idx, t in enumerate(toks):
            if t.nesting == 1:
                stack.append(idx)
            elif t.nesting == -1 and stack:
                self.match[stack.pop()] = idx
        self._scan_headings()
        body = self.blocks(0, len(toks), (-1, 0))
        if body.endswith('</w:tbl>') or not body:
            body += '<w:p/>'
        pw, ph = parts.PAGES[self.page]
        sect = ('<w:sectPr><w:pgSz w:w="%d" w:h="%d"/><w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" '
                'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>' % (pw, ph, parts.MARGIN, parts.MARGIN,
                                                                           parts.MARGIN, parts.MARGIN))
        doc = parts.HEAD + '<w:document %s><w:body>%s%s</w:body></w:document>' % (parts.NS, body, sect)
        has_fn = bool(self.fn_defs)
        rels = list(self.rels)
        if has_fn:
            rels.append(('rIdF', 'footnotes', 'footnotes.xml', False))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('[Content_Types].xml', parts.content_types(self.exts, has_fn))
            z.writestr('_rels/.rels', parts.root_rels())
            z.writestr('word/document.xml', doc)
            z.writestr('word/_rels/document.xml.rels', parts.doc_rels(rels))
            z.writestr('word/styles.xml', parts.styles_xml())
            z.writestr('word/numbering.xml', parts.numbering_xml(self.nums))
            z.writestr('word/settings.xml', parts.settings_xml(has_fn))
            z.writestr('docProps/core.xml', parts.core_xml(self.title))
            if has_fn:
                z.writestr('word/footnotes.xml', parts.footnotes_xml(self.fn_defs))
            for name, data in self.media.items():
                z.writestr('word/media/' + name, data)
        return Result(buf.getvalue(), self.rep, self.warnings)

    def _scan_headings(self):
        seen = {}
        for i, t in enumerate(self.toks):
            if t.type == 'heading_open':
                inl = self.toks[i + 1]
                txt = ''.join(c.content for c in inl.children if c.type in ('text', 'code_inline'))
                if not self.title:
                    self.title = txt
                base = slugify(txt)
                n = seen.get(base, 0)
                seen[base] = n + 1
                slug = base if n == 0 else '%s-%d' % (base, n)
                name = '_md%d' % len(self.heading_bm)
                self.heading_bm[i] = name
                self.anchors[slug] = name

    # ------------------------------------------------------------------ blocks
    def blocks(self, i, j, ctx):
        out = []
        while i < j:
            i = self.block_at(i, ctx, out)
        return ''.join(out)

    def block_at(self, i, ctx, out):
        toks, match = self.toks, self.match
        t = toks[i]
        ty = t.type
        if ty == 'paragraph_open':
            out.append(self.p_block(toks[i + 1], ctx))
            return match.get(i, i + 2) + 1
        if ty == 'heading_open':
            out.append(self.heading(i))
            return match.get(i, i + 2) + 1
        if ty in ('bullet_list_open', 'ordered_list_open'):
            out.append(self.list_(i, ctx))
            return match.get(i, i) + 1
        if ty == 'blockquote_open':
            self.rep.ok('block quotes')
            out.append(self.blocks(i + 1, match.get(i, i), (ctx[0], ctx[1] + 1)))
            return match.get(i, i) + 1
        if ty in ('fence', 'code_block'):
            out.append(self.code(t, ctx))
        elif ty == 'hr':
            out.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="A6A6A6"/></w:pBdr>'
                       '</w:pPr></w:p>')
            self.rep.ok('horizontal rules')
        elif ty == 'table_open':
            out.append(self.table(i, ctx))
            return match.get(i, i) + 1
        elif ty == 'html_block':
            self.html_block(t, out)
        elif ty in ('math_block', 'math_block_label'):
            out.append(self.math_block(t.content))
        elif ty == 'footnote_block_open':
            self.footnote_block(i)
            return match.get(i, i) + 1
        return i + 1

    def left(self, ctx):
        lvl, qd = ctx
        return (lvl + 1) * 720 + 567 * qd if (lvl >= 0 or qd) else 0

    @staticmethod
    def ppr(style=None, num=None, ind=None, jc=None, spacing=None, extra=''):
        s = ''
        if style:
            s += '<w:pStyle w:val="%s"/>' % style
        if num:
            s += '<w:numPr><w:ilvl w:val="%d"/><w:numId w:val="%d"/></w:numPr>' % num
        s += extra
        if spacing:
            s += spacing
        if ind:
            s += ind
        if jc:
            s += '<w:jc w:val="%s"/>' % jc
        return '<w:pPr>%s</w:pPr>' % s if s else ''

    def p_block(self, inl, ctx, numpr=None):
        left = self.left(ctx)
        self.maxw = max(self.text_w - left * 635, 720 * 635)
        runs = self.inline(inl.children)
        pre, self.prefix = self.prefix, ''
        if not runs and not pre and not numpr:
            return ''
        qd = ctx[1]
        style = ind = None
        if numpr:
            style = 'ListParagraph'
            if qd:
                ind = '<w:ind w:left="%d" w:hanging="360"/>' % left
        elif self.in_note and ctx[0] < 0 and not qd:
            style = 'FootnoteText'
        elif qd:
            style, ind = 'Quote', '<w:ind w:left="%d"/>' % left
        elif left:
            ind = '<w:ind w:left="%d"/>' % left
        return '<w:p>%s%s%s</w:p>' % (self.ppr(style, (numpr[0], numpr[1]) if numpr else None, ind), pre, runs)

    def heading(self, i):
        level = min(int(self.toks[i].tag[1:]), 6)
        self.maxw = self.text_w
        runs = self.inline(self.toks[i + 1].children)
        self.bm_id += 1
        name = self.heading_bm.get(i)
        bm = ('<w:bookmarkStart w:id="%d" w:name="%s"/>' % (self.bm_id, name), '<w:bookmarkEnd w:id="%d"/>' % self.bm_id)
        self.rep.ok('headings')
        return '<w:p><w:pPr><w:pStyle w:val="Heading%d"/></w:pPr>%s%s%s</w:p>' % (level, bm[0], runs, bm[1])

    def code(self, t, ctx):
        left = self.left(ctx)
        lines = t.content.rstrip('\n').split('\n')
        ind = '<w:ind w:left="%d"/>' % left if left else None
        out = []
        for k, line in enumerate(lines):
            sp = '<w:spacing w:after="160"/>' if k == len(lines) - 1 else None
            out.append('<w:p>%s%s</w:p>' % (self.ppr('Code', ind=ind, extra='', spacing=sp), self.run(line, 0)))
        self.rep.ok('code blocks')
        return ''.join(out)

    def html_block(self, t, out):
        c = t.content.strip()
        if c.startswith('<!--'):
            return
        text = html.unescape(_PLAIN_TAGS.sub('', c)).strip()
        if text:
            out.append('<w:p>%s</w:p>' % self.run(' '.join(text.split()), 0))
            self.rep.part('raw HTML blocks (tags stripped)')

    def math_block(self, tex):
        try:
            xml = latex.to_omml(tex)
            self.rep.ok('equations')
            return '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><m:oMathPara>%s</m:oMathPara></w:p>' % xml
        except Exception:
            self.rep.part('equations kept as LaTeX text')
            return '<w:p>%s</w:p>' % self.run(tex.strip(), CODE)

    # ------------------------------------------------------------------ lists
    def list_(self, i, ctx):
        toks, match = self.toks, self.match
        t = toks[i]
        end = match.get(i, i)
        ordered = t.type == 'ordered_list_open'
        lvl = ctx[0] + 1
        ilvl = min(lvl, 8)
        if ordered:
            numid = self.next_num
            self.next_num += 1
            self.nums.append((numid, ilvl, int(t.attrGet('start') or 1)))
        else:
            numid = 1
        self.rep.ok('lists')
        out, j = [], i + 1
        while j < end:
            if toks[j].type == 'list_item_open':
                ie = match.get(j, j)
                out.append(self.list_item(j + 1, ie, (lvl, ctx[1]), numid, ilvl))
                j = ie + 1
            else:
                j += 1
        return ''.join(out)

    def list_item(self, i, j, ctx, numid, ilvl):
        toks = self.toks
        out = []
        first = True
        while i < j:
            if first:
                first = False
                if toks[i].type == 'paragraph_open':
                    inl = toks[i + 1]
                    self._checkbox(inl)
                    out.append(self.p_block(inl, ctx, (ilvl, numid)) or
                               '<w:p>%s</w:p>' % self.ppr('ListParagraph', (ilvl, numid)))
                    i = self.match.get(i, i + 2) + 1
                    continue
                out.append('<w:p>%s</w:p>' % self.ppr('ListParagraph', (ilvl, numid)))   # item starts with a block
            i = self.block_at(i, ctx, out)
        return ''.join(out)

    @staticmethod
    def _checkbox(inl):
        ch = inl.children
        if ch and ch[0].type == 'text':
            m = _CHECK.match(ch[0].content)
            if m:
                ch[0].content = ('☐ ' if m.group(1) == ' ' else '☒ ') + ch[0].content[m.end():]

    # ------------------------------------------------------------------ tables
    def table(self, i, ctx):
        toks, end = self.toks, self.match.get(i, i)
        rows, row = [], None
        for k in range(i + 1, end):
            t = toks[k]
            if t.type == 'tr_open':
                row = []
                rows.append(row)
            elif t.type in ('th_open', 'td_open'):
                style = t.attrGet('style') or ''
                al = 'center' if 'center' in style else 'right' if 'right' in style else None
                row.append((toks[k + 1], al, t.type == 'th_open'))
        rows = [r for r in rows if r]
        if not rows:
            return ''
        ncols = max(len(r) for r in rows)
        weights = [6] * ncols
        for r in rows:
            for c, (inl, _, _) in enumerate(r):
                n = sum(len(x.content) for x in inl.children if x.type in ('text', 'code_inline'))
                weights[c] = max(weights[c], min(n, 50))
        left = self.left(ctx)
        total = self.text_twips - left
        widths = [max(int(total * w / sum(weights)), 500) for w in weights]
        out = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="%d" w:type="dxa"/>' % sum(widths)]
        if left:
            out.append('<w:tblInd w:w="%d" w:type="dxa"/>' % left)
        out.append('<w:tblLayout w:type="fixed"/><w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" '
                   'w:noHBand="0" w:noVBand="1"/></w:tblPr><w:tblGrid>%s</w:tblGrid>' %
                   ''.join('<w:gridCol w:w="%d"/>' % w for w in widths))
        for r in rows:
            header = r[0][2]
            out.append('<w:tr><w:trPr><w:cantSplit/>%s</w:trPr>' % ('<w:tblHeader/>' if header else ''))
            for c in range(ncols):
                inl, al, hd = r[c] if c < len(r) else (None, None, header)
                self.maxw = max(widths[c] * 635 - 216 * 635, 635 * 300)
                runs = self.inline(inl.children) if inl is not None else ''
                out.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/></w:tcPr><w:p>%s%s</w:p></w:tc>' % (
                    widths[c], self.ppr(spacing='<w:spacing w:before="40" w:after="40" w:line="240" '
                                                      'w:lineRule="auto"/>', jc=al), runs))
            out.append('</w:tr>')
        out.append('</w:tbl><w:p><w:pPr><w:spacing w:after="0" w:line="120" w:lineRule="exact"/></w:pPr></w:p>')
        self.rep.ok('tables')
        return ''.join(out)

    # ------------------------------------------------------------------ footnotes
    def footnote_block(self, i):
        toks, match = self.toks, self.match
        end, j = match.get(i, i), i + 1
        while j < end:
            if toks[j].type == 'footnote_open':
                je = match.get(j, j)
                fid = (toks[j].meta or {}).get('id', 0) + 1
                ref = '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>'
                self.in_note, self.prefix = True, ref + '<w:r><w:t xml:space="preserve"> </w:t></w:r>'
                body = self.blocks(j + 1, je, (-1, 0))
                self.in_note, self.prefix = False, ''
                if not body:
                    body = '<w:p>%s</w:p>' % ref
                self.fn_defs.append('<w:footnote w:id="%d">%s</w:footnote>' % (fid, body))
                j = je + 1
            else:
                j += 1

    # ------------------------------------------------------------------ inline
    def run(self, text, fmt):
        if not text:
            return ''
        rpr = ''
        if fmt & LINK:
            rpr += '<w:rStyle w:val="Hyperlink"/>'
            if fmt & CODE:
                rpr += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>'
        elif fmt & CODE:
            rpr += '<w:rStyle w:val="CodeChar"/>'
        if fmt & B:
            rpr += '<w:b/><w:bCs/>'
        if fmt & I:
            rpr += '<w:i/><w:iCs/>'
        if fmt & S:
            rpr += '<w:strike/>'
        if fmt & MARK:
            rpr += '<w:highlight w:val="yellow"/>'
        if fmt & U:
            rpr += '<w:u w:val="single"/>'
        if fmt & SUP:
            rpr += '<w:vertAlign w:val="superscript"/>'
        elif fmt & SUB:
            rpr += '<w:vertAlign w:val="subscript"/>'
        t = '</w:t><w:tab/><w:t xml:space="preserve">'.join(esc(p) for p in text.split('\t'))
        return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % ('<w:rPr>%s</w:rPr>' % rpr if rpr else '', t)

    def inline(self, children, base=0):
        out, stack, fmt = [], [], base
        for c in children:
            ty = c.type
            if ty == 'text':
                out.append(self.run(c.content, fmt))
            elif ty == 'softbreak':
                out.append(self.run(' ', fmt))
            elif ty == 'hardbreak':
                out.append(_BR)
            elif ty == 'code_inline':
                out.append(self.run(c.content, fmt | CODE))
            elif ty == 'strong_open':
                fmt |= B
            elif ty == 'strong_close':
                fmt &= ~B | base & B
            elif ty == 'em_open':
                fmt |= I
            elif ty == 'em_close':
                fmt &= ~I
            elif ty == 's_open':
                fmt |= S
            elif ty == 's_close':
                fmt &= ~S
            elif ty == 'link_open':
                href = (c.attrGet('href') or '').strip()
                live = self.link_ok(href)
                stack.append((out, href, live))
                out, fmt = [], fmt | LINK if live else fmt
            elif ty == 'link_close' and stack:
                inner = ''.join(out)
                out, href, live = stack.pop()
                out.append(self.hyperlink(href, inner))
                if live:
                    fmt &= ~LINK
            elif ty == 'image':
                out.append(self.image(c, fmt))
            elif ty == 'html_inline':
                fmt = self.html_tag(c.content, fmt, out)
            elif ty == 'footnote_ref':
                fid = (c.meta or {}).get('id', 0) + 1
                out.append('<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference '
                           'w:id="%d"/></w:r>' % fid)
                self.rep.ok('footnotes/endnotes')
            elif ty == 'math_inline' or ty == 'math_inline_double':
                out.append(self.math(c.content))
        while stack:
            inner = ''.join(out)
            out, href, _ = stack.pop()
            out.append(self.hyperlink(href, inner))
        return ''.join(out)

    def html_tag(self, content, fmt, out):
        m = _TAG.match(content)
        if not m:
            return fmt
        name = m.group(2).lower()
        if name == 'br':
            out.append(_BR)
            return fmt
        bit = _HTML_FMT.get(name)
        if bit:
            return fmt & ~bit if m.group(1) else fmt | bit
        return fmt

    def math(self, tex):
        try:
            xml = latex.to_omml(tex)
            self.rep.ok('equations')
            return xml
        except Exception:
            self.rep.part('equations kept as LaTeX text')
            return self.run(tex, CODE)

    # --- links / images
    def rel(self, kind, target, external):
        key = (kind, target)
        rid = self._rel_ids.get(key)
        if rid is None:
            rid = self._rel_ids[key] = 'rIdX%d' % (len(self.rels) + 1)
            self.rels.append((rid, kind, target, external))
        return rid

    def _anchor(self, href):
        f = unquote(href[1:])
        return self.anchors.get(f.lower()) or self.anchors.get(f)

    def link_ok(self, href):
        return bool(href) and (not href.startswith('#') or self._anchor(href) is not None)

    def hyperlink(self, href, inner):
        if not inner:
            return ''
        if href.startswith('#'):
            name = self._anchor(href)
            if name is None:
                self.rep.part('links to unknown anchors (text only)')
                return inner
            self.rep.ok('hyperlinks')
            return '<w:hyperlink w:anchor="%s" w:history="1">%s</w:hyperlink>' % (name, inner)
        if not href:
            return inner
        self.rep.ok('hyperlinks')
        return '<w:hyperlink r:id="%s" w:history="1">%s</w:hyperlink>' % (self.rel('hyperlink', href, True), inner)

    def image(self, c, fmt):
        src = c.attrGet('src') or ''
        alt = c.content or ''
        status, payload = images.load(src, self.base_dir)
        if status == 'remote':
            self.rep.part('remote images (linked, not embedded)')
            return self.hyperlink(payload, self.run(alt or payload, fmt | LINK))
        if status == 'missing':
            self.rep.lost('images not found')
            self.warnings.append('image not found: %s (%s)' % (src[:80], payload))
            return self.run('[image not found: %s]' % (alt or src), I)
        prep = images.prepare(payload)
        if prep is None:
            self.rep.lost('unsupported image formats')
            self.warnings.append('unsupported image format: %s' % src[:80])
            return self.run('[unsupported image: %s]' % (alt or src), I)
        ext, data, w, h, dpi = prep
        name = self._media(ext, data)
        rid = self.rel('image', 'media/' + name, False)
        dpi = dpi if dpi and 50 <= dpi <= 1200 else 96
        cx, cy = int(w * 914400 / dpi), int(h * 914400 / dpi)
        if cx > self.maxw:
            cy, cx = int(cy * self.maxw / cx), int(self.maxw)
        self.docpr_id += 1
        n, a = self.docpr_id, attr(alt)
        self.rep.ok('images')
        return ('<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="%d" cy="%d"/>'
                '<wp:docPr id="%d" name="Picture %d" descr="%s"/><wp:cNvGraphicFramePr><a:graphicFrameLocks '
                'noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats'
                '.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="%d" name="%s" descr="%s"/>'
                '<pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="%s"/><a:stretch><a:fillRect/></a:stretch>'
                '</pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom '
                'prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline>'
                '</w:drawing></w:r>' % (cx, cy, n, n, a, n, attr(name), a, rid, cx, cy))

    def _media(self, ext, data):
        key = hashlib.sha1(data).hexdigest()
        name = self._media_ids.get(key)
        if name is None:
            name = self._media_ids[key] = 'image%d.%s' % (len(self.media) + 1, ext)
            self.media[name] = data
            self.exts.add(ext)
        return name


def convert(text, base_dir='.', page='a4'):
    """Markdown text -> Result(data=.docx bytes, report, warnings)."""
    return Builder(base_dir, page).build(text)
