# Changelog

All notable user-facing changes will be summarized here. Versioning follows
[Semantic Versioning](https://semver.org/) where practical; prior to `1.0`,
minor releases may change APIs.

## [Unreleased]

- Fix independent list counters, multilevel restart rules, start overrides and
  replacement level definitions. Resolve numbering-style links and preserve
  logical list nesting and adjacent list boundaries in rendered Markdown.
- Preserve Roman, alphabetic and compound list labels as text with explicit
  approximation warnings; report missing definitions and unsupported formats.
- Preserve body-level equations and resolve footnote/endnote links and images
  against their own package relationships.
- Preserve plain-text imports and readable HTML text from `altChunk`; show a
  placeholder for unsupported or unreadable imports.
- Add source-aware conversion warnings to text and JSON reports for import,
  equation and missing-content losses, with synthetic DOCX regression tests.
- Fix build with recent setuptools by removing the obsolete license classifier.
- Simplify CI and releases to one Alpine container job each; remove Dependabot automation.

- Initial import of the bidirectional converters from the supplied source suite.
- Python packaging and console scripts.
- Automated CI, tag-based GitHub release workflow, smoke tests and governance docs.

## [0.1.0] - TBD

Initial public release; release date assigned when `v0.1.0` is published.
