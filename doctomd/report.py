"""Feature-coverage accounting: how much of what the document uses did we convert."""
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Optional

PARTIAL_WEIGHT = 0.5

# What Markdown cannot express; ignored on purpose and not counted as loss.
IGNORED_BY_DESIGN = ('fonts, colors, sizes, alignment, page layout/margins, headers & footers, '
                     'page breaks, shading, column layout')

FEATURE_MATRIX = (
    ('ok', 'Headings (styles, outline levels, Title), heading numbering'),
    ('ok', 'Bold, italic, strikethrough, underline, sub/superscript, highlight, inline code'),
    ('ok', 'Paragraphs, line breaks, block quotes, code blocks, horizontal rules'),
    ('ok', 'Bullet / decimal / multi-level lists: independent counters, restarts, level overrides; typed bullets'),
    ('part', 'Roman, alphabetic and compound list labels retained as text in bullet items'),
    ('ok', 'Tables -> GitHub pipe tables (column alignment, nested text, single-cell boxes unwrapped)'),
    ('ok', 'Merged table cells -> HTML rowspan/colspan with --table-format html'),
    ('part', 'Merged cells in pipe tables and nested tables are flattened with warnings'),
    ('ok', 'Hyperlinks: external, internal bookmarks, HYPERLINK/REF fields, mailto'),
    ('ok', 'Table of contents (kept as linked list; rebuilt from headings when empty)'),
    ('ok', 'Images: embedded/linked, alt text, floating, VML; extracted or --embed-images base64'),
    ('ok', 'Footnotes and endnotes'),
    ('part', 'Equations (common OMML -> LaTeX; unsupported constructs reported)'),
    ('part', 'Imported content (altChunk): plain text; HTML text without formatting; other formats reported'),
    ('ok', 'Text boxes and shapes with text, content controls, checkboxes, tracked changes (accepted)'),
    ('ok', 'Hidden text skipped, NBSP normalized, symbols (Wingdings/Symbol) mapped'),
    ('part', 'SmartArt (text extracted), OLE objects (preview image only), EMF/WMF (PNG only with Pillow)'),
    ('lost', 'Charts (placeholder), comments, drawing shapes without text, ink, WordArt'),
    ('ok', 'Other word formats: .doc .rtf .odt .dot .wps ... via LibreOffice or MS Word (auto-detected)'),
)


@dataclass(frozen=True)
class ConversionWarning:
    """A conversion limitation with a stable code and its source package part."""

    code: str
    message: str
    part: Optional[str] = None


class Report:
    def __init__(self):
        self.c = Counter()
        self.warnings: list[ConversionWarning] = []

    def warn(self, code: str, message: str, *, part: Optional[str] = None) -> None:
        """Add detail for a feature also counted as approximated or unsupported."""
        self.warnings.append(ConversionWarning(code, message, part))

    def ok(self, name, n=1):
        self.c[('ok', name)] += n

    def part(self, name, n=1):
        self.c[('part', name)] += n

    def lost(self, name, n=1):
        self.c[('lost', name)] += n

    def _sum(self, status):
        return sum(v for (s, _), v in self.c.items() if s == status)

    @property
    def total(self):
        return sum(self.c.values())

    @property
    def percent(self):
        t = self.total
        if not t:
            return 100.0
        return 100.0 * (self._sum('ok') + PARTIAL_WEIGHT * self._sum('part')) / t

    def format(self):
        lines = ['Feature coverage: %.0f%%  (%d feature instances: %d full, %d partial, %d not supported)' % (
            self.percent, self.total, self._sum('ok'), self._sum('part'), self._sum('lost'))]
        for status, label in (('ok', 'converted'), ('part', 'approximated'), ('lost', 'NOT supported')):
            items = sorted(((n, v) for (s, n), v in self.c.items() if s == status), key=lambda x: -x[1])
            if items:
                lines.append('  %-13s %s' % (label + ':', ', '.join('%s x%d' % (n, v) for n, v in items)))
        for warning in self.warnings:
            location = ' (%s)' % warning.part if warning.part else ''
            lines.append('  warning [%s]%s: %s' % (warning.code, location, warning.message))
        return '\n'.join(lines)

    def as_dict(self):
        return {'percent': round(self.percent, 1), 'total': self.total,
                'features': [{'status': s, 'name': n, 'count': v} for (s, n), v in sorted(self.c.items())],
                'warnings': [asdict(warning) for warning in self.warnings]}
