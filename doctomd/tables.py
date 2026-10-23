"""Read Word's table grid and render it without mixing layout with cell content.

Rows contain only the origins of merged cells. Each origin retains the XML
cells it absorbed, so the converter can preserve their content in source order.
"""
from dataclasses import dataclass
from typing import Optional

from lxml import etree

from .xmlns import JC, P, PPR, TC, TCPR, TR, VAL, W


@dataclass
class Cell:
    column: int
    colspan: int
    elements: list[etree._Element]
    alignment: str = ''
    vertical_merge: Optional[str] = None
    rowspan: int = 1


@dataclass
class Table:
    rows: list[list[Cell]]
    columns: int
    issues: list[str]

    @property
    def merged_cells(self):
        return [cell for row in self.rows for cell in row
                if cell.colspan > 1 or cell.rowspan > 1]


def _grid_value(parent, name, default, minimum, issues):
    element = parent.find(W + name) if parent is not None else None
    if element is None:
        return default
    try:
        value = int(element.get(VAL))
        if value >= minimum:
            return value
    except (TypeError, ValueError):
        pass
    issues.append(f'Invalid {name}; used {default}.')
    return default


def _merge_state(properties, name, issues):
    element = properties.find(W + name) if properties is not None else None
    if element is None:
        return None
    value = element.get(VAL, 'continue')
    if value in ('restart', 'continue'):
        return value
    issues.append(f'Invalid {name}; kept the cell separate.')
    return None


def _alignment(element):
    alignment = element.find(f'{P}/{PPR}/{JC}')
    value = alignment.get(VAL) if alignment is not None else None
    return {'center': 'center', 'right': 'right', 'end': 'right'}.get(value, '')


def _read_row(row, grid_columns, issues):
    """Place cells on the shared grid and combine legacy horizontal merges."""
    properties = row.find(W + 'trPr')
    column = _grid_value(properties, 'gridBefore', 0, 0, issues)
    if grid_columns and column > grid_columns:
        issues.append('gridBefore exceeds the table grid; ignored the offset.')
        column = 0
    cells = []
    horizontal = None
    for element in row.iterfind(TC):
        properties = element.find(TCPR)
        span = _grid_value(properties, 'gridSpan', 1, 1, issues)
        vertical = _merge_state(properties, 'vMerge', issues)
        merge = _merge_state(properties, 'hMerge', issues)
        cell = Cell(column, span, [element], _alignment(element), vertical)
        if merge == 'continue' and horizontal is not None and horizontal.vertical_merge == vertical:
            horizontal.colspan += span
            horizontal.elements.append(element)
        else:
            if merge == 'continue':
                issues.append('Unmatched horizontal merge; kept the cell separate.')
            cells.append(cell)
            horizontal = cell if merge == 'restart' else None
        column += span
    after = _grid_value(row.find(W + 'trPr'), 'gridAfter', 0, 0, issues)
    if grid_columns and after and column + after != grid_columns:
        issues.append('gridAfter conflicts with the table grid; ignored the offset.')
        after = 0
    return cells, column + after


def read_table(element) -> Table:
    """Resolve spans without modifying XML or converting any cell content."""
    grid = element.find(W + 'tblGrid')
    grid_columns = len(grid.findall(W + 'gridCol')) if grid is not None else 0
    columns = grid_columns
    rows, issues = [], []
    previous_merges = {}
    for row in element.iterfind(TR):
        cells, width = _read_row(row, grid_columns, issues)
        columns = max(columns, width)
        origins, current_merges = [], {}
        for cell in cells:
            # A vertical continuation must cover exactly the same grid columns
            # as its origin and must be present in every intervening row.
            key = (cell.column, cell.colspan)
            origin = previous_merges.get(key)
            if cell.vertical_merge == 'continue' and origin is not None:
                origin.rowspan += 1
                origin.elements.extend(cell.elements)
                current_merges[key] = origin
                continue
            if cell.vertical_merge == 'continue':
                issues.append('Unmatched vertical merge; kept the cell separate.')
            origins.append(cell)
            if cell.vertical_merge == 'restart':
                current_merges[key] = cell
        rows.append(origins)
        previous_merges = current_merges
    return Table(rows, columns, list(dict.fromkeys(issues)))


def cell_text(cell, contents):
    """Include text from continuation cells once, at the merged cell's origin."""
    return '<br>'.join(contents[element] for element in cell.elements if contents[element])


def flatten(table, contents):
    """Readable fallback for a table embedded inside another cell."""
    rows = []
    for cells in table.rows:
        texts = [cell_text(cell, contents) for cell in cells]
        rows.append(' · '.join(text for text in texts if text))
    return '<br>'.join(rows)


def render_markdown(table, contents):
    rows = []
    alignments = [''] * table.columns
    alignment_row = min(1, len(table.rows) - 1)
    for index, cells in enumerate(table.rows):
        row = [''] * table.columns
        for cell in cells:
            row[cell.column] = cell_text(cell, contents).replace('|', '\\|')
            if index == alignment_row:
                alignments[cell.column:cell.column + cell.colspan] = [cell.alignment] * cell.colspan
        rows.append(row)
    if not rows or not table.columns or not any(text for row in rows for text in row):
        return ''
    widths = [max(len(row[column]) for row in rows) for column in range(table.columns)]
    widths = [max(width, 3) if width <= 40 else 0 for width in widths]

    def render_row(cells):
        return '| ' + ' | '.join(text.ljust(width) for text, width in zip(cells, widths)) + ' |'

    delimiters = []
    for width, alignment in zip(widths, alignments):
        width = max(width, 3)
        if alignment == 'center':
            delimiters.append(':' + '-' * (width - 2) + ':')
        elif alignment == 'right':
            delimiters.append('-' * (width - 1) + ':')
        else:
            delimiters.append('-' * width)
    return '\n'.join([render_row(rows[0]), '| ' + ' | '.join(delimiters) + ' |'] +
                     [render_row(row) for row in rows[1:]])


def render_html(table, contents, render_inline):
    """Emit spans and empty grid positions; never invent a header row."""
    if not table.rows or not table.columns:
        return ''
    parts = ['<table>']
    occupied_until = {}
    for row_index, cells in enumerate(table.rows):
        parts.append('<tr>')
        by_column = {cell.column: cell for cell in cells}
        column = 0
        while column < table.columns:
            if occupied_until.get(column, 0) > row_index:
                column += 1
                continue
            cell = by_column.get(column)
            if cell is None:
                parts.append('<td></td>')
                column += 1
                continue
            attributes = ''
            if cell.colspan > 1:
                attributes += f' colspan="{cell.colspan}"'
            if cell.rowspan > 1:
                attributes += f' rowspan="{cell.rowspan}"'
            if cell.alignment:
                attributes += f' align="{cell.alignment}"'
            parts.append(f'<td{attributes}>{render_inline(cell_text(cell, contents))}</td>')
            for covered in range(column, column + cell.colspan):
                occupied_until[covered] = row_index + cell.rowspan
            column += cell.colspan
        parts.append('</tr>')
    parts.append('</table>')
    # One HTML block also works inside an indented Markdown footnote definition.
    return ''.join(parts)
