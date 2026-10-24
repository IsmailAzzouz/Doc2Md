"""Nested table structure, cell order and resources survive both converters."""
import base64
import io
import zipfile
from html import escape

import pytest
from lxml import etree, html
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

from doctomd import convert_bytes
from doctomd.xmlns import W_NS, R_NS, WP_NS, A_NS, PIC_NS
from mdtodoc import convert


NS = {'w': W_NS, 'wp': WP_NS}
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6GQAAAAASUVORK5CYII=')


def word_xml(result, part='word/document.xml'):
    with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
        return etree.fromstring(archive.read(part))


def text(element):
    return ''.join(element.xpath('.//w:t/text()', namespaces=NS))


def html_output(result):
    renderer = MarkdownIt('commonmark').enable('table').use(footnote_plugin)
    return html.fragment_fromstring(renderer.render(result.markdown), create_parent='div')


def paragraph(value):
    return f'<w:p><w:r><w:t>{escape(value)}</w:t></w:r></w:p>'


def cell(body, properties=''):
    return f'<w:tc><w:tcPr>{properties}</w:tcPr>{body}</w:tc>'


def table(*rows):
    return '<w:tbl>' + ''.join(f'<w:tr>{row}</w:tr>' for row in rows) + '</w:tbl>'


def wrap_html(body, side=''):
    side_cell = f'<td>{side}</td>' if side else ''
    return f'<table><tr><td>{body}</td>{side_cell}</tr></table>'


def nonempty_cell_blocks(element):
    return [(etree.QName(child).localname, text(child)) for child in element
            if child.tag != f'{{{W_NS}}}tcPr' and (text(child) or child.tag == f'{{{W_NS}}}tbl')]


@pytest.mark.parametrize('depth', [1, 2, 4])
def test_multiple_levels_survive_html_word_markdown_roundtrips(depth):
    source = '<p>Leaf</p>'
    for level in reversed(range(depth)):
        source = wrap_html(f'<p>Before {level}</p>{source}<p>After {level}</p>')
    first = convert(source)
    exported = convert_bytes(first.data, table_format='html')
    second = convert(exported.markdown)
    assert len(word_xml(first).findall('.//w:tbl', NS)) == depth
    assert len(word_xml(second).findall('.//w:tbl', NS)) == depth
    assert len(html_output(exported).xpath('.//table')) == depth
    assert text(word_xml(first)) == text(word_xml(second))
    assert not first.report.warnings
    assert not exported.report.warnings
    assert not second.report.warnings
    assert '\x00' not in exported.markdown


def test_word_cell_order_and_required_final_paragraph():
    source = wrap_html('<p>Before</p>' + wrap_html('Inner') + '<p>After</p>')
    root = word_xml(convert(source))
    outer_cell = root.find('.//w:tbl/w:tr/w:tc', NS)
    assert nonempty_cell_blocks(outer_cell) == [('p', 'Before'), ('tbl', 'Inner'), ('p', 'After')]
    assert outer_cell[-1].tag == f'{{{W_NS}}}p'
    only_table = word_xml(convert(wrap_html(wrap_html('Inner'))))
    assert only_table.find('.//w:tbl/w:tr/w:tc', NS)[-1].tag == f'{{{W_NS}}}p'


def test_docx_export_keeps_paragraphs_before_between_and_after_nested_tables(docx_factory):
    body = paragraph('Before') + table(cell(paragraph('First'))) + paragraph('Between')
    body += table(cell(paragraph('Second'))) + paragraph('After')
    result = convert_bytes(docx_factory(table(cell(body))), table_format='html')
    outer_cell = html_output(result).xpath('./table/tr/td')[0]
    assert [(child.tag, child.text_content()) for child in outer_cell] == [
        ('p', 'Before'), ('table', 'First'), ('p', 'Between'), ('table', 'Second'), ('p', 'After')]
    assert result.report.c[('ok', 'nested tables')] == 2
    assert not result.report.warnings


def test_adjacent_nested_tables_remain_separate_in_word_and_html():
    source = wrap_html(wrap_html('First') + wrap_html('Second'))
    first = convert(source)
    outer_cell = word_xml(first).find('.//w:tbl/w:tr/w:tc', NS)
    assert [etree.QName(child).localname for child in outer_cell] == ['tcPr', 'tbl', 'p', 'tbl', 'p']
    exported = html_output(convert_bytes(first.data, table_format='html'))
    assert [child.text_content() for child in exported.xpath('./table/tr/td/table')] == ['First', 'Second']


def test_inner_and_outer_merge_geometry_are_independent():
    inner = ('<table><tr><td colspan="2" rowspan="2">Inner merge</td><td>A</td></tr>'
             '<tr><td>B</td></tr></table>')
    source = ('<table><tr><td colspan="2" rowspan="2"><p>Before</p>' + inner +
              '<p>After</p></td><td>Outer A</td></tr><tr><td>Outer B</td></tr></table>')
    result = convert(source)
    for table_element in word_xml(result).findall('.//w:tbl', NS):
        rows = table_element.findall('w:tr', NS)
        assert len(rows) == 2
        for index, row in enumerate(rows):
            properties = row.find('w:tc/w:tcPr', NS)
            assert properties.find('w:gridSpan', NS).get(f'{{{W_NS}}}val') == '2'
            assert properties.find('w:vMerge', NS).get(f'{{{W_NS}}}val') == ('restart' if index == 0 else 'continue')
    exported = html_output(convert_bytes(result.data, table_format='html'))
    assert len(exported.xpath('.//td[@rowspan="2"][@colspan="2"]')) == 2
    assert len(exported.xpath('./table/tr/td/table/tr/td[@rowspan="2"]')) == 1


def test_nested_table_and_images_fit_the_parent_cell(tmp_path):
    (tmp_path / 'pixel.png').write_bytes(PNG)
    inner = '<table><tr>' + ''.join(f'<td>Column {index}<img src="pixel.png"></td>' for index in range(8)) + '</tr></table>'
    source = wrap_html(wrap_html(inner, 'Middle side'), 'Outer side')
    root = word_xml(convert(source, tmp_path))
    for nested in root.xpath('.//w:tc/w:tbl', namespaces=NS):
        parent_width = int(nested.getparent().find('w:tcPr/w:tcW', NS).get(f'{{{W_NS}}}w'))
        widths = [int(column.get(f'{{{W_NS}}}w')) for column in nested.findall('w:tblGrid/w:gridCol', NS)]
        assert sum(widths) <= parent_width - 216
        assert all(width > 0 for width in widths)
        assert nested.find('w:tblPr/w:tblInd', NS) is None
    for extent in root.findall('.//wp:extent', NS):
        parent_cell = next(extent.iterancestors(f'{{{W_NS}}}tc'))
        width = int(parent_cell.find('w:tcPr/w:tcW', NS).get(f'{{{W_NS}}}w'))
        assert int(extent.get('cx')) <= max(width - 216, 1) * 635


def test_nested_caption_and_formatting_stay_in_document_order():
    inner = '<table><caption>Caption</caption><tr><td><strong>Bold</strong><br><em>Italic</em></td></tr></table>'
    first = convert(wrap_html('<p>Before</p>' + inner + '<p>After</p>'))
    outer_cell = word_xml(first).find('.//w:tbl/w:tr/w:tc', NS)
    assert nonempty_cell_blocks(outer_cell) == [('p', 'Before'), ('p', 'Caption'), ('tbl', 'BoldItalic'), ('p', 'After')]
    exported = html_output(convert_bytes(first.data, table_format='html'))
    assert exported.xpath('.//table//table//strong')[0].text == 'Bold'
    assert exported.xpath('.//table//table//em')[0].text == 'Italic'
    assert len(exported.xpath('.//table//table//br')) == 1


def test_links_and_images_survive_nested_table_roundtrip(tmp_path):
    (tmp_path / 'pixel.png').write_bytes(PNG)
    inner = wrap_html('<a href="https://example.org/source">Source</a> '
                      '<a href="#later">Jump</a><img src="pixel.png" alt="Pixel">')
    first = convert(wrap_html(inner) + '\n\n# Later', tmp_path)
    exported = convert_bytes(first.data, table_format='html', embed_images=True)
    tree = html_output(exported)
    assert tree.xpath('./table/tr/td/table//a/@href') == ['https://example.org/source', '#later']
    assert tree.xpath('./table/tr/td/table//img/@src')[0].startswith('data:image/png;base64,')
    second = convert(exported.markdown)
    assert len(word_xml(second).findall('.//w:hyperlink', NS)) == 2
    assert len(word_xml(second).findall('.//w:drawing', NS)) == 1
    assert not second.report.warnings


def test_nested_table_in_footnote_uses_note_relationships(docx_factory, relationships_xml):
    reference = '<w:p><w:r><w:footnoteReference w:id="1"/></w:r></w:p>'
    link = '<w:p><w:hyperlink r:id="shared"><w:r><w:t>Note link</w:t></w:r></w:hyperlink></w:p>'
    drawing = ('<w:p><w:r><w:drawing><wp:inline><pic:pic><pic:blipFill><a:blip r:embed="picture"/>'
               '</pic:blipFill></pic:pic></wp:inline></w:drawing></w:r></w:p>')
    notes = (f'<w:footnotes xmlns:w="{W_NS}" xmlns:r="{R_NS}" xmlns:wp="{WP_NS}" '
             f'xmlns:a="{A_NS}" xmlns:pic="{PIC_NS}"><w:footnote w:id="1">'
             f'{table(cell(paragraph("Before") + table(cell(link + drawing)) + paragraph("After")))}'
             '</w:footnote></w:footnotes>')
    data = docx_factory(reference,
                        relationships={'notes': ('footnotes', 'notes/footnotes.xml', False),
                                       'shared': ('hyperlink', 'https://example.org/body', True)},
                        parts={'word/notes/footnotes.xml': notes,
                               'word/notes/_rels/footnotes.xml.rels': relationships_xml({
                                   'shared': ('hyperlink', 'https://example.org/note', True),
                                   'picture': ('image', '../media/pixel.png', False)}),
                               'word/media/pixel.png': PNG})
    exported = convert_bytes(data, table_format='html', embed_images=True)
    note = html_output(exported).xpath('.//li[@id="fn1"]')[0]
    assert len(note.xpath('.//table')) == 2
    assert note.xpath('.//table//table//a/@href') == ['https://example.org/note']
    assert note.xpath('.//table//table//img/@src')[0].startswith('data:image/png;base64,')
    imported = convert(exported.markdown)
    assert len(word_xml(imported, 'word/footnotes.xml').findall('.//w:tbl', NS)) == 2


def test_note_reference_fallback_covers_the_whole_nested_tree(docx_factory):
    reference = '<w:p><w:r><w:t>Inner</w:t><w:footnoteReference w:id="1"/></w:r></w:p>'
    notes = f'<w:footnotes xmlns:w="{W_NS}"><w:footnote w:id="1">{paragraph("Note body")}</w:footnote></w:footnotes>'
    inner = table(cell(reference), cell(paragraph('Other row')))
    outer = table(cell(paragraph('Before') + inner + paragraph('After')), cell(paragraph('Other outer row')))
    exported = convert_bytes(docx_factory(outer + table(cell(paragraph('Following HTML table'))),
                                          relationships={'notes': ('footnotes', 'footnotes.xml', False)},
                                          parts={'word/footnotes.xml': notes}), table_format='html')
    codes = [warning.code for warning in exported.report.warnings]
    assert codes.count('html-table-fallback') == 1
    assert 'nested-table-flattened' in codes
    assert 'Note body' in html_output(exported).text_content()
    assert '<td>Following HTML table</td>' in exported.markdown
    assert '\x00' not in exported.markdown


def test_nested_tables_in_merge_continuations_are_retained_once(docx_factory):
    origin = cell(paragraph('Origin'), '<w:vMerge w:val="restart"/>')
    continued = cell(table(cell(paragraph('Nested continuation'))), '<w:vMerge/>')
    result = convert_bytes(docx_factory(table(origin, continued)), table_format='html')
    tree = html_output(result)
    assert len(tree.xpath('./table/tr/td[@rowspan="2"]/table')) == 1
    assert tree.text_content().count('Nested continuation') == 1
    assert [warning.code for warning in result.report.warnings] == ['merged-cell-content-moved']


def test_default_markdown_nested_fallback_retains_all_content(docx_factory):
    inner = table(cell(paragraph('Inner | A')) + cell(paragraph('Inner B')))
    outer = table(cell(paragraph('Before') + inner + paragraph('After')) + cell(paragraph('Side')))
    exported = convert_bytes(docx_factory(outer))
    tree = html_output(exported)
    assert len(tree.xpath('.//table')) == 1
    assert [cell.text_content() for cell in tree.xpath('.//th')] == ['BeforeInner | A · Inner BAfter', 'Side']
    assert [warning.code for warning in exported.report.warnings] == ['nested-table-flattened']


def test_invalid_nested_spans_warn_without_removing_the_inner_table():
    result = convert(wrap_html('<table><tr><td colspan="bad">Keep</td></tr></table>'))
    assert len(word_xml(result).findall('.//w:tbl', NS)) == 2
    assert text(word_xml(result)) == 'Keep'
    assert result.report.warnings[0].code == 'html-table-approximated'


def test_html_boundary_rule_handles_nested_tables_and_blank_lines():
    source = '<table>\n<tr><td>Before\n\n' + wrap_html('Inner') + '\n\nAfter</td></tr>\n</table>\n\n# Following'
    result = convert(source)
    assert len(word_xml(result).findall('.//w:tbl', NS)) == 2
    assert word_xml(result).find('.//w:pStyle[@w:val="Heading1"]', NS) is not None


def test_sibling_cells_after_nested_tables_do_not_inherit_inner_widths(tmp_path):
    (tmp_path / 'pixel.png').write_bytes(PNG)
    source = wrap_html(wrap_html('Inner', 'Narrow'), '<img src="pixel.png" alt="Sibling">')
    result = convert(source, tmp_path)
    cells = word_xml(result).findall('./w:body/w:tbl/w:tr/w:tc', NS)
    assert cells[1].find('.//w:drawing', NS) is not None
    assert cells[1].find('w:tbl', NS) is None
    assert not result.report.warnings
