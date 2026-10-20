# Limitations and compatibility

Doc2Md targets **semantic content** rather than visual/page-perfect fidelity.
A round trip through Markdown will not reproduce the original page layout.

| Feature | Word → Markdown | Markdown → DOCX |
| --- | --- | --- |
| Headings, text formatting, lists, links | Supported for common cases | Supported for common cases |
| Tables | Pipe-table output; merged cells flattened | Markdown tables; no general complex cell spans |
| Images | Embedded images extracted or optionally inlined | Local/data URI raster images; remote URLs linked |
| Equations | Common Word OMML converted to LaTeX | Supported LaTeX subset converted to OMML; other syntax may remain literal |
| Footnotes | Supported for common documents | Supported via Markdown footnote syntax |
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

For planned improvements, see [ROADMAP.md](ROADMAP.md).
