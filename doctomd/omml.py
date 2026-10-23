"""Office Math (OMML) -> LaTeX. Covers the constructs Word's equation editor produces."""
from .xmlns import M

_SYM = {
    'α': r'\alpha ', 'β': r'\beta ', 'γ': r'\gamma ', 'δ': r'\delta ', 'ε': r'\epsilon ', 'ϵ': r'\epsilon ',
    'ζ': r'\zeta ', 'η': r'\eta ', 'θ': r'\theta ', 'ι': r'\iota ', 'κ': r'\kappa ', 'λ': r'\lambda ',
    'μ': r'\mu ', 'ν': r'\nu ', 'ξ': r'\xi ', 'π': r'\pi ', 'ρ': r'\rho ', 'σ': r'\sigma ', 'τ': r'\tau ',
    'υ': r'\upsilon ', 'φ': r'\phi ', 'ϕ': r'\phi ', 'χ': r'\chi ', 'ψ': r'\psi ', 'ω': r'\omega ',
    'Γ': r'\Gamma ', 'Δ': r'\Delta ', 'Θ': r'\Theta ', 'Λ': r'\Lambda ', 'Ξ': r'\Xi ', 'Π': r'\Pi ',
    'Σ': r'\Sigma ', 'Φ': r'\Phi ', 'Ψ': r'\Psi ', 'Ω': r'\Omega ',
    '×': r'\times ', '÷': r'\div ', '±': r'\pm ', '∓': r'\mp ', '·': r'\cdot ', '∙': r'\cdot ', '∘': r'\circ ',
    '≤': r'\leq ', '≥': r'\geq ', '≠': r'\neq ', '≈': r'\approx ', '≡': r'\equiv ', '∼': r'\sim ', '≅': r'\cong ',
    '∝': r'\propto ', '≪': r'\ll ', '≫': r'\gg ', '∞': r'\infty ', '∂': r'\partial ', '∇': r'\nabla ',
    '∈': r'\in ', '∉': r'\notin ', '⊂': r'\subset ', '⊃': r'\supset ', '⊆': r'\subseteq ', '⊇': r'\supseteq ',
    '∪': r'\cup ', '∩': r'\cap ', '∅': r'\emptyset ', '∀': r'\forall ', '∃': r'\exists ', '¬': r'\neg ',
    '∧': r'\wedge ', '∨': r'\vee ', '→': r'\to ', '←': r'\leftarrow ', '↔': r'\leftrightarrow ',
    '⇒': r'\Rightarrow ', '⇐': r'\Leftarrow ', '⇔': r'\Leftrightarrow ', '↦': r'\mapsto ',
    '∑': r'\sum ', '∏': r'\prod ', '∫': r'\int ', '√': r'\sqrt ', '′': "'", '″': "''", '…': r'\ldots ',
    '⋯': r'\cdots ', '⋮': r'\vdots ', '⋱': r'\ddots ', '−': '-', '∗': '*', '‖': r'\| ', 'ℝ': r'\mathbb{R}',
    'ℕ': r'\mathbb{N}', 'ℤ': r'\mathbb{Z}', 'ℚ': r'\mathbb{Q}', 'ℂ': r'\mathbb{C}', '°': r'^\circ ',
    '{': r'\{', '}': r'\}', '%': r'\%', '#': r'\#', '$': r'\$', '_': r'\_', '\\': r'\backslash ',
}
_NARY = {'∑': r'\sum', '∏': r'\prod', '∫': r'\int', '∬': r'\iint', '∭': r'\iiint', '∮': r'\oint',
         '⋃': r'\bigcup', '⋂': r'\bigcap', '⋁': r'\bigvee', '⋀': r'\bigwedge'}
_DELIM = {'(': '(', ')': ')', '[': '[', ']': ']', '{': r'\{', '}': r'\}', '|': '|', '‖': r'\|',
          '⟨': r'\langle', '⟩': r'\rangle', '⌈': r'\lceil', '⌉': r'\rceil', '⌊': r'\lfloor', '⌋': r'\rfloor',
          '': '.'}
_ACC = {'̂': 'hat', '^': 'hat', '̃': 'tilde', '~': 'tilde', '̄': 'bar', '¯': 'bar', '̇': 'dot', '̈': 'ddot',
        '⃗': 'vec', '→': 'vec', '̌': 'check', '̆': 'breve'}
_FUNCS = {'sin', 'cos', 'tan', 'cot', 'sec', 'csc', 'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh',
          'log', 'ln', 'lg', 'exp', 'lim', 'max', 'min', 'sup', 'inf', 'det', 'dim', 'gcd', 'deg', 'arg', 'ker'}


def _g(s):
    """Brace-group unless already a single token."""
    return s if len(s) == 1 else '{' + s + '}'


def _val(e, tag, default=None):
    p = e.find(tag)
    if p is None:
        return default
    c = p.find(M + 'chr')
    if c is not None:
        return c.get(M + 'val', default)
    return default


def _prop(e, pr, tag, default=None):
    p = e.find(M + pr)
    if p is None:
        return default
    c = p.find(M + tag)
    return c.get(M + 'val', default) if c is not None else default


def _seq(e):
    return ''.join(_node(c) for c in e)


def _sub(e, name):
    c = e.find(M + name)
    return _seq(c) if c is not None else ''


def _run(e):
    txt = ''.join(t.text or '' for t in e.iter(M + 't'))
    if not txt:
        return ''
    sty = e.find(M + 'rPr')
    plain = sty is not None and (sty.find(M + 'sty') is not None and sty.find(M + 'sty').get(M + 'val') == 'p'
                                 or sty.find(M + 'nor') is not None)
    out = ''.join(_SYM.get(c, c) for c in txt)
    if plain and len(txt) > 1:
        return r'\mathrm{%s}' % out
    return out


def _frac(e):
    n, d = _sub(e, 'num'), _sub(e, 'den')
    t = _prop(e, 'fPr', 'type')
    if t == 'noBar':
        return r'\binom{%s}{%s}' % (n, d)
    if t == 'lin':
        return '%s/%s' % (_g(n), _g(d))
    return r'\frac{%s}{%s}' % (n, d)


def _rad(e):
    deg, body = _sub(e, 'deg').strip(), _sub(e, 'e')
    return r'\sqrt[%s]{%s}' % (deg, body) if deg else r'\sqrt{%s}' % body


def _nary(e):
    ch = _prop(e, 'naryPr', 'chr', '∫')
    op = _NARY.get(ch, _SYM.get(ch, ch).strip())
    s = op
    sub, sup = _sub(e, 'sub'), _sub(e, 'sup')
    if sub:
        s += '_' + _g(sub)
    if sup:
        s += '^' + _g(sup)
    return s + ' ' + _sub(e, 'e')


def _delim(e):
    beg = _prop(e, 'dPr', 'begChr', '(')
    end = _prop(e, 'dPr', 'endChr', ')')
    sep = _prop(e, 'dPr', 'sepChr', '|')
    body = (' ' + _DELIM.get(sep, sep) + ' ').join(_seq(x) for x in e.findall(M + 'e'))
    return r'\left%s %s \right%s' % (_DELIM.get(beg, beg), body, _DELIM.get(end, end))


def _func(e):
    name = _sub(e, 'fName').strip()
    if name in _FUNCS:
        name = '\\' + name
    elif name.isalpha():
        name = r'\operatorname{%s}' % name
    return name + ' ' + _sub(e, 'e')


def _acc(e):
    ch = _prop(e, 'accPr', 'chr', '̂')
    return '\\%s{%s}' % (_ACC.get(ch, 'hat'), _sub(e, 'e'))


def _bar(e):
    pos = _prop(e, 'barPr', 'pos', 'top')
    return ('\\underline{%s}' if pos == 'bot' else '\\overline{%s}') % _sub(e, 'e')


def _group(e):
    pos = _prop(e, 'groupChrPr', 'pos', 'bot')
    ch = _prop(e, 'groupChrPr', 'chr', '⏟')
    over = pos == 'top' or ch == '⏞'
    return ('\\overbrace{%s}' if over else '\\underbrace{%s}') % _sub(e, 'e')


def _matrix(e):
    rows = [' & '.join(_seq(c) for c in r.findall(M + 'e')) for r in e.findall(M + 'mr')]
    return r'\begin{matrix}' + r' \\ '.join(rows) + r'\end{matrix}'


def _eqarr(e):
    return r'\begin{aligned}' + r' \\ '.join(_seq(c) for c in e.findall(M + 'e')) + r'\end{aligned}'


_H = {
    'r': _run,
    'f': _frac,
    'rad': _rad,
    'nary': _nary,
    'd': _delim,
    'func': _func,
    'acc': _acc,
    'bar': _bar,
    'groupChr': _group,
    'm': _matrix,
    'eqArr': _eqarr,
    'sSup': lambda e: _g(_sub(e, 'e')) + '^' + _g(_sub(e, 'sup')),
    'sSub': lambda e: _g(_sub(e, 'e')) + '_' + _g(_sub(e, 'sub')),
    'sSubSup': lambda e: _g(_sub(e, 'e')) + '_' + _g(_sub(e, 'sub')) + '^' + _g(_sub(e, 'sup')),
    'sPre': lambda e: '{}_' + _g(_sub(e, 'sub')) + '^' + _g(_sub(e, 'sup')) + _g(_sub(e, 'e')),
    'limLow': lambda e: _sub(e, 'e') + '_' + _g(_sub(e, 'lim')),
    'limUpp': lambda e: r'\overset{%s}{%s}' % (_sub(e, 'lim'), _sub(e, 'e')),
    'borderBox': lambda e: r'\boxed{%s}' % _sub(e, 'e'),
}

# Structural containers have no notation of their own; their children carry it.
_CONTAINERS = {'oMath', 'oMathPara', 'e', 'num', 'den', 'deg', 'sub', 'sup',
               'fName', 'lim', 'mr', 't'}


def unsupported_elements(element):
    """Find math constructs that would otherwise be silently flattened by _node."""
    unsupported = set()

    def visit(node):
        if not isinstance(node.tag, str) or not node.tag.startswith(M):
            return
        name = node.tag[len(M):]
        if name.endswith('Pr'):
            return
        if name not in _H and name not in _CONTAINERS:
            unsupported.add(name)
        for child in node:
            visit(child)

    visit(element)
    return sorted(unsupported)


def _node(e):
    tag = e.tag
    if not isinstance(tag, str) or not tag.startswith(M):
        return ''
    local = tag[len(M):]
    h = _H.get(local)
    if h:
        return h(e)
    if local.endswith('Pr'):
        return ''
    return _seq(e)


def to_latex(el):
    """oMath element -> LaTeX string (no delimiters)."""
    return ' '.join(_seq(el).split())
