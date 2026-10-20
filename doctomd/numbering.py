"""numbering.xml -> list counters and labels."""
from .xmlns import *

_ROMAN = (('m', 1000), ('cm', 900), ('d', 500), ('cd', 400), ('c', 100), ('xc', 90),
          ('l', 50), ('xl', 40), ('x', 10), ('ix', 9), ('v', 5), ('iv', 4), ('i', 1))


def _int(v, default):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _roman(n):
    out = []
    for s, v in _ROMAN:
        while n >= v:
            out.append(s)
            n -= v
    return ''.join(out)


def _letters(n):
    return chr(ord('a') + (n - 1) % 26) * ((n - 1) // 26 + 1)


def format_number(fmt, n):
    if fmt == 'decimalZero':
        return '%02d' % n
    if fmt == 'upperRoman':
        return _roman(n).upper()
    if fmt == 'lowerRoman':
        return _roman(n)
    if fmt == 'upperLetter':
        return _letters(n).upper()
    if fmt == 'lowerLetter':
        return _letters(n)
    return str(n)


class Numbering:
    def __init__(self, root):
        self.abs, self.num, self.alias, self.style_lvl = {}, {}, {}, {}
        self.counters, self.seen = {}, set()
        if root is None:
            return
        style_links, pending = {}, {}
        for a in root.iterfind(W + 'abstractNum'):
            aid = a.get(W + 'abstractNumId')
            lvls = {}
            for l in a.iterfind(W + 'lvl'):
                il = _int(l.get(ILVL), 0)
                f, t, s, p = (l.find(W + k) for k in ('numFmt', 'lvlText', 'start', 'pStyle'))
                ps = p.get(VAL) if p is not None else None
                pp = l.find(PPR)
                ind = pp.find(W + 'ind') if pp is not None else None
                left = _int(ind.get(W + 'left', ind.get(W + 'start')), None) if ind is not None else None
                lvls[il] = ((f.get(VAL) if f is not None else None) or 'decimal',
                            (t.get(VAL) if t is not None else None) or '%1.',
                            _int(s.get(VAL), 1) if s is not None else 1, ps, left)
                if ps:
                    self.style_lvl[ps] = il
            self.abs[aid] = lvls
            sl = a.find(W + 'styleLink')
            if sl is not None:
                style_links[sl.get(VAL)] = aid
            nl = a.find(W + 'numStyleLink')
            if nl is not None and not lvls:
                pending[aid] = nl.get(VAL)
        for aid, style in pending.items():
            if style in style_links:
                self.alias[aid] = style_links[style]
        for n in root.iterfind(W + 'num'):
            a = n.find(W + 'abstractNumId')
            if a is None:
                continue
            ov = {}
            for o in n.iterfind(W + 'lvlOverride'):
                so = o.find(W + 'startOverride')
                if so is not None:
                    ov[_int(o.get(ILVL), 0)] = _int(so.get(VAL), 1)
            self.num[_int(n.get(NUMID), -1)] = (a.get(VAL), ov)

    def style_level(self, style_id):
        return self.style_lvl.get(style_id, 0)

    def step(self, numid, ilvl):
        """Advance counters. -> (bullet, number, label, none, left_indent_twips) or None if unknown."""
        n = self.num.get(numid)
        if n is None:
            return None
        aid, ov = n
        aid = self.alias.get(aid, aid)
        lv = self.abs.get(aid)
        if not lv:
            return None
        ilvl = max(0, min(ilvl, 8))
        info = lv.get(ilvl) or lv[min(lv)]
        arr = self.counters.setdefault(aid, [None] * 9)
        if numid not in self.seen:
            self.seen.add(numid)
            for l in ov:
                for j in range(l, 9):
                    arr[j] = None
        fmt, text, start, _, left = info
        left = left if left is not None else (ilvl + 1) * 360
        start = ov.get(ilvl, start)
        arr[ilvl] = start if arr[ilvl] is None else arr[ilvl] + 1
        for j in range(ilvl + 1, 9):
            arr[j] = None
        if fmt == 'bullet':
            return True, 0, '', False, left
        if fmt == 'none':
            return False, 0, '', True, left
        return False, arr[ilvl], self._label(lv, arr, text), False, left

    @staticmethod
    def _label(lv, arr, text):
        out, i, n = [], 0, len(text)
        while i < n:
            c = text[i]
            if c == '%' and i + 1 < n and text[i + 1].isdigit():
                k = int(text[i + 1]) - 1
                li = lv.get(k)
                v = arr[k] if 0 <= k < 9 and arr[k] is not None else (li[2] if li else 1)
                out.append(format_number(li[0] if li else 'decimal', v))
                i += 2
            else:
                out.append(c)
                i += 1
        return ''.join(out).strip()
