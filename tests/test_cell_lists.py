"""Cell lists keep native Word numbering and HTML structure across round trips."""
import base64
import io
import zipfile

import pytest
from lxml import etree, html
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin

from doctomd import convert_bytes
from doctomd.numbering import Numbering
from doctomd.xmlns import W_NS, WP_NS
from mdtodoc import convert


NS = {'w': W_NS, 'wp': WP_NS}
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6GQAAAAASUVORK5CYII=')


def table(content):
    return f'<table><tr><td>{content}</td></tr></table>'


def word_xml(result, part='word/document.xml'):
    with zipfile.ZipFile(io.BytesIO(result.data)) as archive:
        return etree.fromstring(archive.read(part))


def word_text(element):
    return ''.join(element.xpath('.//w:t/text()', namespaces=NS))


def numbered_paragraphs(result):
    numbering = Numbering(word_xml(result, 'word/numbering.xml'))
    paragraphs = []
    for paragraph in word_xml(result).findall('.//w:p', NS):
        properties = paragraph.find('w:pPr/w:numPr', NS)
        if properties is not None:
            num_id = int(properties.find('w:numId', NS).get(f'{{{W_NS}}}val'))
            level = int(properties.find('w:ilvl', NS).get(f'{{{W_NS}}}val'))
            number = numbering.step(num_id, level)
            paragraphs.append((word_text(paragraph), level, number.number_format, number.value))
    return paragraphs


def export(result):
    converted = convert_bytes(result.data, table_format='html', embed_images=True)
    renderer = MarkdownIt('commonmark').use(footnote_plugin)
    tree = html.fragment_fromstring(renderer.render(converted.markdown), create_parent='div')
    assert '\x00' not in converted.markdown
    return converted, tree


def roundtrip(source):
    first = convert(source)
    converted, tree = export(first)
    second = convert(converted.markdown)
    assert numbered_paragraphs(second) == numbered_paragraphs(first)
    assert not first.report.warnings
    assert not converted.report.warnings
    assert not second.report.warnings
    return first, tree, second


@pytest.mark.parametrize('start', [0, 1, 7, 123])
def test_ordered_starts_and_item_values_are_native_numbering(start):
    first, tree, _ = roundtrip(table(
        f'<ol start="{start}"><li>First</li><li>Next</li><li value="9">Restart</li><li>Last</li></ol>'))
    assert numbered_paragraphs(first) == [
        ('First', 0, 'decimal', start), ('Next', 0, 'decimal', start + 1),
        ('Restart', 0, 'decimal', 9), ('Last', 0, 'decimal', 10)]
    starts = [start] if start + 2 == 9 else [start, 9]
    assert [int(element.get('start', '1')) for element in tree.xpath('./table/tr/td/ol')] == starts
    assert word_xml(first, 'word/numbering.xml').xpath(
        './/w:num/w:lvlOverride/w:startOverride/@w:val', namespaces=NS) == [str(value) for value in starts]


def test_mixed_nested_lists_keep_decimal_values_at_each_depth():
    source = table('<ol start="3"><li>Outer<ul><li>Bullet<ol start="4">'
                   '<li>Inner A</li><li>Inner B</li></ol></li></ul></li><li>Outer next</li></ol>')
    first, tree, _ = roundtrip(source)
    assert numbered_paragraphs(first) == [
        ('Outer', 0, 'decimal', 3), ('Bullet', 1, 'bullet', 1),
        ('Inner A', 2, 'decimal', 4), ('Inner B', 2, 'decimal', 5), ('Outer next', 0, 'decimal', 4)]
    assert tree.xpath('./table/tr/td/ol[@start="3"]/li/ul/li/ol[@start="4"]/li/text()') == ['Inner A', 'Inner B']


@pytest.mark.parametrize('tag', ['ol', 'ul'])
def test_adjacent_lists_and_separate_cells_have_independent_instances(tag):
    source = (f'<table><tr><td><{tag}><li>A</li></{tag}><{tag}><li>B</li></{tag}></td>'
              f'<td><{tag}><li>C</li></{tag}></td></tr></table>')
    first, tree, _ = roundtrip(source)
    identifiers = word_xml(first).xpath('.//w:numPr/w:numId/@w:val', namespaces=NS)
    assert len(set(identifiers)) == 3
    assert len(tree.xpath(f'./table/tr/td[1]/{tag}')) == 2
    assert len(tree.xpath(f'./table/tr/td[2]/{tag}')) == 1


def test_paragraphs_inside_and_between_lists_keep_their_ownership():
    source = table('<p>Before</p><ol><li><p>First</p><p>More</p><ul><li>Child</li></ul>'
                   '<p>After child</p></li><li>Second</li></ol><p>Between</p>'
                   '<ol start="8"><li>Later</li></ol><p>After</p>')
    _, tree, _ = roundtrip(source)
    cell = tree.xpath('./table/tr/td')[0]
    assert [child.tag for child in cell] == ['p', 'ol', 'p', 'ol', 'p']
    assert cell.xpath('./p/text()') == ['Before', 'Between', 'After']
    assert cell.xpath('./ol[1]/li[1]/p/text()') == ['First', 'More', 'After child']
    assert cell.xpath('./ol[1]/li[1]/ul/li/text()') == ['Child']


def test_nested_tables_and_their_lists_stay_inside_the_correct_item():
    inner = table('<ol start="6"><li>Inner</li></ol>')
    source = table('<ul><li>Before' + inner + '<p>Between</p>' + table('Other table') +
                   '<p>After</p></li><li>Next</li></ul>' + table('Sibling table'))
    first, tree, _ = roundtrip(source)
    item = tree.xpath('./table/tr/td/ul/li[1]')[0]
    assert [child.tag for child in item] == ['p', 'table', 'p', 'table', 'p']
    assert item.xpath('./table[1]/tr/td/ol[@start="6"]/li/text()') == ['Inner']
    assert tree.xpath('./table/tr/td/table/tr/td/text()') == ['Sibling table']
    for nested in word_xml(first).xpath('.//w:tc/w:tbl[w:tblPr/w:tblInd]', namespaces=NS):
        width = int(nested.getparent().find('w:tcPr/w:tcW', NS).get(f'{{{W_NS}}}w'))
        indent = int(nested.find('w:tblPr/w:tblInd', NS).get(f'{{{W_NS}}}w'))
        grid = sum(int(column.get(f'{{{W_NS}}}w')) for column in nested.findall('w:tblGrid/w:gridCol', NS))
        assert grid + indent <= width - 216


@pytest.mark.parametrize('content, selector', [
    ('', './ol/li[1]'),
    ('<ul><li>Nested</li></ul>', './ol/li[1]/ul/li'),
    (table('Nested'), './ol/li[1]/table/tr/td'),
    ('<pre>one\n  two</pre>', './ol/li[1]/pre/code'),
])
def test_empty_items_and_items_starting_with_blocks(content, selector):
    first, tree, _ = roundtrip(table(f'<ol><li>{content}</li><li>Next</li></ol>'))
    cell = tree.xpath('./table/tr/td')[0]
    assert len(cell.xpath(selector)) == 1
    assert [item[3] for item in numbered_paragraphs(first) if item[1] == 0] == [1, 2]


def test_preformatted_continuation_preserves_newlines_and_indentation():
    _, tree, second = roundtrip(table(
        '<ol><li>First<pre>one\n  two\nthree</pre><p>After</p></li><li>Next</li></ol>'))
    assert tree.xpath('./table/tr/td/ol/li[1]/pre/code/text()') == ['one\n  two\nthree\n']
    assert '  two' in word_text(word_xml(second))


def test_rich_items_in_merged_and_nested_cells_preserve_links_and_images(tmp_path):
    (tmp_path / 'pixel.png').write_bytes(PNG)
    rich = '<ol><li><strong>Bold</strong> <em>Italic</em> <a href="#later">Jump</a><img src="pixel.png" alt="Pixel"></li></ol>'
    first = convert('<table><tr><td rowspan="2" colspan="2">' + table(rich) +
                    '</td><td>A</td></tr><tr><td>B</td></tr></table>\n\n# Later', tmp_path)
    converted, tree = export(first)
    item = tree.xpath('./table/tr/td[@rowspan="2"][@colspan="2"]/table/tr/td/ol/li')[0]
    assert item.find('strong').text == 'Bold'
    assert item.find('em').text == 'Italic'
    assert item.find('a').get('href') == '#later'
    assert item.find('img').get('src').startswith('data:image/png;base64,')
    second = convert(converted.markdown)
    assert len(word_xml(second).findall('.//w:hyperlink', NS)) == 1
    assert len(word_xml(second).findall('.//w:drawing', NS)) == 1
    extent = word_xml(first).find('.//wp:extent', NS)
    parent_cell = next(extent.iterancestors(f'{{{W_NS}}}tc'))
    width = int(parent_cell.find('w:tcPr/w:tcW', NS).get(f'{{{W_NS}}}w'))
    assert int(extent.get('cx')) <= max(width - 216 - 720, 1) * 635


@pytest.mark.parametrize('attributes, item_attributes, values, warning', [
    ('start="bad"', 'value="bad"', [1, 2], 'Invalid list'),
    ('reversed', '', [2, 1], 'Descending'),
    ('reversed start="5"', 'value="8"', [5, 8], 'Descending'),
    ('type="A"', '', [1, 2], 'Non-decimal'),
])
def test_approximations_keep_values_and_report_them(attributes, item_attributes, values, warning):
    first = convert(table(f'<ol {attributes}><li>A</li><li {item_attributes}>B</li></ol>'))
    assert [item[3] for item in numbered_paragraphs(first)] == values
    assert any(warning in item.message for item in first.report.warnings)
    converted, _ = export(first)
    assert numbered_paragraphs(convert(converted.markdown)) == numbered_paragraphs(first)


def test_negative_values_remain_visible_as_text_labels():
    first = convert(table('<ol start="-1"><li>A</li><li>B</li><li>C</li></ol>'))
    assert [item[:3] for item in numbered_paragraphs(first)] == [
        ('-1. A', 0, 'bullet'), ('0. B', 0, 'bullet'), ('1. C', 0, 'bullet')]
    assert any('Negative list values' in item.message for item in first.report.warnings)
    converted, tree = export(first)
    assert tree.xpath('./table/tr/td/ul/li/text()') == ['-1. A', '0. B', '1. C']
    assert numbered_paragraphs(convert(converted.markdown)) == numbered_paragraphs(first)


def test_malformed_list_content_is_retained_with_a_warning():
    first = convert(table('<ul>Before<li>Item</li>Between<div>Loose block</div>After</ul>'))
    text = word_text(word_xml(first))
    assert all(value in text for value in ('Before', 'Item', 'Between', 'Loose block', 'After'))
    assert any('outside list items' in item.message for item in first.report.warnings)
    converted, tree = export(first)
    assert 'Loose block' in tree.text_content()
    # The fallback bullet label may become an automatic marker on export.
    assert word_text(word_xml(convert(converted.markdown))) == 'BeforeItemBetweenLoose blockAfter'


@pytest.mark.parametrize('depth', [9, 11])
def test_word_depth_limit_keeps_all_item_text(depth):
    source = ''
    for index in reversed(range(depth)):
        source = f'<ol><li>Level {index}{source}</li></ol>'
    first = convert(table(source))
    numbers = numbered_paragraphs(first)
    assert [item[1] for item in numbers] == [min(index, 8) for index in range(depth)]
    assert bool(first.report.warnings) == (depth > 9)
    converted, tree = export(first)
    assert len(tree.xpath('.//li')) == depth
    assert numbered_paragraphs(convert(converted.markdown)) == numbers


def test_existing_word_indentation_controls_continuation_membership(docx_factory):
    numbering = (f'<w:numbering xmlns:w="{W_NS}"><w:abstractNum w:abstractNumId="0">'
                 '<w:lvl w:ilvl="0"><w:start w:val="4"/><w:numFmt w:val="decimal"/>'
                 '<w:lvlText w:val="%1."/><w:pPr><w:ind w:start="960"/></w:pPr></w:lvl>'
                 '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
    marker = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'

    def paragraph(text, properties=''):
        return f'<w:p><w:pPr>{properties}</w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'

    content = (paragraph('First', marker) + paragraph('Continuation', '<w:ind w:left="960"/>') +
               paragraph('Between') + paragraph('Resumed', marker) +
               paragraph('Different indent', '<w:ind w:left="300"/>'))
    data = docx_factory('<w:tbl><w:tr><w:tc>' + content + '</w:tc></w:tr></w:tbl>',
                        relationships={'numbering': ('numbering', 'numbering.xml', False)},
                        parts={'word/numbering.xml': numbering})
    result = convert_bytes(data, table_format='html')
    tree = html.fragment_fromstring(result.markdown)
    assert tree.xpath('./tr/td/ol[1]/li/p/text()') == ['First', 'Continuation']
    assert tree.xpath('./tr/td/p/text()') == ['Between', 'Different indent']
    assert tree.xpath('./tr/td/ol[2]/@start') == ['5']


def test_default_pipe_table_keeps_readable_list_fallback():
    first = convert('<table><tr><td><ol start="3"><li>A</li><li>B</li></ol></td><td>Side</td></tr></table>')
    converted = convert_bytes(first.data)
    assert '• 3. A<br>• 4. B' in converted.markdown
    assert '<ol' not in converted.markdown


def test_note_reference_fallback_still_resolves_notes(docx_factory):
    marker = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
    first = convert(table('<ol start="3"><li>Item</li></ol>'))
    numbering = etree.tostring(word_xml(first, 'word/numbering.xml'))
    # The shared bullet instance is present in every generated numbering part.
    paragraph = f'<w:p><w:pPr>{marker}</w:pPr><w:r><w:t>Item</w:t><w:footnoteReference w:id="1"/></w:r></w:p>'
    notes = f'<w:footnotes xmlns:w="{W_NS}"><w:footnote w:id="1"><w:p><w:r><w:t>Note</w:t></w:r></w:p></w:footnote></w:footnotes>'
    data = docx_factory('<w:tbl><w:tr><w:tc>' + paragraph + '</w:tc><w:tc><w:p/></w:tc></w:tr></w:tbl>',
                        relationships={'numbering': ('numbering', 'numbering.xml', False),
                                       'notes': ('footnotes', 'footnotes.xml', False)},
                        parts={'word/numbering.xml': numbering, 'word/footnotes.xml': notes})
    converted = convert_bytes(data, table_format='html')
    tree = html.fragment_fromstring(MarkdownIt('commonmark').enable('table').use(footnote_plugin).render(converted.markdown), create_parent='div')
    assert 'Note' in tree.xpath('.//li[@id="fn1"]')[0].text_content()
    assert [item.code for item in converted.report.warnings] == ['html-table-fallback']
