"""Footnote/endnote relationships are local to each package part."""
import pytest

from doctomd import convert_bytes
from doctomd.xmlns import A_NS, M_NS, PIC_NS, R_NS, W_NS, WP_NS


def note_part(kind, body):
    return (
        f'<w:{kind}s xmlns:w="{W_NS}" xmlns:r="{R_NS}" xmlns:m="{M_NS}" '
        f'xmlns:a="{A_NS}" xmlns:pic="{PIC_NS}" xmlns:wp="{WP_NS}">'
        f'<w:{kind} w:id="1">{body}</w:{kind}></w:{kind}s>'
    )


@pytest.mark.parametrize('kind', ['footnote', 'endnote'])
def test_note_uses_its_own_hyperlink_relationship(docx_factory, relationships_xml, kind):
    result = convert_bytes(docx_factory(
        '<w:p><w:hyperlink r:id="shared"><w:r><w:t>Body link</w:t></w:r></w:hyperlink>'
        f'<w:r><w:{kind}Reference w:id="1"/></w:r></w:p>',
        relationships={
            'notes': (kind + 's', kind + 's.xml', False),
            'shared': ('hyperlink', 'https://example.org/body', True),
        },
        parts={
            f'word/{kind}s.xml': note_part(kind,
                '<w:p><w:hyperlink r:id="shared"><w:r><w:t>Note link</w:t></w:r></w:hyperlink></w:p>'),
            f'word/_rels/{kind}s.xml.rels': relationships_xml({
                'shared': ('hyperlink', 'https://example.org/note', True),
            }),
        },
    ))
    assert '[Body link](https://example.org/body)' in result.markdown
    assert '[^1]: [Note link](https://example.org/note)' in result.markdown
    assert result.report.warnings == []


@pytest.mark.parametrize('kind', ['footnote', 'endnote'])
def test_note_images_use_part_relative_paths(docx_factory, relationships_xml, kind):
    result = convert_bytes(docx_factory(
        f'<w:p><w:r><w:{kind}Reference w:id="1"/></w:r></w:p>',
        relationships={'notes': (kind + 's', f'notes/{kind}s.xml', False)},
        parts={
            f'word/notes/{kind}s.xml': note_part(kind,
                '<w:p><w:r><w:drawing><wp:inline><pic:pic><pic:blipFill>'
                '<a:blip r:embed="picture"/></pic:blipFill></pic:pic></wp:inline>'
                '</w:drawing></w:r></w:p>'),
            f'word/notes/_rels/{kind}s.xml.rels': relationships_xml({
                'picture': ('image', '../media/picture.png', False),
            }),
            'word/media/picture.png': b'fixture image bytes',
        },
    ))
    assert '![image](media/picture.png)' in result.markdown
    assert result.images == {'picture.png': b'fixture image bytes'}
    assert result.report.warnings == []


@pytest.mark.parametrize('kind', ['footnote', 'endnote'])
def test_missing_note_is_visible_and_reported(docx_factory, kind):
    result = convert_bytes(docx_factory(f'<w:p><w:r><w:{kind}Reference w:id="42"/></w:r></w:p>'))
    assert '[^1]: *[Note content is missing]*' in result.markdown
    assert result.report.percent == 0
    assert result.report.warnings[0].code == 'missing-note'
    assert '42' in result.report.warnings[0].message


def test_missing_note_link_preserves_label_and_warns(docx_factory):
    result = convert_bytes(docx_factory(
        '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>',
        relationships={'notes': ('footnotes', 'footnotes.xml', False)},
        parts={'word/footnotes.xml': note_part('footnote',
            '<w:p><w:hyperlink r:id="missing"><w:r><w:t>Source</w:t></w:r></w:hyperlink></w:p>')},
    ))
    assert '[^1]: Source' in result.markdown
    assert result.report.percent < 100
    assert result.report.warnings[0].code == 'missing-hyperlink-target'
    assert result.report.warnings[0].part == 'word/footnotes.xml'


def test_equations_and_imports_inside_notes(docx_factory, relationships_xml):
    result = convert_bytes(docx_factory(
        '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>',
        relationships={'notes': ('footnotes', 'footnotes.xml', False)},
        parts={
            'word/footnotes.xml': note_part('footnote',
                '<m:oMathPara><m:oMath><m:r><m:t>x</m:t></m:r></m:oMath></m:oMathPara>'
                '<w:altChunk r:id="import"/>'),
            'word/_rels/footnotes.xml.rels': relationships_xml({
                'import': ('aFChunk', 'note.txt', False),
            }),
            'word/note.txt': b'Imported note text',
        },
    ))
    assert '[^1]: $$\n    x\n    $$' in result.markdown
    assert '    Imported note text' in result.markdown
    assert result.report.warnings == []


def test_footnotes_and_endnotes_can_reuse_relationship_ids(docx_factory, relationships_xml):
    parts = {}
    relationships = {}
    for kind in ('footnote', 'endnote'):
        relationships[kind] = (kind + 's', kind + 's.xml', False)
        parts[f'word/{kind}s.xml'] = note_part(kind,
            '<w:p><w:hyperlink r:id="shared"><w:r><w:t>Source</w:t></w:r></w:hyperlink></w:p>')
        parts[f'word/_rels/{kind}s.xml.rels'] = relationships_xml({
            'shared': ('hyperlink', 'https://example.org/' + kind, True),
        })
    result = convert_bytes(docx_factory(
        '<w:p><w:r><w:footnoteReference w:id="1"/><w:endnoteReference w:id="1"/>'
        '<w:footnoteReference w:id="1"/></w:r></w:p>',
        relationships=relationships, parts=parts,
    ))
    assert '[^1][^2][^1]' in result.markdown
    assert '[^1]: [Source](https://example.org/footnote)' in result.markdown
    assert '[^2]: [Source](https://example.org/endnote)' in result.markdown
    assert result.markdown.count('[^1]:') == 1
    assert result.report.warnings == []


def test_missing_note_image_is_reported(docx_factory):
    result = convert_bytes(docx_factory(
        '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>',
        relationships={'notes': ('footnotes', 'footnotes.xml', False)},
        parts={'word/footnotes.xml': note_part('footnote',
            '<w:p><w:r><w:drawing><wp:inline><pic:pic><pic:blipFill>'
            '<a:blip r:embed="missing"/></pic:blipFill></pic:pic></wp:inline>'
            '</w:drawing></w:r></w:p>')},
    ))
    assert result.report.percent < 100
    assert result.report.warnings[0].code == 'missing-image'
    assert result.report.warnings[0].part == 'word/footnotes.xml'
