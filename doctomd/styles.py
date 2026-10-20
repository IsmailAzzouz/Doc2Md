"""styles.xml -> resolved paragraph / run properties (cached)."""
import re

from .xmlns import *

_HEADING = re.compile(r'^heading (\d)$')
_TOC = re.compile(r'^toc (\d)$')
_KIND = {
    'title': 'title', 'subtitle': 'subtitle',
    'quote': 'quote', 'intense quote': 'quote', 'block text': 'quote', 'block quotation': 'quote',
    'code': 'code', 'source code': 'code', 'html preformatted': 'code', 'preformatted text': 'code',
    'macro': 'code', 'html code': 'code', 'verbatim': 'code',
}
_CHAR_CODE = {'verbatim char', 'source code', 'html code', 'html typewriter', 'code', 'macro text'}


def is_mono(font):
    f = font.lower()
    if 'monotype' in f:
        return False
    return any(k in f for k in ('courier', 'consolas', 'mono', 'menlo', 'monaco', 'lucida console',
                                'source code', 'fira code', 'cascadia', 'inconsolata', 'typewriter'))


def on(e):
    return e.get(VAL) not in ('0', 'false', 'off')


def parse_rpr(rpr):
    """Run properties element -> dict of the flags we care about (only keys present)."""
    d = {}
    for e in rpr:
        t = e.tag
        if t == B:
            d['b'] = on(e)
        elif t == I:
            d['i'] = on(e)
        elif t == STRIKE or t == DSTRIKE:
            d['s'] = on(e)
        elif t == U:
            d['u'] = e.get(VAL) != 'none'
        elif t == VERTALIGN:
            d['va'] = e.get(VAL)
        elif t == RFONTS:
            f = e.get(W + 'ascii') or e.get(W + 'hAnsi')
            if f:
                d['mono'] = is_mono(f)
        elif t == HIGHLIGHT:
            d['hl'] = e.get(VAL) != 'none'
        elif t == VANISH:
            d['vanish'] = on(e)
        elif t == RSTYLE:
            d['rstyle'] = e.get(VAL)
    return d


class _Style:
    __slots__ = ('id', 'type', 'name', 'based', 'outline', 'hlevel', 'numid', 'ilvl', 'rpr')


class ParaInfo:
    __slots__ = ('level', 'kind', 'toc', 'numid', 'ilvl', 'numstyle', 'rpr')


class Styles:
    def __init__(self, root):
        self.s = {}
        self.default_p = None
        self._chain, self._para, self._rpr = {}, {}, {}
        if root is None:
            return
        for st in root.iterfind(W + 'style'):
            s = _Style()
            s.id = st.get(W + 'styleId')
            s.type = st.get(TYPE)
            n = st.find(W + 'name')
            s.name = ((n.get(VAL) if n is not None else '') or '').lower()
            b = st.find(W + 'basedOn')
            s.based = b.get(VAL) if b is not None else None
            s.outline = s.hlevel = s.numid = s.ilvl = None
            m = _HEADING.match(s.name)
            if m:
                s.hlevel = int(m.group(1))
            ppr = st.find(PPR)
            if ppr is not None:
                o = ppr.find(OUTLINELVL)
                if o is not None:
                    v = _int(o.get(VAL), 9)
                    s.outline = v + 1 if v < 9 else 0
                np_ = ppr.find(NUMPR)
                if np_ is not None:
                    nid = np_.find(NUMID)
                    il = np_.find(ILVL)
                    if nid is not None:
                        s.numid = _int(nid.get(VAL), 0)
                    if il is not None:
                        s.ilvl = _int(il.get(VAL), 0)
            rpr = st.find(RPR)
            s.rpr = parse_rpr(rpr) if rpr is not None else {}
            s.rpr.pop('rstyle', None)
            if s.name in _CHAR_CODE and s.type == 'character':
                s.rpr['mono'] = True
            if st.get(W + 'default') in ('1', 'true') and s.type == 'paragraph':
                self.default_p = s.id
                s.rpr.pop('mono', None)
            self.s[s.id] = s

    def chain(self, sid):
        c = self._chain.get(sid)
        if c is None:
            c, seen, cur = [], set(), sid
            while cur and cur in self.s and cur not in seen:
                seen.add(cur)
                st = self.s[cur]
                c.append(st)
                cur = st.based
            self._chain[sid] = c
        return c

    def para(self, sid):
        if sid is None:
            sid = self.default_p
        info = self._para.get(sid)
        if info is None:
            info = self._para[sid] = self._build(sid)
        return info

    def _build(self, sid):
        info = ParaInfo()
        chain = self.chain(sid)
        info.level, info.kind, info.toc = None, None, 0
        info.numid = info.ilvl = info.numstyle = None
        rpr = {}
        for st in reversed(chain):
            rpr.update(st.rpr)
        info.rpr = rpr
        if chain and chain[0].name == 'toc heading':
            info.level, info.kind = 0, 'tocheading'
        for st in chain:
            if info.level is None:
                if st.outline is not None:
                    info.level = st.outline
                elif st.hlevel:
                    info.level = st.hlevel
            if info.numid is None and st.numid is not None:
                info.numid, info.ilvl, info.numstyle = st.numid, st.ilvl, st.id
            if info.kind is None and info.toc == 0:
                m = _TOC.match(st.name)
                if m:
                    info.toc = int(m.group(1))
                elif st.name == 'table of figures':
                    info.toc = 1
                else:
                    k = _KIND.get(st.name)
                    if k:
                        info.kind = k
        if info.level is None:
            m = re.match(r'^heading ?(\d)$', (sid or '').lower())  # style table missing/odd
            info.level = int(m.group(1)) if m else 0
        if info.kind is None and not info.level and not info.toc and rpr.get('mono'):
            info.kind = 'code'
        return info

    def rpr(self, pstyle, rstyle):
        key = (pstyle, rstyle)
        d = self._rpr.get(key)
        if d is None:
            d = dict(self.para(pstyle).rpr)
            if rstyle:
                for st in reversed(self.chain(rstyle)):
                    d.update(st.rpr)
            self._rpr[key] = d
        return d


def _int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
