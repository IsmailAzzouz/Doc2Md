"""HTML tables become native Word tables, including merged-cell round trips."""
import base64
import io
import zipfile

import pytest
from lxml import etree, html

from doctomd import convert_bytes
from doctomd.xmlns import W_NS
from mdtodoc import convert
from mdtodoc.cli import main


NS = {'w': W_NS, 'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6GQAAAAASUVORK5CYII=')


def document(result):
    with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
        return etree.fromstring(archive.read('word/document.xml'))


def xml_part(result, name):
    with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
        return etree.fromstring(archive.read(name))


def text(element):
    return ''.join(element.xpath('.//w:t/text()', namespaces=NS))


def cell_rows(result):
    table = document(result).find('.//w:tbl', NS)
    return [row.findall('w:tc', NS) for row in table.findall('w:tr', NS)]


def value(element, path):
    match = element.find(path, NS)
    return match.get(f'{{{W_NS}}}val') if match is not None else None


def test_html_table_produces_native_word_rows_and_columns():
    result = convert('<table><tr><td>A</td><td>B</td></tr><tr><td>C</td><td>D</td></tr></table>')
    assert [[text(cell) for cell in row] for row in cell_rows(result)] == [['A', 'B'], ['C', 'D']]
    assert len(document(result).findall('.//w:tblGrid/w:gridCol', NS)) == 2
    assert not result.report.warnings


def test_combined_rowspan_and_colspan_have_matching_continuations():
    source = ('<table><tr><td rowspan="3" colspan="2">Region</td><td>A</td></tr>'
              '<tr><td>B</td></tr><tr><td>C</td></tr></table>')
    result = convert(source)
    rows = cell_rows(result)
    assert [value(row[0], 'w:tcPr/w:vMerge') for row in rows] == ['restart', 'continue', 'continue']
    assert [value(row[0], 'w:tcPr/w:gridSpan') for row in rows] == ['2', '2', '2']
    assert [[text(cell) for cell in row] for row in rows] == [['Region', 'A'], ['', 'B'], ['', 'C']]
    widths = [int(node.get(f'{{{W_NS}}}w')) for node in document(result).findall('.//w:gridCol', NS)]
    assert int(rows[0][0].find('w:tcPr/w:tcW', NS).get(f'{{{W_NS}}}w')) == sum(widths[:2])


def test_cell_after_an_active_rowspan_keeps_its_column():
    source = ('<table><tr><td>A</td><td rowspan="2">B</td><td>C</td></tr>'
              '<tr><td>D</td><td>E</td></tr></table>')
    result = convert(source)
    assert [[text(cell) for cell in row] for row in cell_rows(result)] == [['A', 'B', 'C'], ['D', '', 'E']]
    assert value(cell_rows(result)[1][1], 'w:tcPr/w:vMerge') == 'continue'


def test_rowspan_zero_stops_at_row_group_boundary():
    source = ('<table><tbody><tr><td rowspan="0">First group</td><td>A</td></tr><tr><td>B</td></tr>'
              '</tbody><tbody><tr><td>Next group</td><td>C</td></tr></tbody></table>')
    rows = cell_rows(convert(source))
    assert [value(row[0], 'w:tcPr/w:vMerge') for row in rows] == ['restart', 'continue', None]
    assert text(rows[2][0]) == 'Next group'


def test_empty_rows_covered_by_spans_still_have_word_cells():
    result = convert('<table><tr><td rowspan="2" colspan="2">All</td></tr><tr></tr></table>')
    rows = cell_rows(result)
    assert len(rows[1]) == 1
    assert value(rows[1][0], 'w:tcPr/w:vMerge') == 'continue'
    assert rows[1][0].find('w:p', NS) is not None


def test_short_rows_are_padded_with_empty_cells():
    rows = cell_rows(convert('<table><tr><td>A</td><td>B</td></tr><tr><td>C</td></tr></table>'))
    assert [[text(cell) for cell in row] for row in rows] == [['A', 'B'], ['C', '']]


def test_header_groups_repeat_and_header_text_is_bold():
    source = ('<table><thead><tr><th colspan="2">Group</th></tr><tr><th>A</th><th>B</th></tr></thead>'
              '<tbody><tr><th scope="row">Row label</th><td>Value</td></tr></tbody></table>')
    result = convert(source)
    rows = document(result).findall('.//w:tbl/w:tr', NS)
    assert [row.find('w:trPr/w:tblHeader', NS) is not None for row in rows] == [True, True, False]
    assert rows[2].find('w:tc/w:p/w:r/w:rPr/w:b', NS) is not None
    assert rows[2].findall('w:tc', NS)[1].find('w:p/w:r/w:rPr/w:b', NS) is None


def test_footer_group_is_written_after_body():
    result = convert('<table><tfoot><tr><td>Footer</td></tr></tfoot><tbody><tr><td>Body</td></tr></tbody></table>')
    assert [text(row[0]) for row in cell_rows(result)] == ['Body', 'Footer']


@pytest.mark.parametrize('source', [
    '<table>\n<tr><td>A</td></tr>\n\n<tr><td>B</td></tr>\n</table>',
    '<TABLE>\n<TR><TD>A</TD></TR>\n\n<TR><TD>B</TD></TR>\n</TABLE>',
    '> <table>\n> <tr><td>A</td></tr>\n>\n> <tr><td>B</td></tr>\n> </table>',
])
def test_multiline_html_tables_allow_blank_lines(source):
    result = convert(source)
    assert [text(row[0]) for row in cell_rows(result)] == ['A', 'B']
    assert len(document(result).findall('.//w:tbl', NS)) == 1


def test_surrounding_html_captions_and_multiple_tables_keep_their_order():
    source = ('<div><p>Before</p><table><caption>Caption</caption><tr><td>First</td></tr></table>'
              '<p>Between</p><table><tr><td>Second</td></tr></table><p>After</p></div>')
    body = document(convert(source)).find('w:body', NS)
    assert [text(child) for child in body if text(child)] == ['Before', 'Caption', 'First', 'Between', 'Second', 'After']


def test_table_does_not_consume_markdown_after_its_closing_tag():
    result = convert('<table><tr><td>Cell</td></tr></table>\n# Next heading\n\nAfter')
    assert document(result).find('.//w:pStyle[@w:val="Heading1"]', NS) is not None
    assert text(document(result)).endswith('Next headingAfter')


@pytest.mark.parametrize('fence', ['```html\n{}\n```', '    {}'])
def test_html_in_code_is_not_converted_to_a_table(fence):
    result = convert(fence.format('<table><tr><td>Example</td></tr></table>'))
    assert not document(result).findall('.//w:tbl', NS)
    assert '<table>' in text(document(result))


def test_literal_markdown_html_entities_and_paragraph_breaks_in_cells():
    source = ('<table><tr><td><p>**literal** &amp; &lt;tag&gt;</p>'
              '<p><strong>Bold</strong> <em>Italic</em><br>Second line</p></td></tr></table>')
    cell = cell_rows(convert(source))[0][0]
    paragraphs = cell.findall('w:p', NS)
    assert len(paragraphs) == 2
    assert text(paragraphs[0]) == '**literal** & <tag>'
    assert paragraphs[0].find('.//w:b', NS) is None
    assert paragraphs[1].find('.//w:b', NS) is not None
    assert paragraphs[1].find('.//w:i', NS) is not None
    assert len(paragraphs[1].findall('.//w:br', NS)) == 1


def test_cell_alignment_and_inline_styles_survive():
    result = convert('<table><tr><td style="text-align: center"><u>U</u><sup>2</sup><sub>3</sub>'
                     '<s>Old</s><mark>Mark</mark><code>code</code></td><td align="right">R</td></tr></table>')
    cells = cell_rows(result)[0]
    assert [value(cell, 'w:p/w:pPr/w:jc') for cell in cells] == ['center', 'right']
    assert value(cells[0], './/w:u') == 'single'
    assert cells[0].find('.//w:strike', NS) is not None
    assert value(cells[0], './/w:highlight') == 'yellow'
    assert value(cells[0], './/w:rStyle') == 'CodeChar'


def test_preformatted_cell_content_preserves_spaces_and_newlines():
    cell = cell_rows(convert('<table><tr><td><pre>  first\n    second</pre></td></tr></table>'))[0][0]
    assert cell.xpath('.//w:t/text()', namespaces=NS) == ['  first', '    second']
    assert cell.find('.//w:br', NS) is not None
    assert value(cell, './/w:rStyle') == 'CodeChar'


def test_nested_formatting_and_header_bold_do_not_end_early():
    source = ('<table><tr><th><b>Header</b> tail</th></tr>'
              '<tr><td><strong>First<b>Second</b>Third</strong> plain</td></tr></table>')
    rows = cell_rows(convert(source))
    assert all(run.find('w:rPr/w:b', NS) is not None for run in rows[0][0].findall('.//w:r', NS))
    runs = rows[1][0].findall('.//w:r', NS)
    assert [run.find('w:rPr/w:b', NS) is not None for run in runs] == [True, True, True, False]


def test_html_without_explicit_cell_closing_tags_is_recovered():
    rows = cell_rows(convert('<table><tr><td>A<td>B<tr><td>C<td>D</table>'))
    assert [[text(cell) for cell in row] for row in rows] == [['A', 'B'], ['C', 'D']]


def test_html_table_without_usable_rows_keeps_text_and_warns():
    result = convert('<table><caption>Caption</caption><td>Keep me</td></table>')
    assert text(document(result)) == 'CaptionKeep me'
    assert result.report.warnings[0].code == 'html-table-approximated'


def test_table_links_use_relationships_and_later_markdown_heading_anchors():
    source = ('<table><tr><td><a href="https://example.org/?a=1&amp;b=2">External</a>'
              '<a href="#later">Internal</a></td></tr></table>\n\n# Later')
    result = convert(source)
    links = document(result).findall('.//w:hyperlink', NS)
    assert len(links) == 2
    assert links[1].get(f'{{{W_NS}}}anchor') == '_md0'
    relationships = xml_part(result, 'word/_rels/document.xml.rels')
    assert any(rel.get('Target') == 'https://example.org/?a=1&b=2' for rel in relationships)


@pytest.mark.parametrize('embedded', [False, True])
def test_html_cell_images_reuse_existing_embedding(tmp_path, embedded):
    (tmp_path / 'pixel.png').write_bytes(PNG)
    src = 'data:image/png;base64,' + base64.b64encode(PNG).decode() if embedded else 'pixel.png'
    result = convert(f'<table><tr><td colspan="2"><img src="{src}" alt="Pixel &amp; dot"></td></tr></table>', tmp_path)
    assert document(result).find('.//w:drawing', NS) is not None
    with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
        assert archive.read('word/media/image1.png') == PNG


def test_remote_cell_images_are_linked_without_downloading():
    result = convert('<table><tr><td><img src="https://example.org/picture.png" alt="Remote"></td></tr></table>')
    assert document(result).find('.//w:hyperlink', NS) is not None
    assert document(result).find('.//w:drawing', NS) is None
    assert result.report.c[('part', 'remote images (linked, not embedded)')] == 1


def test_html_table_inside_a_footnote_keeps_its_reference_and_structure():
    result = convert('Reference[^1]\n\n[^1]: <table><tr><td colspan="2">Note table</td></tr></table>')
    footnotes = xml_part(result, 'word/footnotes.xml')
    note = footnotes.find('w:footnote[@w:id="1"]', NS)
    assert note.find('.//w:footnoteRef', NS) is not None
    assert value(note, './/w:tcPr/w:gridSpan') == '2'
    assert 'Note table' in text(note)


@pytest.mark.parametrize('attributes', ['colspan="bad"', 'colspan="0"', 'colspan="-2"', 'rowspan="bad"', 'rowspan="4"'])
def test_invalid_or_oversized_spans_keep_text_and_warn(attributes):
    result = convert(f'<table><tr><td {attributes}>Keep</td><td>Other</td></tr></table>')
    assert [text(cell) for cell in cell_rows(result)[0]] == ['Keep', 'Other']
    assert result.report.warnings[0].code == 'html-table-approximated'


def test_overlapping_spans_are_repaired_without_dropping_cells():
    source = ('<table><tr><td>A</td><td rowspan="2">B</td></tr>'
              '<tr><td colspan="2">Moved</td></tr></table>')
    result = convert(source)
    assert 'Moved' in text(document(result))
    assert len(document(result).findall('.//w:gridCol', NS)) == 4
    assert 'Overlapping' in result.report.warnings[0].message


def test_nested_tables_are_flattened_once_with_a_warning():
    result = convert('<table><tr><td>Outer<table><tr><td>Inner A</td><td>Inner B</td></tr></table>'
                     'After</td></tr></table>')
    assert len(document(result).findall('.//w:tbl', NS)) == 1
    assert text(document(result)).count('Inner A') == 1
    assert 'After' in text(document(result))
    assert 'nested' in result.report.warnings[0].message


def test_script_and_style_content_is_not_imported_as_cell_text():
    result = convert('<table><tr><td>A<script>hidden()</script><style>.hidden{}</style>B</td></tr></table>')
    assert text(cell_rows(result)[0][0]) == 'AB'


def test_ordinary_markdown_tables_still_work_with_shared_writer():
    result = convert('| Name | Value |\n| :--- | ---: |\n| **Bold** | 42 |')
    rows = cell_rows(result)
    assert [[text(cell) for cell in row] for row in rows] == [['Name', 'Value'], ['Bold', '42']]
    assert value(rows[1][1], 'w:p/w:pPr/w:jc') == 'right'
    assert rows[1][0].find('.//w:b', NS) is not None


def test_html_spans_survive_word_to_markdown_roundtrip():
    source = ('<table><tr><td rowspan="2" colspan="2"><strong>Group</strong><br>Details</td><td>A</td></tr>'
              '<tr><td>B</td></tr></table>')
    first = convert(source)
    markdown = convert_bytes(first.data, table_format='html').markdown
    second = convert(markdown)
    assert etree.tostring(document(first).find('.//w:tbl', NS)) == etree.tostring(document(second).find('.//w:tbl', NS))
    output = html.fromstring(convert_bytes(second.data, table_format='html').markdown)
    assert output.xpath('.//td[@rowspan="2"][@colspan="2"]')[0].text_content() == 'GroupDetails'


def test_doc2md_export_reconstructs_original_word_merge_geometry(docx_factory):
    body = ('<w:tbl><w:tblGrid><w:gridCol/><w:gridCol/><w:gridCol/></w:tblGrid>'
            '<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/><w:vMerge w:val="restart"/></w:tcPr>'
            '<w:p><w:r><w:t>Origin</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>A</w:t></w:r></w:p></w:tc></w:tr>'
            '<w:tr><w:tc><w:tcPr><w:gridSpan w:val="2"/><w:vMerge/></w:tcPr><w:p/>'
            '</w:tc><w:tc><w:p><w:r><w:t>B</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    exported = convert_bytes(docx_factory(body), table_format='html')
    rows = cell_rows(convert(exported.markdown))
    assert [value(row[0], 'w:tcPr/w:gridSpan') for row in rows] == ['2', '2']
    assert [value(row[0], 'w:tcPr/w:vMerge') for row in rows] == ['restart', 'continue']
    assert [[text(cell) for cell in row] for row in rows] == [['Origin', 'A'], ['', 'B']]


def test_cli_converts_html_tables_without_an_extra_flag(tmp_path):
    source, target = tmp_path / 'table.md', tmp_path / 'table.docx'
    source.write_text('<table><tr><td colspan="2">Merged</td></tr></table>', encoding='utf-8')
    assert main([str(source), '-o', str(target), '-q']) == 0
    with zipfile.ZipFile(target) as archive:
        root = etree.fromstring(archive.read('word/document.xml'))
    assert value(root, './/w:tcPr/w:gridSpan') == '2'
