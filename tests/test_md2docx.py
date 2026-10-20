"""Markdown to Word smoke tests, including a semantic round trip."""
import io
import zipfile

from doctomd import convert_bytes


def test_markdown_to_valid_docx():
    from mdtodoc import convert
    result = convert('# Welcome\n\nHello **world**.\n')
    with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
        names = archive.namelist()
        assert 'word/document.xml' in names
        assert '[Content_Types].xml' in names
    roundtrip = convert_bytes(result.data)
    assert 'Welcome' in roundtrip.markdown
    assert 'Hello' in roundtrip.markdown


def test_markdown_cli(tmp_path):
    from mdtodoc.cli import main
    source = tmp_path / 'note.md'
    source.write_text('# Title\n\nA line.\n', encoding='utf-8')
    target = tmp_path / 'note.docx'
    assert main([str(source), '-o', str(target), '-q']) == 0
    assert target.is_file()
