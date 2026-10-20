"""LaTeX (common subset) -> Office Math (OMML). Raises LatexError on anything it cannot represent."""
import re
from xml.sax.saxutils import escape

from doctomd import omml


class LatexError(Exception):
    pass


_TOK = re.compile(r'\\([A-Za-z]+|.)|([{}^_&\[\]])|(\s+)|(.)', re.S)

# command name -> unicode, derived from the OMML->LaTeX table so both directions agree
_SYM = {}
for _ch, _tex in omml._SYM.items():
    _m = re.fullmatch(r'\\([A-Za-z]+) ?', _tex)
    if _m:
        _SYM[_m.group(1)] = _ch
_SYM.update({'le': '≤', 'ge': '≥', 'ne': '≠', 'to': '→', 'gets': '←', 'cdotp': '·', 'ldots': '…', 'dots': '…',
             'lbrace': '{', 'rbrace': '}', 'langle': '⟨', 'rangle': '⟩', 'lvert': '|', 'rvert': '|',
             'epsilon': 'ε', 'varepsilon': 'ε', 'varphi': 'φ', 'vartheta': 'ϑ', 'degree': '°', 'prime': '′',
             'perp': '⊥', 'parallel': '∥', 'angle': '∠', 'triangle': '△', 'mid': '|', 'ell': 'ℓ', 'hbar': 'ℏ',
             'iff': '⇔', 'implies': '⇒', 'longrightarrow': '⟶', 'Rightarrow': '⇒', 'Leftarrow': '⇐',
             'oplus': '⊕', 'otimes': '⊗', 'setminus': '∖', 'approx': '≈', 'cong': '≅', 'simeq': '≃'})
_LITERAL = {'%': '%', '&': '&', '#': '#', '$': '$', '_': '_', '{': '{', '}': '}', '|': '‖', '\\': ' '}
_SPACE = {',', ';', ':', '!', ' ', 'quad', 'qquad', 'enspace', 'thinspace'}
_NARY = {'sum': '∑', 'prod': '∏', 'coprod': '∐', 'int': '∫', 'iint': '∬', 'iiint': '∭', 'oint': '∮',
         'bigcup': '⋃', 'bigcap': '⋂', 'bigvee': '⋁', 'bigwedge': '⋀'}
_LIMITS = {'lim', 'max', 'min', 'sup', 'inf', 'limsup', 'liminf', 'argmax', 'argmin'}
_FUNCS = {'sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh', 'log', 'ln',
          'lg', 'exp', 'det', 'dim', 'gcd', 'deg', 'arg', 'ker', 'Pr', 'hom', 'mod'}
_ACCENT = {'hat': '̂', 'widehat': '̂', 'tilde': '̃', 'widetilde': '̃', 'bar': '̄', 'vec': '⃗', 'dot': '̇',
           'ddot': '̈', 'check': '̌', 'breve': '̆', 'acute': '́', 'grave': '̀'}
_DELIM = {'(': '(', ')': ')', '[': '[', ']': ']', '|': '|', '.': '', '/': '/', '\\{': '{', '\\}': '}',
          '\\|': '‖', '\\langle': '⟨', '\\rangle': '⟩', '\\lfloor': '⌊', '\\rfloor': '⌋', '\\lceil': '⌈',
          '\\rceil': '⌉', '\\lvert': '|', '\\rvert': '|', '\\lbrace': '{', '\\rbrace': '}', '\\vert': '|'}
_ENV_DELIMS = {'pmatrix': ('(', ')'), 'bmatrix': ('[', ']'), 'Bmatrix': ('{', '}'), 'vmatrix': ('|', '|'),
               'Vmatrix': ('‖', '‖'), 'matrix': None, 'smallmatrix': None, 'array': None,
               'cases': ('{', '')}
_ENV_ARRAY = {'aligned', 'align', 'align*', 'gather', 'gathered', 'split', 'eqnarray'}
_BB = {'R': 'ℝ', 'N': 'ℕ', 'Z': 'ℤ', 'Q': 'ℚ', 'C': 'ℂ', 'H': 'ℍ', 'P': 'ℙ'}


def _run(text, sty=None):
    rpr = '<m:rPr><m:sty m:val="%s"/></m:rPr>' % sty if sty else ''
    return '<m:r>%s<m:t xml:space="preserve">%s</m:t></m:r>' % (rpr, escape(text))


def _tokenize(src):
    toks = []
    for m in _TOK.finditer(src):
        if m.group(1) is not None:
            toks.append(('cmd', m.group(1)))
        elif m.group(2) is not None:
            toks.append((m.group(2), m.group(2)))
        elif m.group(3) is not None:
            toks.append(('sp', ' '))
        else:
            toks.append(('ch', m.group(4)))
    return toks


class _Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    # --- helpers
    def peek(self, skip_space=True):
        j = self.i
        while skip_space and j < len(self.t) and self.t[j][0] == 'sp':
            j += 1
        return self.t[j] if j < len(self.t) else None

    def next(self, skip_space=True):
        while skip_space and self.i < len(self.t) and self.t[self.i][0] == 'sp':
            self.i += 1
        if self.i >= len(self.t):
            raise LatexError('unexpected end')
        tok = self.t[self.i]
        self.i += 1
        return tok

    def raw_group(self):
        """Raw text inside {...} (for \\text)."""
        if self.next()[0] != '{':
            raise LatexError('expected {')
        depth, out = 1, []
        while True:
            k, v = self.next(skip_space=False)
            if k == '{':
                depth += 1
            elif k == '}':
                depth -= 1
                if depth == 0:
                    return ''.join(out)
            out.append('\\' + v if k == 'cmd' and len(v) == 1 else v if k != 'cmd' else '')

    def arg(self):
        """One argument: {group} or a single token (with no scripts)."""
        tok = self.peek()
        if tok is None:
            raise LatexError('missing argument')
        if tok[0] == '{':
            self.next()
            xml = self.seq(until='}')
            self.next()
            return xml
        a = self.atom()
        if isinstance(a, tuple):
            return _run(a[1])
        if isinstance(a, dict):
            raise LatexError('operator used as argument')
        return a

    # --- grammar
    def seq(self, until=None, stop_cmds=()):
        out = []
        while True:
            tok = self.peek()
            if tok is None:
                if until:
                    raise LatexError('unbalanced braces')
                break
            if until and tok[0] == until:
                break
            if tok[0] == 'cmd' and tok[1] in stop_cmds:
                break
            if tok[0] in ('}',):
                raise LatexError('unbalanced }')
            out.append(self.scripted())
        return ''.join(self._merge(out))

    @staticmethod
    def _merge(nodes):
        """Merge adjacent plain single-char runs into one m:r."""
        res, buf = [], []
        for n in nodes:
            if isinstance(n, tuple):
                buf.append(n[1])
            else:
                if buf:
                    res.append(_run(''.join(buf)))
                    buf = []
                res.append(n)
        if buf:
            res.append(_run(''.join(buf)))
        return res

    def scripted(self):
        base = self.atom()
        sub = sup = None
        while True:
            tok = self.peek()
            if tok and tok[0] == '_' and sub is None:
                self.next()
                sub = self.arg()
            elif tok and tok[0] == '^' and sup is None:
                self.next()
                sup = self.arg()
            else:
                break
        if isinstance(base, dict):                       # nary operator / limit function
            if base['kind'] == 'nary':
                body = self.operand()
                return ('<m:nary><m:naryPr><m:chr m:val="%s"/>%s%s</m:naryPr><m:sub>%s</m:sub><m:sup>%s</m:sup>'
                        '<m:e>%s</m:e></m:nary>' % (
                            base['chr'], '<m:subHide m:val="1"/>' if not sub else '',
                            '<m:supHide m:val="1"/>' if not sup else '', sub or '', sup or '', body))
            if base['kind'] == 'limit':
                name = '<m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>%s</m:t></m:r>' % base['name']
                if sub and sup:
                    return '<m:sSubSup><m:e>%s</m:e><m:sub>%s</m:sub><m:sup>%s</m:sup></m:sSubSup>' % (name, sub, sup)
                if sub:
                    return '<m:limLow><m:e>%s</m:e><m:lim>%s</m:lim></m:limLow>' % (name, sub)
                return name
            if base['kind'] == 'func':
                return ('<m:func><m:fName><m:r><m:rPr><m:sty m:val="p"/></m:rPr><m:t>%s</m:t></m:r></m:fName>'
                        '<m:e>%s</m:e></m:func>' % (base['name'], self.operand_opt(sub, sup)))
        if sub is None and sup is None:
            return base
        b = base if isinstance(base, str) else _run(base[1])
        if sub is not None and sup is not None:
            return '<m:sSubSup><m:e>%s</m:e><m:sub>%s</m:sub><m:sup>%s</m:sup></m:sSubSup>' % (b, sub, sup)
        if sub is not None:
            return '<m:sSub><m:e>%s</m:e><m:sub>%s</m:sub></m:sSub>' % (b, sub)
        return '<m:sSup><m:e>%s</m:e><m:sup>%s</m:sup></m:sSup>' % (b, sup)

    def operand(self):
        tok = self.peek()
        if tok is None or tok[0] in ('}',) or (tok[0] == 'cmd' and tok[1] in ('right', 'end')) or tok[0] == '&':
            return ''
        n = self.scripted()
        return ''.join(self._merge([n]))

    def operand_opt(self, sub, sup):
        return self.operand()

    def atom(self):
        k, v = self.next()
        if k == 'ch':
            return ('r', v)
        if k == '&':
            return ('r', '&')
        if k in ('[', ']'):
            return ('r', v)
        if k == '{':
            xml = self.seq(until='}')
            self.next()
            return xml or _run('')
        if k in ('^', '_'):
            raise LatexError('dangling script')
        if k == 'cmd':
            return self.command(v)
        raise LatexError('unexpected token %r' % (v,))

    def command(self, c):
        if c in _SYM:
            return ('r', _SYM[c])
        if c in _LITERAL:
            return ('r', _LITERAL[c])
        if c in _SPACE:
            return ('r', ' ') if c in ('quad', 'qquad', 'enspace', ' ') else ('r', '')
        if c in _NARY:
            return {'kind': 'nary', 'chr': _NARY[c]}
        if c in _LIMITS:
            return {'kind': 'limit', 'name': c}
        if c in _FUNCS:
            return {'kind': 'func', 'name': c}
        if c in ('frac', 'dfrac', 'tfrac', 'cfrac'):
            n, d = self.arg(), self.arg()
            return '<m:f><m:num>%s</m:num><m:den>%s</m:den></m:f>' % (n, d)
        if c == 'binom':
            n, d = self.arg(), self.arg()
            return ('<m:d><m:dPr><m:begChr m:val="("/><m:endChr m:val=")"/></m:dPr><m:e><m:f><m:fPr><m:type m:val="noBar"/>'
                    '</m:fPr><m:num>%s</m:num><m:den>%s</m:den></m:f></m:e></m:d>' % (n, d))
        if c == 'sqrt':
            deg = ''
            if self.peek() and self.peek()[0] == '[':
                self.next()
                deg = self.seq(until=']')
                self.next()
            body = self.arg()
            if deg:
                return '<m:rad><m:deg>%s</m:deg><m:e>%s</m:e></m:rad>' % (deg, body)
            return '<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>%s</m:e></m:rad>' % body
        if c in ('text', 'textrm', 'textit', 'textbf', 'mbox', 'hbox'):
            return _run(self.raw_group(), None) .replace('<m:r>', '<m:r><m:rPr><m:nor/></m:rPr>', 1)
        if c in ('mathrm', 'operatorname', 'mathsf', 'mathtt', 'rm'):
            return _run(self.raw_group(), 'p')
        if c in ('mathbf', 'boldsymbol', 'bm'):
            return _run(self.raw_group(), 'b')
        if c == 'mathbb':
            return _run(''.join(_BB.get(ch, ch) for ch in self.raw_group()))
        if c in ('mathcal', 'mathscr', 'mathfrak', 'mathit'):
            return self.arg()
        if c in _ACCENT:
            return '<m:acc><m:accPr><m:chr m:val="%s"/></m:accPr><m:e>%s</m:e></m:acc>' % (_ACCENT[c], self.arg())
        if c == 'overline':
            return '<m:bar><m:barPr><m:pos m:val="top"/></m:barPr><m:e>%s</m:e></m:bar>' % self.arg()
        if c == 'underline':
            return '<m:bar><m:barPr><m:pos m:val="bot"/></m:barPr><m:e>%s</m:e></m:bar>' % self.arg()
        if c in ('overbrace', 'underbrace'):
            pos, ch = ('top', '⏞') if c == 'overbrace' else ('bot', '⏟')
            return ('<m:groupChr><m:groupChrPr><m:chr m:val="%s"/><m:pos m:val="%s"/></m:groupChrPr><m:e>%s</m:e>'
                    '</m:groupChr>' % (ch, pos, self.arg()))
        if c in ('left', 'bigl', 'Bigl', 'biggl'):
            return self.delimited()
        if c in ('right', 'middle', 'bigr', 'Bigr', 'biggr', 'big', 'Big'):
            d = self.delim_token()
            return ('r', _DELIM.get(d, d) or '')
        if c == 'begin':
            return self.environment()
        if c in ('displaystyle', 'textstyle', 'scriptstyle', 'limits', 'nolimits', 'nonumber', 'notag', 'label'):
            return ('r', '')
        raise LatexError('unsupported command \\%s' % c)

    def delim_token(self):
        k, v = self.next()
        if k == 'cmd':
            return '\\' + v
        return v

    def delimited(self):
        beg = self.delim_token()
        body_parts = [self.seq(stop_cmds=('right', 'middle'))]
        while self.peek() and self.peek() == ('cmd', 'middle'):
            self.next()
            self.delim_token()
            body_parts.append(self.seq(stop_cmds=('right', 'middle')))
        if not self.peek() or self.peek() != ('cmd', 'right'):
            raise LatexError('missing \\right')
        self.next()
        end = self.delim_token()
        return ('<m:d><m:dPr><m:begChr m:val="%s"/><m:endChr m:val="%s"/></m:dPr>%s</m:d>' % (
            _DELIM.get(beg, beg), _DELIM.get(end, end), ''.join('<m:e>%s</m:e>' % p for p in body_parts)))

    def environment(self):
        name = self.raw_group()
        if name == 'array' and self.peek() and self.peek()[0] == '{':
            self.raw_group()                              # column spec
        rows, row, cell = [], [], []
        while True:
            tok = self.peek()
            if tok is None:
                raise LatexError('missing \\end{%s}' % name)
            if tok == ('cmd', 'end'):
                self.next()
                if self.raw_group() != name:
                    raise LatexError('mismatched \\end')
                break
            if tok[0] == '&' and name not in _ENV_ARRAY:
                self.next()
                row.append(''.join(self._merge(cell)))
                cell = []
            elif tok == ('cmd', '\\'):
                self.next()
                row.append(''.join(self._merge(cell)))
                rows.append(row)
                row, cell = [], []
            else:
                cell.append(self.scripted())
        if cell or row:
            row.append(''.join(self._merge(cell)))
            rows.append(row)
        rows = [r for r in rows if any(r)] or rows
        if name in _ENV_ARRAY:
            return '<m:eqArr>%s</m:eqArr>' % ''.join('<m:e>%s</m:e>' % ''.join(r) for r in rows)
        mx = '<m:m>%s</m:m>' % ''.join('<m:mr>%s</m:mr>' % ''.join('<m:e>%s</m:e>' % c for c in r) for r in rows)
        d = _ENV_DELIMS.get(name)
        if d:
            return ('<m:d><m:dPr><m:begChr m:val="%s"/><m:endChr m:val="%s"/></m:dPr><m:e>%s</m:e></m:d>'
                    % (d[0], d[1], mx))
        return mx


def to_omml(src):
    """LaTeX math (no $ delimiters) -> '<m:oMath>...</m:oMath>' string."""
    p = _Parser(_tokenize(src))
    xml = p.seq()
    if p.peek() is not None:
        raise LatexError('trailing input')
    return '<m:oMath>%s</m:oMath>' % xml
