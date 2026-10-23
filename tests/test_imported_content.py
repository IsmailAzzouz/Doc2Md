"""Imported content must survive as text or leave an explicit loss indication."""
import json

import pytest

from doctomd import convert_bytes
from doctomd.cli import main


@pytest.fixture
def imported_docx(docx_factory):
    def build(data, content_type='text/html', *, target='imports/chunk.bin'):
        return docx_factory(
            '<w:p><w:r><w:t>Before</w:t></w:r></w:p>'
            '<w:altChunk r:id="import"/>'
            '<w:p><w:r><w:t>After</w:t></w:r></w:p>',
            relationships={'import': ('aFChunk', target, False)},
            parts={'word/' + target: data},
            content_types={'word/' + target: content_type},
        )
    return build


def test_html_text_is_preserved_in_document_order(imported_docx):
    result = convert_bytes(imported_docx(
        '<html><head><title>Page title</title><style>SECRET CSS</style></head>'
        '<body><h1>Imported heading</h1><p>Hello <b>world</b> &amp; café.</p>'
        '<script>SECRET SCRIPT</script><ul><li>First</li><li>Second</li></ul>'
        '<table><tr><td>Left</td><td>Right</td></tr></table>'
        '<img src="https://example.org/image.png" alt="Diagram"/></body></html>'
    ))
    expected = ['Before', 'Imported heading', 'Hello world & café.', 'First', 'Second',
                'Left', 'Right', 'Diagram', 'After']
    positions = [result.markdown.index(text) for text in expected]
    assert positions == sorted(positions)
    assert 'SECRET' not in result.markdown
    assert 'Page title' not in result.markdown
    assert '<script>' not in result.markdown
    assert result.report.percent < 100
    warning = result.report.warnings[0]
    assert warning.code == 'imported-html-as-text'
    assert warning.part == 'word/imports/chunk.bin'


@pytest.mark.parametrize('data, content_type, expected', [
    ('Résumé'.encode(), 'text/plain', 'Résumé'),
    ('Résumé'.encode('utf-16'), 'text/plain', 'Résumé'),
    ('Résumé'.encode('utf-32'), 'text/plain', 'Résumé'),
    ('Résumé'.encode('utf-8-sig'), 'text/plain', 'Résumé'),
    ('Résumé'.encode('cp1252'), 'text/plain; charset=windows-1252', 'Résumé'),
    (b'<meta charset="windows-1252"><p>R\xe9sum\xe9</p>', 'text/html', 'Résumé'),
    (b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">'
     b'<p>R\xe9sum\xe9</p>', 'text/html', 'Résumé'),
    (b'<p>R\xe9sum\xe9</p>', 'text/html; charset=windows-1252', 'Résumé'),
    ('<p>Résumé</p>'.encode('utf-16'), 'text/html', 'Résumé'),
    (b'<?xml version="1.0" encoding="UTF-8"?><html xmlns="http://www.w3.org/1999/xhtml">'
     b'<body><p>XHTML text</p></body></html>', 'application/xhtml+xml', 'XHTML text'),
])
def test_import_encodings(imported_docx, data, content_type, expected):
    result = convert_bytes(imported_docx(data, content_type))
    assert expected in result.markdown
    assert not any(warning.code == 'unconverted-import' for warning in result.report.warnings)


def test_plain_text_is_escaped_as_text(imported_docx):
    result = convert_bytes(imported_docx(b'# Not a heading\r\n\r\n<script>literal</script>', 'text/plain'))
    assert '\\# Not a heading' in result.markdown
    assert '\\<script>literal\\</script>' in result.markdown
    assert '\r' not in result.markdown
    assert result.report.percent == 100
    assert result.report.warnings == []


@pytest.mark.parametrize('data, content_type', [
    (b'{\\rtf1 Unsupported}', 'application/rtf'),
    (b'not a supported document', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    (b'\xffinvalid', 'text/plain'),
    (b'hello', 'text/plain; charset=not-a-real-encoding'),
    (b'unknown', 'application/octet-stream'),
])
def test_unreadable_imports_are_visible_and_reported(imported_docx, data, content_type):
    result = convert_bytes(imported_docx(data, content_type))
    assert result.markdown == 'Before\n\n*[Imported content could not be converted]*\n\nAfter\n'
    assert result.report.percent < 100
    assert result.report.warnings[0].code == 'unconverted-import'
    assert 'unconverted-import' in result.report.format()


@pytest.mark.parametrize('relationships', [
    {},
    {'import': ('aFChunk', 'missing.html', False)},
    {'import': ('aFChunk', 'https://example.org/import.html', True)},
    {'import': ('image', 'wrong.html', False)},
])
def test_invalid_import_relationships_are_reported(docx_factory, relationships):
    result = convert_bytes(docx_factory('<w:altChunk r:id="import"/>', relationships=relationships))
    assert 'Imported content could not be converted' in result.markdown
    assert result.report.percent == 0
    assert result.report.warnings[0].part == 'word/document.xml'


def test_declared_content_type_wins_over_filename(imported_docx):
    result = convert_bytes(imported_docx(b'<p>Literal markup</p>', 'text/plain', target='chunk.html'))
    assert '\\<p>Literal markup\\</p>' in result.markdown
    assert result.report.warnings == []


def test_default_content_type_is_used(docx_factory):
    result = convert_bytes(docx_factory(
        '<w:altChunk r:id="import"/>',
        relationships={'import': ('aFChunk', 'chunk.data', False)},
        parts={
            'word/chunk.data': b'Imported text',
            '[Content_Types].xml':
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="data" ContentType="text/plain"/></Types>',
        },
    ))
    assert result.markdown == 'Imported text\n'
    assert result.report.warnings == []


@pytest.mark.parametrize('json_report', [False, True])
def test_cli_reports_import_loss(imported_docx, tmp_path, capsys, json_report):
    source = tmp_path / 'import.docx'
    source.write_bytes(imported_docx(b'{\\rtf1 Text}', 'application/rtf'))
    arguments = [str(source), '-o', '-'] + (['--json'] if json_report else [])
    assert main(arguments) == 0
    captured = capsys.readouterr()
    assert 'Imported content could not be converted' in captured.out
    assert 'unconverted-import' in captured.err
    if json_report:
        report = json.loads(captured.err.splitlines()[-1])
        assert report['percent'] < 100
        assert report['warnings'][0]['code'] == 'unconverted-import'
        assert report['warnings'][0]['part'] == 'word/imports/chunk.bin'
