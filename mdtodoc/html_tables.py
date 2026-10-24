"""Parse HTML row groups and spans into the shared Word-table model."""
import re
from html.parser import HTMLParser

from lxml import html
from markdown_it.token import Token

from .html_content import ContentReader
from .tables import Cell, ListBlock, ListItem, Paragraph, Table


_TABLE_START = re.compile(r'^<table(?=[\s>])', re.IGNORECASE)


class _TableBoundary(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.depth = 0
        self.closed = False

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.depth += 1
            self.closed = False

    def handle_endtag(self, tag):
        if tag == 'table':
            self.depth -= 1
            self.closed = self.depth == 0


def table_block(state, start_line, end_line, silent):
    """Keep a complete HTML table together even when rows have blank lines."""
    if state.sCount[start_line] - state.blkIndent >= 4 or not state.md.options['html']:
        return False
    start = state.bMarks[start_line] + state.tShift[start_line]
    if not _TABLE_START.match(state.src[start:state.eMarks[start_line]]):
        return False
    if silent:
        return True
    boundary = _TableBoundary()
    for line in range(start_line, end_line):
        if state.sCount[line] < state.blkIndent and not state.isEmpty(line):
            break
        boundary.feed(state.getLines(line, line + 1, state.blkIndent, True))
        if boundary.closed:
            token = state.push('html_block', '', 0)
            token.map = [start_line, line + 1]
            token.content = state.getLines(start_line, line + 1, state.blkIndent, True)
            state.line = line + 1
            return True
    return False


def read_fragment(source):
    """Recover ordinary HTML syntax without fetching external resources."""
    parser = html.HTMLParser(no_network=True)
    return html.fragment_fromstring(source, create_parent='div', parser=parser)


def read_content(element):
    """Resolve tables and lists recursively, retaining surrounding paragraphs."""
    reader = ContentReader()
    source_blocks = reader.read(element)
    blocks, issues = [], list(reader.issues)
    for block in source_blocks:
        if isinstance(block, Paragraph):
            blocks.append(block)
            continue
        if block.tag in ('ol', 'ul'):
            list_block, list_issues = read_list(block)
            blocks.append(list_block)
            issues.extend(list_issues)
            continue
        table, table_issues = read_table(block)
        issues.extend(table_issues)
        if table.cells:
            for caption in block.findall('caption'):
                caption_blocks, caption_issues = read_content(caption)
                blocks.extend(caption_blocks)
                issues.extend(caption_issues)
            blocks.append(table)
        else:
            fallback, fallback_issues = read_content(block)
            blocks.extend(fallback)
            issues.extend(fallback_issues)
            issues.append('An HTML table without usable rows was retained as text.')
    return blocks, list(dict.fromkeys(issues))


def _list_integer(element, name, default, issues):
    raw = element.get(name)
    if raw is None:
        return default
    try:
        if re.fullmatch(r'\s*[+-]?[0-9]+\s*', raw):
            return int(raw)
    except ValueError:
        pass
    issues.append(f'Invalid list {name}; used {default}.')
    return default


def read_list(element):
    """Resolve HTML starts and per-item values before writing Word numbering."""
    stray_content = bool((element.text or '').strip()) or any(
        (child.tail or '').strip() or (isinstance(child.tag, str) and child.tag != 'li')
        for child in element)
    if stray_content:
        # Malformed lists used to pass through the text reader. Keep that
        # recovery path instead of silently discarding text outside li nodes.
        blocks, issues = read_content(element)
        issues.append('HTML list content outside list items was retained in a bullet item.')
        return ListBlock([ListItem(blocks)]), issues
    ordered = element.tag == 'ol'
    sources = element.findall('li')
    items, issues = [], []
    descending = ordered and 'reversed' in element.attrib
    value = _list_integer(element, 'start', len(sources) if descending else 1, issues) if ordered else 1
    if descending:
        issues.append('Descending list values were retained with individual numbering restarts.')
    if ordered and element.get('type', '1') != '1':
        issues.append('Non-decimal HTML list markers were converted to decimal numbering.')
    for source in sources:
        blocks, content_issues = read_content(source)
        issues.extend(content_issues)
        if ordered:
            value = _list_integer(source, 'value', value, issues)
        items.append(ListItem(blocks, value if ordered else None))
        value += -1 if descending else 1
    if ordered and any(item.value < 0 for item in items):
        # Word counters cannot start below zero. Retain these visible values
        # using the same text-label fallback used by DOCX export.
        issues.append('Negative list values were retained as text labels in bullet items.')
        ordered = False
        for item in items:
            marker = Token('text', '', 0)
            marker.content = f'{item.value}. '
            if item.blocks and isinstance(item.blocks[0], Paragraph):
                item.blocks[0].children.insert(0, marker)
            else:
                item.blocks.insert(0, Paragraph([marker]))
            item.value = None
    return ListBlock(items, ordered), list(dict.fromkeys(issues))


def _span(element, name, issues):
    raw = element.get(name)
    if raw is None:
        return 1
    if not re.fullmatch(r'\s*\+?[0-9]+\s*', raw):
        issues.append(f'Invalid {name}; used 1.')
        return 1
    try:
        value = int(raw)
    except ValueError:
        issues.append(f'Invalid {name}; used 1.')
        return 1
    limit = 1000 if name == 'colspan' else 65534
    if value > limit or (name == 'colspan' and value == 0):
        issues.append(f'Out-of-range {name}; used 1.')
        return 1
    return value


def _alignment(element, row):
    for source in (element, row):
        match = re.search(r'(?:^|;)\s*text-align\s*:\s*(left|center|right|justify)\b',
                          source.get('style', ''), re.IGNORECASE)
        value = match.group(1).lower() if match else source.get('align', '').lower()
        if value in ('left', 'center', 'right', 'justify'):
            return 'both' if value == 'justify' else value
    return None


def _row_groups(element):
    groups, loose_rows, footers = [], [], []
    for child in element:
        if child.tag == 'tr':
            loose_rows.append(child)
        elif child.tag in ('thead', 'tbody', 'tfoot'):
            if loose_rows:
                groups.append(loose_rows)
                loose_rows = []
            rows = child.findall('tr')
            (footers if child.tag == 'tfoot' else groups).append(rows)
    if loose_rows:
        groups.append(loose_rows)
    return groups + footers


def read_table(element):
    """Resolve cells without overlap; report repairs and content approximations."""
    cells, issues, header_rows = [], [], set()
    row_offset = columns = 0
    leading_headers = True
    for rows in _row_groups(element):
        occupied = [set() for _ in rows]
        for index, row in enumerate(rows):
            elements = [child for child in row if child.tag in ('th', 'td')]
            is_header = bool(elements) and all(child.tag == 'th' for child in elements)
            if leading_headers and (is_header or row.getparent().tag == 'thead'):
                header_rows.add(row_offset + index)
            else:
                leading_headers = False
            column = 0
            for source in elements:
                colspan = _span(source, 'colspan', issues)
                rowspan = _span(source, 'rowspan', issues)
                remaining = len(rows) - index
                if rowspan == 0:
                    rowspan = remaining
                elif rowspan > remaining:
                    issues.append('rowspan exceeded its row group; shortened it to the remaining rows.')
                    rowspan = remaining
                while column in occupied[index]:
                    column += 1
                if any(slot in occupied[index] for slot in range(column, column + colspan)):
                    issues.append('Overlapping HTML cells were moved to the next available grid position.')
                    while any(slot in occupied[index] for slot in range(column, column + colspan)):
                        column += 1
                blocks, content_issues = read_content(source)
                issues.extend(content_issues)
                cells.append(Cell(row_offset + index, column, blocks, colspan, rowspan,
                                  _alignment(source, row), source.tag == 'th'))
                for covered_row in range(index, index + rowspan):
                    occupied[covered_row].update(range(column, column + colspan))
                column += colspan
                columns = max(columns, column)
        row_offset += len(rows)
    return Table(cells, row_offset, columns, header_rows), list(dict.fromkeys(issues))
