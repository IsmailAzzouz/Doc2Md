# Limitations and compatibility

Doc2Md targets **semantic content** rather than visual/page-perfect fidelity.
A round trip through Markdown will not reproduce the original page layout.

| Feature | Word → Markdown | Markdown → DOCX |
| --- | --- | --- |
| Headings, text formatting, links | Supported for common cases | Supported for common cases |
| Lists | Independent counters, restarts and level overrides; see numbering details below | Common Markdown lists with predefined Word numbering styles |
| Tables | Pipe tables by default; optional HTML preserves merges, nested tables and cell lists | Pipe tables and HTML tables, including nested tables, cell lists and row/column spans |
| Images | Embedded images extracted or optionally inlined | Local/data URI raster images; remote URLs linked |
| Equations | Common Word OMML converted to LaTeX | Supported LaTeX subset converted to OMML; other syntax may remain literal |
| Footnotes and endnotes | Text, links and images use each note part's relationships | Markdown footnotes; endnote distinction is not restored |
| Imported content (`altChunk`) | Plain text preserved; HTML reduced to text with a warning; other formats get a placeholder | Not reconstructed |
| SmartArt and embedded objects | Text or preview image, if present | Not reconstructed |
| Charts and comments | Unsupported / content may be lost | No native reconstruction |
| Page design (fonts, margins, headers, page breaks, columns) | Intentionally not preserved | Uses predefined DOCX styles and page size |
| Legacy Word formats | Requires LibreOffice or Microsoft Word | DOCX output only |

Known caveats:

- Markdown cannot encode many Word presentation features; merged cells in pipe
  tables, floating shapes and text wrapping are approximated or discarded.
- Chart data, annotations/comments, ink and drawing-only shapes are not reliably
  converted. Do not treat a successful exit status as lossless conversion.
- Word math and Markdown LaTeX support overlapping **subsets**; arbitrary LaTeX,
  complex OMML and all math environments are not guaranteed.
- Equations directly inside the document body, supported content wrappers and
  notes are converted as display math. Unknown OMML constructs retain whatever
  can be converted and produce a warning; this does not detect every unsupported
  equation property or guarantee equivalent mathematical meaning.
- Imported HTML retains readable text and image labels, but loses formatting,
  hyperlink destinations and embedded media. Scripts, styles and document-head
  content are excluded. Plain-text/HTML imports support UTF-8, Unicode BOMs,
  MIME charsets and HTML meta charsets. RTF, embedded DOCX, MHTML and other
  unsupported imports are not decoded: a visible placeholder and warning identify
  the omission. External imports are not fetched.
- Raster conversions of less common image formats can require Pillow;
  EMF/WMF handling depends on platform and installed converters.
- Remote images are not fetched by Markdown → DOCX. Missing local assets yield
  warnings and can be omitted.
- Legacy formats use third-party programs and can behave differently on different
  platforms. LibreOffice/MS Word are **not** bundled or installed automatically.
- Untrusted input may contain oversized images or ZIP/XML content. No formal
  resource quotas or security-hardening audit are provided; use process-level
  limits for server-side use and avoid running legacy converters on untrusted
  documents without sandboxing.
- The coverage percentage indicates recognized feature instances, not visual
  accuracy, accessibility compliance or semantic equivalence.

## Tables

The converter resolves the table grid, including `gridSpan`, vertical `vMerge`,
legacy horizontal `hMerge`, and skipped columns before/after a row. A vertical
continuation must occupy the same grid columns in the immediately preceding
row. Invalid spans or unmatched merges retain readable cells and produce an
`invalid-table-structure` warning. Nonempty continuation cells are retained
once at the merge origin, with a `merged-cell-content-moved` warning.

The default `--table-format markdown` produces pipe tables. Merged origins
occupy their original grid position; the other covered positions are empty.
Each affected table produces a `merged-table-flattened` warning. As before,
the first row becomes the Markdown header, and simple single-cell boxes are
unwrapped into document content.

Use `--table-format html` (Python: `table_format="html"`) to preserve merged
cells with `rowspan` and `colspan`. This option emits HTML for all tables,
including single-cell boxes, and does not assume that the first row is a
header. Text formatting, links, images and line breaks are retained. Nested
tables remain inside their parent cells, with paragraphs before, between and
after them kept in order. Numbered and bulleted lists become HTML lists with
their starts, restarts and nesting preserved. Cells containing lists keep
surrounding paragraphs and tables in order; simple text-only cells still use
line breaks between paragraphs. Equations retain LaTeX text.
Pipe-table output retains nested table content as readable text with a
`nested-table-flattened` warning. Lists in pipe tables remain readable labels
separated by line breaks, without automatic numbering or nesting.

Word stores list items and their continuation paragraphs as siblings.
In HTML cells, an unnumbered paragraph or table joins the preceding item only
when its explicit indentation matches the item's content indentation. The
item indent comes from its paragraph or numbering definition, defaulting to
half an inch per level. Unindented content stays outside the list. Continuation
indentation inherited only from a paragraph style is not resolved.

HTML mode requires a Markdown renderer that permits raw HTML. Tables containing
footnote/endnote references fall back to pipe tables with an
`html-table-fallback` warning, because those Markdown references would not be
resolved inside raw HTML. This fallback applies to the containing table and
all its nested tables; note content remains available.

Markdown → DOCX recognizes HTML table blocks automatically and reconstructs
native Word tables with `gridSpan` and `vMerge`. Cells support literal text,
common inline formatting, paragraphs, line breaks, preformatted text, links,
local/data-URI images, nested tables, and ordered/bulleted lists at multiple
levels. Paragraphs, lists and nested tables retain their order. List items may
contain several paragraphs, preformatted text, sublists and tables. Inner
table grids and images are sized to the available width of their parent cell.
Remote images use the existing
link-only behavior.
`th` cells are bold; leading header rows repeat across pages. Captions are
retained as paragraphs before the table. Basic `align` and CSS `text-align`
values are supported; general CSS, borders, widths, shading and page layout
are not restored.

HTML row groups are respected, including `rowspan="0"` through the remaining
rows of its group. Spans extending past explicit rows are shortened; invalid
span values default to 1; overlapping cells move to the next available grid
position. These repairs produce `html-table-approximated` warnings.
HTML `ol start` and `li value` become native Word numbering starts/restarts;
separate lists have independent numbering. Ordered HTML lists use decimal
markers at every depth. Non-decimal `ol type` values normalize to decimal;
negative values become visible text labels in bullet items. Reversed lists
retain their values using individual numbering restarts rather than a
descending counter. Nesting beyond Word's nine levels is flattened at level
nine. These approximations, invalid numbering attributes and malformed list
content produce the same warning. An HTML table without usable rows falls
back to readable text.
This is a table importer, not a general HTML/CSS layout engine. Markdown syntax
inside raw HTML cells stays literal, as it does in normal raw HTML blocks.

Merged-cell spans, nested table hierarchy and supported cell lists survive
DOCX → HTML-in-Markdown → DOCX. Other layout and cell-block distinctions remain
subject to the approximations above.

Grid handling follows the OOXML definitions of
[column spans](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.gridspan)
and [vertical merges](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.verticalmerge).
The output choices reflect the limits of [GFM pipe tables](https://github.github.com/gfm/#tables-extension-).
HTML span parsing follows the [HTML table model](https://html.spec.whatwg.org/multipage/tables.html#processing-model-1),
with the explicit repair behavior described above.

## List numbering

Each Word numbering instance (`numId`) has independent counters, even when
several instances share an abstract list definition. Returning to the same
instance continues its counters. The converter respects per-level starts,
`startOverride`, replacement `lvl` definitions and `lvlRestart` (including
zero, which disables restarting). List nesting follows logical levels rather
than visual indentation. Missing numbering definitions retain the paragraph's
text and produce a warning instead of borrowing an unrelated level.

Decimal labels such as `3.` and `3)` become ordered Markdown lists. Invisible
HTML comments separate adjacent independent lists so Markdown renderers do not
merge them or ignore their starting values. These comments also allow nested
lists to start at values other than 1.

Roman, alphabetic, zero-padded and compound labels cannot be expressed as
ordinary CommonMark list markers. Their visible labels are retained as text
inside bullet items, for example `- IV. Introduction` or `- 2.3 Scope`, with a
`numbering-label-as-text` warning. They will return as bullet lists on a round
trip to DOCX; original automatic numbering is not reconstructed. Heading
labels remain heading text. Unknown number formats fall back to decimal with
an `unsupported-numbering-format` warning. Custom picture bullets, number-font
styling and section-specific numbering extensions are not preserved.

The restart and override behavior follows the OOXML definitions of
[level restarts](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.levelrestart)
and [start overrides](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.startoverridenumberingvalue).
Markdown list boundaries follow the [GFM list rules](https://github.github.com/gfm/#lists).

## Conversion warnings

Word → Markdown reports include diagnostic details for the cases below. The
normal CLI report prints them; `--json` adds a `warnings` array alongside the
existing `percent`, `total` and `features` fields. Each warning contains `code`,
`message` and `part` (the source path within the DOCX package, or `null`). Python
callers can inspect `result.report.warnings`. `--quiet` still suppresses reports.

| Code | Meaning |
| --- | --- |
| `imported-html-as-text` | Imported HTML was approximated as readable plain text. |
| `unconverted-import` | An import is unsupported, unreadable, missing or has an invalid relationship. |
| `unsupported-math` | An equation contains an unhandled OMML construct. |
| `missing-hyperlink-target` | Link text was retained, but its relationship target is missing. |
| `missing-note` | A referenced footnote/endnote has no readable definition; a placeholder was emitted. |
| `missing-image` | An image relationship or its packaged data is missing. |
| `plain-text-fallback` | An unexpected conversion error forced a block to plain text. |
| `missing-numbering` | A list instance or level could not be resolved; paragraph text was retained. |
| `unsupported-numbering-format` | An unsupported numbering format was approximated using decimal values. |
| `numbering-label-as-text` | A label Markdown cannot express was preserved as text inside a bullet item. |
| `merged-table-flattened` | Merged cells were flattened into pipe-table grid positions. |
| `invalid-table-structure` | Invalid grid values or unmatched merges were repaired without dropping cell text. |
| `merged-cell-content-moved` | Content from merged continuation cells was retained at the merge origin. |
| `nested-table-flattened` | A nested table was retained as readable text in its parent cell. |
| `html-table-fallback` | HTML output fell back to a pipe table to preserve Markdown note references. |

Numbering warnings are emitted once per affected instance and level in each
document part, rather than repeated for every list item.

Markdown → DOCX also reports `html-table-approximated` when an HTML table needs
span repairs or list-numbering approximations. These warnings
appear in `result.report.warnings` and the normal CLI report.

These cases also count as approximated or unsupported features. Warnings are
not yet exhaustive: other limitations may appear only in the feature counts,
and unrecognized structures can still escape detection. A successful conversion
or 100% coverage is not a guarantee of lossless output.

For planned improvements, see [ROADMAP.md](ROADMAP.md).
