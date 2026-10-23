"""List behavior from inspectable OOXML, including rendered Markdown structure."""
from html import escape

import pytest
from lxml import etree, html
from markdown_it import MarkdownIt

from doctomd import convert_bytes
from doctomd.numbering import Numbering, format_number
from doctomd.styles import Styles
from doctomd.xmlns import W_NS


def level(index=0, *, number_format='decimal', text=None, start=1, restart=None, extra=''):
    """Build one numbering level; None omits optional start/restart elements."""
    if text is None:
        text = f'%{index + 1}.'
    properties = f'<w:numFmt w:val="{number_format}"/><w:lvlText w:val="{escape(text, quote=True)}"/>'
    if start is not None:
        properties += f'<w:start w:val="{start}"/>'
    if restart is not None:
        properties += f'<w:lvlRestart w:val="{restart}"/>'
    return f'<w:lvl w:ilvl="{index}">{properties}{extra}</w:lvl>'


def abstract(levels, abstract_id=0, *, extra=''):
    return f'<w:abstractNum w:abstractNumId="{abstract_id}">{levels}{extra}</w:abstractNum>'


def instance(num_id, abstract_id=0, *, overrides=''):
    return (f'<w:num w:numId="{num_id}"><w:abstractNumId w:val="{abstract_id}"/>'
            f'{overrides}</w:num>')


def override(index, *, start=None, replacement=''):
    start_xml = f'<w:startOverride w:val="{start}"/>' if start is not None else ''
    return f'<w:lvlOverride w:ilvl="{index}">{start_xml}{replacement}</w:lvlOverride>'


def numbering_xml(definitions):
    return f'<w:numbering xmlns:w="{W_NS}">{definitions}</w:numbering>'


def counter(definitions, styles=None):
    return Numbering(etree.fromstring(numbering_xml(definitions)), styles)


def paragraph(text, num_id=None, index=0, *, heading=False, extra=''):
    properties = '<w:pStyle w:val="Heading1"/>' if heading else ''
    if num_id is not None:
        level_xml = f'<w:ilvl w:val="{index}"/>' if index is not None else ''
        properties += f'<w:numPr>{level_xml}<w:numId w:val="{num_id}"/></w:numPr>'
    return f'<w:p><w:pPr>{properties}{extra}</w:pPr><w:r><w:t>{escape(text)}</w:t></w:r></w:p>'


@pytest.fixture
def convert_list(docx_factory):
    def convert(definitions, body, *, styles=None):
        parts = {'word/numbering.xml': numbering_xml(definitions)}
        relationships = {'numbering': ('numbering', 'numbering.xml', False)}
        if styles is not None:
            parts['word/styles.xml'] = styles
            relationships['styles'] = ('styles', 'styles.xml', False)
        return convert_bytes(docx_factory(body, parts=parts, relationships=relationships))
    return convert


def rendered(markdown):
    return html.fragment_fromstring(MarkdownIt('commonmark').render(markdown), create_parent='div')


def test_instances_have_independent_counters_and_resume():
    numbering = counter(abstract(level()) + instance(1) + instance(2))
    assert [numbering.step(num_id, 0).value for num_id in (1, 1, 2, 1, 2)] == [1, 2, 1, 3, 2]


def test_start_override_does_not_reset_another_instance():
    numbering = counter(abstract(level()) + instance(1) + instance(2, overrides=override(0, start=7)))
    assert [numbering.step(num_id, 0).value for num_id in (1, 2, 1, 2)] == [1, 7, 2, 8]


def test_default_restart_uses_previous_level():
    numbering = counter(abstract(level() + level(1)) + instance(1))
    assert [numbering.step(1, index).value for index in (0, 1, 1, 0, 1)] == [1, 1, 2, 2, 1]


def test_never_restart_keeps_child_counter():
    numbering = counter(abstract(level() + level(1, restart=0)) + instance(1))
    assert [numbering.step(1, index).value for index in (0, 1, 1, 0, 1)] == [1, 1, 2, 2, 3]


def test_explicit_restart_trigger_ignores_other_ancestors():
    numbering = counter(abstract(level() + level(1) + level(2, restart=1)) + instance(1))
    levels = (0, 1, 2, 2, 1, 2, 0, 2)
    assert [numbering.step(1, index).value for index in levels] == [1, 1, 1, 2, 2, 3, 2, 1]


def test_default_restart_waits_for_its_trigger_even_when_levels_are_skipped():
    numbering = counter(abstract(level() + level(1) + level(2)) + instance(1))
    assert [numbering.step(1, index).value for index in (0, 2, 0, 2, 1, 2)] == [1, 1, 2, 2, 1, 1]


@pytest.mark.parametrize('restart', [-1, 5, 'invalid'])
def test_invalid_restart_uses_the_default_rule(restart):
    numbering = counter(abstract(level() + level(1, restart=restart)) + instance(1))
    assert [numbering.step(1, index).value for index in (0, 1, 0, 1)] == [1, 1, 2, 1]


def test_start_override_is_reapplied_after_restart():
    numbering = counter(abstract(level() + level(1, start=2)) +
                        instance(1, overrides=override(1, start=7)))
    assert [numbering.step(1, index).value for index in (0, 1, 1, 0, 1)] == [1, 7, 8, 2, 7]


def test_level_override_replaces_format_label_and_restart():
    replacement = level(1, number_format='upperRoman', text='Part %2)', start=4, restart=0)
    numbering = counter(abstract(level() + level(1)) + instance(1) +
                        instance(2, overrides=override(1, replacement=replacement)))
    labels = [numbering.step(2, index).label for index in (0, 1, 0, 1)]
    assert labels == ['1.', 'Part IV)', '2.', 'Part V)']
    assert numbering.step(1, 1).label == '1.'


def test_start_override_takes_precedence_over_nested_level():
    numbering = counter(abstract(level()) + instance(1, overrides=override(
        0, start=8, replacement=level(number_format='upperRoman', start=3))))
    assert numbering.step(1, 0).label == 'VIII.'


def test_level_override_uses_schema_defaults_not_old_properties():
    replacement = '<w:lvl w:ilvl="0"><w:lvlText w:val="%1)"/></w:lvl>'
    numbering = counter(abstract(level(number_format='upperRoman', start=9)) +
                        instance(1, overrides=override(0, replacement=replacement)))
    assert numbering.step(1, 0).label == '0)'


def test_parent_label_uses_its_effective_start_override_without_advancing():
    numbering = counter(abstract(level() + level(1, text='%1.%2')) +
                        instance(1, overrides=override(0, start=5)))
    assert numbering.step(1, 1).label == '5.1'
    assert numbering.step(1, 0).label == '5.'
    assert numbering.step(1, 1).label == '5.1'


def test_compound_labels_use_each_referenced_levels_format():
    numbering = counter(abstract(level(number_format='upperLetter') +
                                 level(1, number_format='lowerRoman', text='%1.%2')) + instance(1))
    assert [numbering.step(1, index).label for index in (0, 1, 1, 0, 1)] == ['A.', 'A.i', 'A.ii', 'B.', 'B.i']


@pytest.mark.parametrize('legal, expected', [('<w:isLgl/>', '1.1'), ('<w:isLgl w:val="false"/>', 'A.i')])
def test_legal_numbering_uses_decimal_for_referenced_levels(legal, expected):
    numbering = counter(abstract(level(number_format='upperLetter') +
                                 level(1, number_format='lowerRoman', text='%1.%2', extra=legal)) + instance(1))
    numbering.step(1, 0)
    assert numbering.step(1, 1).label == expected


def test_deeper_references_are_ignored_and_literal_percent_is_preserved():
    numbering = counter(abstract(level(text='Rate 50% / %0 / %1 / %2') + level(1)) + instance(1))
    assert numbering.step(1, 0).label == 'Rate 50% / %0 / 1 /'


def test_omitted_start_defaults_to_zero():
    numbering = counter(abstract(level(start=None)) + instance(1))
    assert [numbering.step(1, 0).value for _ in range(2)] == [0, 1]


@pytest.mark.parametrize('number_format, value, expected', [
    ('decimalZero', 7, '07'), ('upperRoman', 14, 'XIV'), ('lowerRoman', 49, 'xlix'),
    ('upperLetter', 26, 'Z'), ('upperLetter', 27, 'AA'), ('lowerLetter', 28, 'bb'),
    ('upperLetter', 53, 'AAA'), ('upperRoman', 0, '0'),
])
def test_supported_number_formats(number_format, value, expected):
    assert format_number(number_format, value) == expected


@pytest.mark.parametrize('num_id, index', [(99, 0), (0, 0), (1, 2), (1, -1), (1, 9)])
def test_missing_instances_or_levels_are_not_substituted(num_id, index):
    numbering = counter(abstract(level()) + instance(1))
    assert numbering.step(num_id, index) is None


def test_style_level_lookup_is_scoped_to_instance():
    style = '<w:pStyle w:val="ListStyle"/>'
    numbering = counter(abstract(level(extra=style)) + abstract(level(2, extra=style), 1) +
                        instance(1) + instance(2, 1))
    assert numbering.style_level('ListStyle', 1) == 0
    assert numbering.style_level('ListStyle', 2) == 2
    assert numbering.style_level(None, 2) == 0


def test_style_link_resolves_numbering_style_and_keeps_instance_counters():
    styles = Styles(etree.fromstring(f'<w:styles xmlns:w="{W_NS}">'
        '<w:style w:type="numbering" w:styleId="LinkedList"><w:pPr>'
        '<w:numPr><w:numId w:val="1"/></w:numPr></w:pPr></w:style></w:styles>'))
    numbering = counter(abstract(level()) + abstract('', 1, extra='<w:numStyleLink w:val="LinkedList"/>') +
                        instance(1, overrides=override(0, start=3)) + instance(2, 1), styles)
    assert [numbering.step(num_id, 0).value for num_id in (1, 1, 2, 1)] == [3, 4, 3, 5]


def test_cyclic_numbering_style_link_is_unresolved_without_recursing():
    styles = Styles(etree.fromstring(f'<w:styles xmlns:w="{W_NS}">'
        '<w:style w:type="numbering" w:styleId="Cycle"><w:pPr>'
        '<w:numPr><w:numId w:val="1"/></w:numPr></w:pPr></w:style></w:styles>'))
    numbering = counter(abstract('', extra='<w:numStyleLink w:val="Cycle"/>') + instance(1), styles)
    assert numbering.step(1, 0) is None


def test_style_link_can_use_an_abstract_style_definition():
    definitions = abstract(level(start=3), extra='<w:styleLink w:val="ListStyle"/>')
    definitions += abstract('', 1, extra='<w:numStyleLink w:val="ListStyle"/>') + instance(1, 1)
    assert counter(definitions).step(1, 0).value == 3


def test_adjacent_independent_lists_render_separately(convert_list):
    result = convert_list(abstract(level()) + instance(1) + instance(2),
                          paragraph('First', 1) + paragraph('Second', 1) + paragraph('New list', 2))
    lists = rendered(result.markdown).xpath('./ol')
    assert [len(element.findall('li')) for element in lists] == [2, 1]
    assert all(element.get('start', '1') == '1' for element in lists)
    assert result.report.warnings == []


def test_list_resumes_after_prose(convert_list):
    result = convert_list(abstract(level()) + instance(1),
                          paragraph('First', 1) + paragraph('Between') + paragraph('Second', 1))
    assert result.markdown == '1. First\n\nBetween\n\n2. Second\n'


def test_interleaved_lists_keep_rendered_starts(convert_list):
    result = convert_list(abstract(level()) + instance(1) + instance(2),
                          paragraph('A', 1) + paragraph('B', 2) + paragraph('C', 1))
    assert [element.get('start', '1') for element in rendered(result.markdown).xpath('./ol')] == ['1', '1', '2']


def test_multilevel_lists_use_logical_depth_even_with_identical_indentation(convert_list):
    indent = '<w:pPr><w:ind w:left="360"/></w:pPr>'
    definitions = abstract(level(extra=indent) + level(1, extra=indent)) + instance(1)
    result = convert_list(definitions, paragraph('Parent', 1) + paragraph('Child', 1, 1) + paragraph('Next', 1))
    root = rendered(result.markdown)
    assert len(root.xpath('./ol/li')) == 2
    assert root.xpath('./ol/li/ol/li')[0].text == 'Child'


def test_nested_never_restart_list_renders_continued_value(convert_list):
    definitions = abstract(level() + level(1, restart=0)) + instance(1)
    result = convert_list(definitions, paragraph('Parent', 1) + paragraph('Child', 1, 1) +
                          paragraph('Next parent', 1) + paragraph('Continued child', 1, 1))
    children = rendered(result.markdown).xpath('./ol/li/ol')
    assert [element.get('start', '1') for element in children] == ['1', '2']


def test_nested_lists_with_different_instance_ids_remain_inside_parent(convert_list):
    definitions = abstract(level() + level(1)) + instance(1) + instance(2) + instance(3)
    result = convert_list(definitions, paragraph('Parent', 1) + paragraph('First child list', 2, 1) +
                          paragraph('Second child list', 3, 1) + paragraph('Next parent', 1))
    root = rendered(result.markdown)
    assert len(root.xpath('./ol/li')) == 2
    assert len(root.xpath('./ol/li[1]/ol')) == 2


@pytest.mark.parametrize('number_format, label, expected', [
    ('upperRoman', '%1.', 'IV.'), ('lowerLetter', '%1)', 'd)'),
    ('decimal', 'Article %1:', 'Article 4:'), ('decimalZero', '%1.', '04.'),
])
def test_non_markdown_labels_are_preserved_as_text(convert_list, number_format, label, expected):
    result = convert_list(abstract(level(number_format=number_format, text=label, start=4)) + instance(1),
                          paragraph('Text', 1) + paragraph('More', 1))
    items = rendered(result.markdown).xpath('./ul/li')
    assert items[0].text == expected + ' Text'
    assert [warning.code for warning in result.report.warnings] == ['numbering-label-as-text']
    assert result.report.percent < 100


def test_compound_heading_numbers_are_preserved(convert_list):
    definitions = abstract(level(number_format='upperRoman') + level(1, text='%1.%2')) + instance(1)
    result = convert_list(definitions, paragraph('Chapter', 1, heading=True) +
                          paragraph('Section', 1, 1, heading=True))
    assert result.markdown == '# I. Chapter\n\n# I.1 Section\n'
    assert result.report.warnings == []


def test_decimal_parenthesis_markers_remain_ordered_lists(convert_list):
    result = convert_list(abstract(level(text='%1)', start=3)) + instance(1), paragraph('Text', 1))
    assert result.markdown == '3) Text\n'
    assert rendered(result.markdown).xpath('./ol')[0].get('start') == '3'


@pytest.mark.parametrize('definition', [level(number_format='none'), level(text='')])
def test_explicit_unmarked_levels_do_not_infer_typed_lists(convert_list, definition):
    result = convert_list(abstract(definition) + instance(1), paragraph('1. Literal', 1))
    assert result.markdown == '1\\. Literal\n'
    assert rendered(result.markdown).xpath('./ol') == []


def test_num_id_zero_disables_numbering_and_typed_list_detection(convert_list):
    result = convert_list(abstract(level()) + instance(1), paragraph('1. Literal', 0))
    assert result.markdown == '1\\. Literal\n'
    assert result.report.warnings == []


def test_missing_numbering_keeps_text_and_warns_once(convert_list):
    result = convert_list(abstract(level()) + instance(1), paragraph('First', 99) + paragraph('Second', 99))
    assert result.markdown == 'First\n\nSecond\n'
    assert [warning.code for warning in result.report.warnings] == ['missing-numbering']
    assert result.report.percent == 0


def test_unsupported_format_is_reported_even_for_heading(convert_list):
    result = convert_list(abstract(level(number_format='ordinal')) + instance(1), paragraph('Text', 1, heading=True))
    assert result.markdown == '# 1. Text\n'
    assert result.report.warnings[0].code == 'unsupported-numbering-format'
    assert result.report.percent < 100


def test_numbering_is_preserved_when_table_cells_are_flattened(convert_list):
    body = '<w:tbl><w:tr><w:tc>' + paragraph('One', 1) + paragraph('Two', 1) + '</w:tc>'
    body += '<w:tc>' + paragraph('Other cell') + '</w:tc></w:tr></w:tbl>'
    result = convert_list(abstract(level()) + instance(1), body)
    assert '1. One' in result.markdown
    assert '2. Two' in result.markdown


def test_style_inherited_numbering_uses_effective_level(convert_list):
    styles = f'<w:styles xmlns:w="{W_NS}"><w:style w:type="paragraph" w:styleId="ListStyle">'
    styles += '<w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr></w:style></w:styles>'
    definitions = abstract(level() + level(1, start=4, extra='<w:pStyle w:val="ListStyle"/>')) + instance(1)
    body = paragraph('Parent', 1) + paragraph('Styled child', extra='<w:pStyle w:val="ListStyle"/>')
    result = convert_list(definitions, body, styles=styles)
    assert rendered(result.markdown).xpath('./ol/li/ol')[0].get('start') == '4'


def test_bullets_and_numbered_children_keep_their_structure(convert_list):
    definitions = abstract(level(number_format='bullet') + level(1)) + instance(1)
    result = convert_list(definitions, paragraph('Parent', 1) + paragraph('Child', 1, 1) +
                          paragraph('Second child', 1, 1) + paragraph('Next parent', 1))
    root = rendered(result.markdown)
    assert len(root.xpath('./ul/li')) == 2
    assert len(root.xpath('./ul/li[1]/ol/li')) == 2
    assert result.report.warnings == []


def test_nested_numbered_list_can_follow_bullets_at_the_same_level(convert_list):
    definitions = abstract(level() + level(1)) + abstract(level(1, number_format='bullet'), 1)
    definitions += instance(1) + instance(2, 1) + instance(3, overrides=override(1, start=3))
    body = paragraph('Parent', 1) + paragraph('Bullet', 2, 1) + paragraph('Numbered', 3, 1)
    result = convert_list(definitions, body)
    root = rendered(result.markdown)
    assert root.xpath('./ol/li/ul/li')[0].text == 'Bullet'
    assert root.xpath('./ol/li/ol')[0].get('start') == '3'


def test_parent_marker_width_changes_keep_children_nested(convert_list):
    definitions = abstract(level(start=9) + level(1)) + instance(1)
    body = paragraph('Nine', 1) + paragraph('Child nine', 1, 1)
    body += paragraph('Ten', 1) + paragraph('Child ten', 1, 1)
    result = convert_list(definitions, body)
    assert len(rendered(result.markdown).xpath('./ol/li/ol/li')) == 2


def test_typed_bullets_still_use_indentation(convert_list):
    body = paragraph('• Parent') + paragraph('• Child', extra='<w:ind w:left="720"/>')
    result = convert_list('', body)
    assert len(rendered(result.markdown).xpath('./ul/li/ul/li')) == 1


def test_list_separator_survives_a_docx_round_trip(convert_list):
    from mdtodoc import convert

    result = convert_list(abstract(level()) + instance(1) + instance(2),
                          paragraph('First', 1) + paragraph('New list', 2))
    round_trip = convert_bytes(convert(result.markdown).data)
    lists = rendered(round_trip.markdown).xpath('./ol')
    assert len(lists) == 2
    assert all(element.get('start', '1') == '1' for element in lists)


@pytest.mark.parametrize('start', [0, 999999999, 1000000000])
def test_large_or_zero_starts_remain_visible(convert_list, start):
    result = convert_list(abstract(level(start=start)) + instance(1), paragraph('Text', 1))
    root = rendered(result.markdown)
    if start <= 999999999:
        assert root.xpath('./ol')[0].get('start') == str(start)
    else:
        assert root.xpath('./ul/li')[0].text == f'{start}. Text'
        assert result.report.warnings[0].code == 'numbering-label-as-text'
