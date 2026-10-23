"""Merged-cell regressions using small OOXML tables and rendered output."""
from html import escape

import pytest
from lxml import etree, html
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

from doctomd import convert_bytes, convert_file
from doctomd.cli import main
from doctomd.tables import read_table
from doctomd.xmlns import W_NS


def paragraph(text):
    return f'<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>'


def cell(text='', *, span=None, vertical=None, horizontal=None, body=None, align=None):
    properties = ''
    if span is not None:
        properties += f'<w:gridSpan w:val="{span}"/>'
    for name, value in [('vMerge', vertical), ('hMerge', horizontal)]:
        if value is not None:
            attribute = f' w:val="{value}"' if value else ''
            properties += f'<w:{name}{attribute}/>'
    if body is None:
        body = paragraph(text)
    if align:
        body = body.replace('<w:p>', f'<w:p><w:pPr><w:jc w:val="{align}"/></w:pPr>', 1)
    return f'<w:tc><w:tcPr>{properties}</w:tcPr>{body}</w:tc>'


def row(*cells, before=None, after=None):
    properties = ''
    for name, value in [('gridBefore', before), ('gridAfter', after)]:
        if value is not None:
            properties += f'<w:{name} w:val="{value}"/>'
    return f'<w:tr><w:trPr>{properties}</w:trPr>{"".join(cells)}</w:tr>'


def table(*rows, columns=None):
    grid = '' if columns is None else '<w:tblGrid>' + '<w:gridCol/>' * columns + '</w:tblGrid>'
    return f'<w:tbl>{grid}{"".join(rows)}</w:tbl>'


def layout(xml):
    element = etree.fromstring(xml.replace('<w:tbl>', f'<w:tbl xmlns:w="{W_NS}">', 1))
    return read_table(element)


def rendered(markdown):
    renderer = MarkdownIt('commonmark').enable(['table', 'strikethrough']).use(footnote_plugin)
    return html.fragment_fromstring(renderer.render(markdown), create_parent='div')


def warning_codes(result):
    return [warning.code for warning in result.report.warnings]


@pytest.fixture
def convert_table(docx_factory):
    def convert(xml, table_format='markdown', **package_options):
        return convert_bytes(docx_factory(xml, **package_options), table_format=table_format)
    return convert


def test_combined_row_and_column_spans(convert_table):
    xml = table(
        row(cell('Region', span=2, vertical='restart'), cell('First')),
        row(cell(span=2, vertical=''), cell('Second')),
        row(cell(span=2, vertical='continue'), cell('Third')),
        columns=3,
    )
    result = convert_table(xml, 'html')
    rows = rendered(result.markdown).xpath('.//tr')
    merged = rows[0][0]
    assert merged.get('colspan') == '2'
    assert merged.get('rowspan') == '3'
    assert [len(row) for row in rows] == [2, 1, 1]
    assert [row[-1].text_content() for row in rows] == ['First', 'Second', 'Third']
    assert not warning_codes(result)
    assert result.report.c[('ok', 'merged table cells')] == 1


def test_markdown_flattens_spans_at_correct_columns_with_one_warning(convert_table):
    xml = table(row(cell('A', span=2, vertical='restart'), cell('B')),
                row(cell(span=2, vertical=''), cell('C')), columns=3)
    result = convert_table(xml)
    rows = rendered(result.markdown).xpath('.//tr')
    assert [[cell.text_content() for cell in row] for row in rows] == [['A', '', 'B'], ['', '', 'C']]
    assert warning_codes(result) == ['merged-table-flattened']
    assert result.report.warnings[0].part == 'word/document.xml'


def test_separate_vertical_merges_do_not_share_state(convert_table):
    xml = table(row(cell('A', vertical='restart'), cell('B', vertical='restart')),
                row(cell(vertical=''), cell(vertical='')),
                row(cell('C'), cell(vertical='')))
    result = convert_table(xml, 'html')
    rows = rendered(result.markdown).xpath('.//tr')
    assert [cell.get('rowspan') for cell in rows[0]] == ['2', '3']
    assert len(rows[1]) == 0
    assert rows[2][0].text == 'C'


@pytest.mark.parametrize('interruption', [row(cell('Separate')), row(before=1)])
def test_vertical_merges_end_at_an_interruption(interruption):
    parsed = layout(table(row(cell('A', vertical='restart')), interruption,
                          row(cell('Orphan', vertical='')), columns=1))
    assert parsed.rows[0][0].rowspan == 1
    assert len(parsed.rows[2]) == 1
    assert 'Unmatched vertical merge' in parsed.issues[0]


def test_restart_begins_a_new_vertical_group():
    parsed = layout(table(row(cell(vertical='restart')), row(cell(vertical='')),
                          row(cell(vertical='restart')), row(cell(vertical=''))))
    assert [parsed.rows[index][0].rowspan for index in (0, 2)] == [2, 2]
    assert not parsed.issues


@pytest.mark.parametrize('continuation', [row(cell('Orphan', span=2, vertical='')),
                                         row(cell('Orphan', vertical=''), before=1)])
def test_misaligned_vertical_continuations_keep_their_text(convert_table, continuation):
    result = convert_table(table(row(cell('Origin', vertical='restart'), cell('Side')), continuation), 'html')
    document = rendered(result.markdown)
    assert 'Orphan' in document.text_content()
    assert not document.xpath('.//td[@rowspan]')
    assert 'invalid-table-structure' in warning_codes(result)


def test_legacy_horizontal_merges_preserve_all_content(convert_table):
    xml = table(row(cell('Start', horizontal='restart'), cell('Middle', horizontal=''),
                    cell('End', horizontal='continue'), cell('Separate')), columns=4)
    result = convert_table(xml, 'html')
    cells = rendered(result.markdown).xpath('.//td')
    assert len(cells) == 2
    assert cells[0].get('colspan') == '3'
    assert cells[0].text_content() == 'StartMiddleEnd'
    assert len(cells[0].xpath('./br')) == 2
    assert warning_codes(result) == ['merged-cell-content-moved']


def test_legacy_horizontal_and_vertical_merges_combine(convert_table):
    xml = table(row(cell('Origin', horizontal='restart', vertical='restart'),
                    cell(horizontal='', vertical='restart')),
                row(cell(horizontal='restart', vertical=''), cell(horizontal='', vertical='')))
    result = convert_table(xml, 'html')
    cells = rendered(result.markdown).xpath('.//td')
    assert len(cells) == 1
    assert cells[0].get('rowspan') == cells[0].get('colspan') == '2'


@pytest.mark.parametrize('table_format', ['markdown', 'html'])
def test_vertical_continuation_content_is_retained_once(convert_table, table_format):
    xml = table(row(cell('Origin', vertical='restart'), cell('Right')),
                row(cell('Extra', vertical=''), cell('Bottom')))
    result = convert_table(xml, table_format)
    assert result.markdown.count('Extra') == 1
    first = rendered(result.markdown).xpath('.//tr')[0][0]
    assert first.text_content() == 'OriginExtra'
    assert 'merged-cell-content-moved' in warning_codes(result)


def test_grid_offsets_and_short_rows_preserve_column_positions(convert_table):
    xml = table(row(cell('A'), cell('B'), cell('C'), cell('D')),
                row(cell('Middle', span=2), before=1, after=1), row(cell('Last'), before=3), columns=4)
    result = convert_table(xml)
    rows = rendered(result.markdown).xpath('.//tr')
    assert [cell.text_content() for cell in rows[1]] == ['', 'Middle', '', '']
    assert [cell.text_content() for cell in rows[2]] == ['', '', '', 'Last']
    html_rows = rendered(convert_table(xml, 'html').markdown).xpath('.//tr')
    assert len(html_rows[1]) == 3
    assert html_rows[1][1].get('colspan') == '2'


def test_span_can_extend_the_declared_grid():
    parsed = layout(table(row(cell(span=3), cell()), columns=2))
    assert parsed.columns == 4
    assert parsed.rows[0][1].column == 3
    assert not parsed.issues


def test_grid_can_be_inferred_without_tblgrid():
    parsed = layout(table(row(cell(span=2), before=1, after=2)))
    assert parsed.columns == 5
    assert parsed.rows[0][0].column == 1


@pytest.mark.parametrize('span', ['invalid', 0, -2])
def test_invalid_spans_default_to_one_without_losing_cells(convert_table, span):
    result = convert_table(table(row(cell('A', span=span), cell('B'))), 'html')
    assert [cell.text for cell in rendered(result.markdown).xpath('.//td')] == ['A', 'B']
    assert warning_codes(result) == ['invalid-table-structure']


def test_invalid_offsets_do_not_extend_a_declared_grid():
    parsed = layout(table(row(cell(), before=9, after=9), columns=2))
    assert parsed.columns == 2
    assert parsed.rows[0][0].column == 0
    assert len(parsed.issues) == 2


@pytest.mark.parametrize('properties', [{'horizontal': ''}, {'vertical': ''},
                                       {'horizontal': 'invalid'}, {'vertical': 'invalid'}])
def test_unmatched_and_invalid_merges_remain_visible(convert_table, properties):
    result = convert_table(table(row(cell('Keep', **properties), cell('Other'))), 'html')
    assert [cell.text for cell in rendered(result.markdown).xpath('.//td')] == ['Keep', 'Other']
    assert warning_codes(result) == ['invalid-table-structure']


def test_simple_markdown_table_keeps_formatting_and_alignment(convert_table):
    xml = table(row(cell('Name'), cell('Value')),
                row(cell('A | B', align='center'), cell('123', align='right')))
    result = convert_table(xml)
    assert result.markdown == '| Name   | Value |\n| :----: | ----: |\n| A \\| B | 123   |\n'
    assert not warning_codes(result)


def test_html_cells_render_inline_formatting_and_escape_literal_markup(convert_table):
    body = ('<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Bold</w:t></w:r>'
            '<w:r><w:t xml:space="preserve"> &lt;script&gt;&amp; | </w:t></w:r>'
            '<w:r><w:rPr><w:strike/></w:rPr><w:t>Deleted</w:t></w:r></w:p>')
    result = convert_table(table(row(cell(body=body, span=2, align='center'))), 'html')
    document = rendered(result.markdown)
    assert document.xpath('.//strong')[0].text == 'Bold'
    assert document.xpath('.//s')[0].text == 'Deleted'
    assert not document.xpath('.//script')
    assert '<script>& |' in document.text_content()
    assert document.xpath('.//td')[0].get('align') == 'center'


def test_html_links_resolve_bookmarks_in_later_headings(convert_table):
    link = '<w:p><w:hyperlink w:anchor="target"><w:r><w:t>Jump</w:t></w:r></w:hyperlink></w:p>'
    heading = ('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
               '<w:bookmarkStart w:id="1" w:name="target"/><w:r><w:t>Later title</w:t></w:r></w:p>')
    result = convert_table(table(row(cell(body=link, span=2))) + heading, 'html')
    assert rendered(result.markdown).xpath('.//a')[0].get('href') == '#later-title'
    assert '\x00' not in result.markdown


def test_html_cells_preserve_external_links_and_extracted_images(convert_table):
    body = ('<w:p><w:hyperlink r:id="link"><w:r><w:t>Source</w:t></w:r></w:hyperlink>'
            '<w:r><w:drawing><wp:inline><pic:pic><pic:blipFill>'
            '<a:blip r:embed="image"/></pic:blipFill></pic:pic></wp:inline></w:drawing></w:r></w:p>')
    result = convert_table(table(row(cell(body=body, span=2))), 'html',
                           relationships={'link': ('hyperlink', 'https://example.org/?a=1&b=2', True),
                                          'image': ('image', 'media/picture.png', False)},
                           parts={'word/media/picture.png': b'fixture image bytes'})
    document = rendered(result.markdown)
    assert document.xpath('.//td/a')[0].get('href') == 'https://example.org/?a=1&b=2'
    assert document.xpath('.//td/img')[0].get('src') == 'media/picture.png'
    assert result.images == {'picture.png': b'fixture image bytes'}
    assert not warning_codes(result)


def test_html_cells_preserve_embedded_images(docx_factory):
    drawing = ('<w:p><w:r><w:drawing><wp:inline><pic:pic><pic:blipFill>'
               '<a:blip r:embed="image"/></pic:blipFill></pic:pic></wp:inline></w:drawing></w:r></w:p>')
    data = docx_factory(table(row(cell(body=drawing, span=2))),
                        relationships={'image': ('image', 'media/picture.png', False)},
                        parts={'word/media/picture.png': b'fixture image bytes'})
    result = convert_bytes(data, embed_images=True, table_format='html')
    assert rendered(result.markdown).xpath('.//td/img')[0].get('src').startswith('data:image/png;base64,')
    assert not result.images


def test_numbered_content_is_converted_in_source_order_before_merging(convert_table):
    def numbered(text):
        properties = '<w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        return paragraph(text).replace('<w:p>', '<w:p>' + properties, 1)

    numbering = (f'<w:numbering xmlns:w="{W_NS}"><w:abstractNum w:abstractNumId="0">'
                 '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/>'
                 '<w:lvlText w:val="%1."/></w:lvl></w:abstractNum>'
                 '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
    xml = table(row(cell(body=numbered('Origin'), vertical='restart'), cell(body=numbered('Side'))),
                row(cell(body=numbered('Continued'), vertical=''), cell(body=numbered('Last'))))
    result = convert_table(xml, 'html', relationships={'numbering': ('numbering', 'numbering.xml', False)},
                           parts={'word/numbering.xml': numbering})
    cells = rendered(result.markdown).xpath('.//td')
    assert cells[0].text_content() == '• 1. Origin• 3. Continued'
    assert cells[1].text_content() == '• 2. Side'
    assert cells[2].text_content() == '• 4. Last'


def test_empty_spanned_cells_are_preserved_in_html(convert_table):
    result = convert_table(table(row(cell(span=2))), 'html')
    assert rendered(result.markdown).xpath('.//td')[0].get('colspan') == '2'


def test_single_cell_boxes_unwrap_only_in_default_mode(convert_table):
    xml = table(row(cell('Box')))
    assert convert_table(xml).markdown == 'Box\n'
    assert rendered(convert_table(xml, 'html').markdown).xpath('.//td')[0].text == 'Box'


@pytest.mark.parametrize('table_format', ['markdown', 'html'])
def test_nested_table_flattening_is_explicit(convert_table, table_format):
    nested = table(row(cell('Nested | left'), cell('Nested right')))
    result = convert_table(table(row(cell(body=nested), cell('Outer'))), table_format)
    document = rendered(result.markdown)
    assert len(document.xpath('.//table')) == 1
    assert 'Nested | left' in document.text_content()
    assert 'Nested right' in document.text_content()
    assert warning_codes(result) == ['nested-table-flattened']


def test_html_tables_with_footnotes_fall_back_to_markdown(convert_table):
    reference = '<w:p><w:r><w:t>See note</w:t><w:footnoteReference w:id="1"/></w:r></w:p>'
    notes = f'<w:footnotes xmlns:w="{W_NS}"><w:footnote w:id="1">{paragraph("Note body")}</w:footnote></w:footnotes>'
    result = convert_table(table(row(cell(body=reference, span=2))), 'html',
                           relationships={'notes': ('footnotes', 'footnotes.xml', False)},
                           parts={'word/footnotes.xml': notes})
    document = rendered(result.markdown)
    assert 'Note body' in document.text_content()
    assert document.xpath('.//table//a[@href="#fn1"]')
    assert warning_codes(result) == ['html-table-fallback', 'merged-table-flattened']


def test_html_table_inside_footnote_stays_in_the_note(convert_table):
    reference = '<w:p><w:r><w:t>Reference</w:t><w:footnoteReference w:id="1"/></w:r></w:p>'
    notes = (f'<w:footnotes xmlns:w="{W_NS}"><w:footnote w:id="1">'
             f'{table(row(cell("Note table", span=2)))}</w:footnote></w:footnotes>')
    result = convert_table(reference, 'html',
                           relationships={'notes': ('footnotes', 'footnotes.xml', False)},
                           parts={'word/footnotes.xml': notes})
    document = rendered(result.markdown)
    assert document.xpath('.//li[@id="fn1"]//td[@colspan="2"]')[0].text == 'Note table'
    assert '\x00' not in result.markdown


def test_cli_and_file_api_accept_html_option(docx_factory, tmp_path, capsys):
    source = tmp_path / 'merged.docx'
    source.write_bytes(docx_factory(table(row(cell('Merged', span=2)))))
    assert '<td colspan="2">Merged</td>' in convert_file(source, table_format='html').markdown
    assert main([str(source), '--table-format', 'html', '-o', '-', '--quiet']) == 0
    assert '<td colspan="2">Merged</td>' in capsys.readouterr().out


def test_flat_opc_file_forwards_html_option(tmp_path):
    source = tmp_path / 'merged.xml'
    source.write_text(
        '<pkg:package xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage">'
        '<pkg:part pkg:name="/word/document.xml" '
        'pkg:contentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml">'
        f'<pkg:xmlData><w:document xmlns:w="{W_NS}"><w:body>'
        f'{table(row(cell("Merged", span=2)))}'
        '</w:body></w:document></pkg:xmlData></pkg:part></pkg:package>', encoding='utf-8')
    result = convert_file(source, table_format='html')
    assert rendered(result.markdown).xpath('.//td')[0].get('colspan') == '2'


def test_invalid_table_format_is_rejected(docx_factory):
    with pytest.raises(ValueError, match='table_format'):
        convert_bytes(docx_factory(paragraph('Text')), table_format='unknown')
