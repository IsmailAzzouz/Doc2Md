"""Minimal integration tests with a synthetic, non-confidential OOXML fixture."""
import io
import zipfile

import pytest

from doctomd import DocError, convert_bytes
from doctomd.cli import main


def make_docx():
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as archive:
        archive.writestr('word/document.xml',
                         '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                         '<w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
                         '<w:r><w:t>Example</w:t></w:r></w:p>'
                         '<w:p><w:r><w:t>Hello from Word</w:t></w:r></w:p>'
                         '</w:body></w:document>')
    return out.getvalue()


def test_docx_to_markdown():
    result = convert_bytes(make_docx())
    assert 'Hello from Word' in result.markdown
    assert 'Example' in result.markdown
    assert result.report.total >= 0


def test_non_word_zip_raises():
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('random.txt', 'Not a Word file')
    with pytest.raises(DocError):
        convert_bytes(output.getvalue())


def test_cli_file(tmp_path):
    src = tmp_path / 'example.docx'
    src.write_bytes(make_docx())
    dest = tmp_path / 'example.md'
    assert main([str(src), '-o', str(dest), '-q']) == 0
    assert 'Hello from Word' in dest.read_text(encoding='utf-8')


def test_cli_features(capsys):
    assert main(['--features']) == 0
    assert 'Headings' in capsys.readouterr().out
