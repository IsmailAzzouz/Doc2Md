# Limitations and compatibility

Doc2Md targets **semantic content** rather than visual/page-perfect fidelity.
A round trip through Markdown will not reproduce the original page layout.

| Feature | Word → Markdown | Markdown → DOCX |
| --- | --- | --- |
| Headings, text formatting, links | Supported for common cases | Supported for common cases |
| Lists | Independent counters, restarts and level overrides; see numbering details below | Common Markdown lists with predefined Word numbering styles |
| Tables | Pipe-table output; merged cells flattened | Markdown tables; no general complex cell spans |
| Images | Embedded images extracted or optionally inlined | Local/data URI raster images; remote URLs linked |
| Equations | Common Word OMML converted to LaTeX | Supported LaTeX subset converted to OMML; other syntax may remain literal |
| Footnotes and endnotes | Text, links and images use each note part's relationships | Markdown footnotes; endnote distinction is not restored |
| Imported content (`altChunk`) | Plain text preserved; HTML reduced to text with a warning; other formats get a placeholder | Not reconstructed |
| SmartArt and embedded objects | Text or preview image, if present | Not reconstructed |
| Charts and comments | Unsupported / content may be lost | No native reconstruction |
| Page design (fonts, margins, headers, page breaks, columns) | Intentionally not preserved | Uses predefined DOCX styles and page size |
| Legacy Word formats | Requires LibreOffice or Microsoft Word | DOCX output only |

Known caveats:

- Markdown cannot encode many Word presentation features; tables with merged
  cells, floating shapes and text wrapping are approximated or discarded.
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

Numbering warnings are emitted once per affected instance and level in each
document part, rather than repeated for every list item.

These cases also count as approximated or unsupported features. Warnings are
not yet exhaustive: other limitations may appear only in the feature counts,
and unrecognized structures can still escape detection. A successful conversion
or 100% coverage is not a guarantee of lossless output.

For planned improvements, see [ROADMAP.md](ROADMAP.md).
