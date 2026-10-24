"""A small table model and a shared OOXML writer for Markdown and HTML input."""
from dataclasses import dataclass, field
from typing import Optional, Union

from markdown_it.token import Token


@dataclass
class Paragraph:
    children: list[Token]
    preformatted: bool = False


@dataclass
class ListItem:
    blocks: list[Union[Paragraph, 'Table', 'ListBlock']]
    value: Optional[int] = None


@dataclass
class ListBlock:
    items: list[ListItem]
    ordered: bool = False


@dataclass
class Cell:
    row: int
    column: int
    blocks: list[Union[Paragraph, 'Table', ListBlock]]
    colspan: int = 1
    rowspan: int = 1
    alignment: Optional[str] = None
    header: bool = False


@dataclass
class Table:
    cells: list[Cell]
    rows: int
    columns: int
    header_rows: set[int] = field(default_factory=set)


def _text_length(blocks):
    length = 0
    for block in blocks:
        if isinstance(block, Paragraph):
            length += sum(len(token.content) for token in block.children if token.type in ('text', 'code_inline'))
        elif isinstance(block, ListBlock):
            length += sum(_text_length(item.blocks) for item in block.items)
        else:
            length += sum(_text_length(cell.blocks) for cell in block.cells)
    return length


def _column_widths(weights, available_width):
    """Keep the grid within its container, even when nested cells are narrow."""
    available_width = max(int(available_width), len(weights))
    minimum = min(500, available_width // len(weights))
    remaining = available_width - minimum * len(weights)
    widths = [minimum + int(remaining * weight / sum(weights)) for weight in weights]
    widths[-1] += available_width - sum(widths)
    return widths


def write_table(table, available_width, left, render_cell):
    """Write origins, vertical continuations and empty grid positions.

    render_cell receives the origin cell and its width in twips. Continuation
    cells have no content; their gridSpan must match the merge origin exactly.
    """
    if not table.cells or not table.columns:
        return ''
    weights = [6] * table.columns
    placements = [{} for _ in range(table.rows)]
    for cell in table.cells:
        length = _text_length(cell.blocks)
        weight = min(length, 50) / cell.colspan
        for column in range(cell.column, cell.column + cell.colspan):
            weights[column] = max(weights[column], weight)
        for row in range(cell.row, cell.row + cell.rowspan):
            placements[row][cell.column] = cell
    widths = _column_widths(weights, available_width)
    out = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/>'
           f'<w:tblW w:w="{sum(widths)}" w:type="dxa"/>']
    if left:
        out.append(f'<w:tblInd w:w="{left}" w:type="dxa"/>')
    first_header = int(0 in table.header_rows)
    out.append('<w:tblLayout w:type="fixed"/>'
               f'<w:tblLook w:firstRow="{first_header}" w:lastRow="0" w:firstColumn="0" '
               'w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr><w:tblGrid>')
    out.extend(f'<w:gridCol w:w="{width}"/>' for width in widths)
    out.append('</w:tblGrid>')
    for row_index, row in enumerate(placements):
        header = '<w:tblHeader/>' if row_index in table.header_rows else ''
        out.append(f'<w:tr><w:trPr><w:cantSplit/>{header}</w:trPr>')
        column = 0
        while column < table.columns:
            cell = row.get(column)
            span = cell.colspan if cell is not None else 1
            width = sum(widths[column:column + span])
            properties = f'<w:tcW w:w="{width}" w:type="dxa"/>'
            if span > 1:
                properties += f'<w:gridSpan w:val="{span}"/>'
            if cell is not None and cell.rowspan > 1:
                state = 'restart' if cell.row == row_index else 'continue'
                properties += f'<w:vMerge w:val="{state}"/>'
            content = render_cell(cell, width) if cell is not None and cell.row == row_index else '<w:p/>'
            out.append(f'<w:tc><w:tcPr>{properties}</w:tcPr>{content or "<w:p/>"}</w:tc>')
            column += span
        out.append('</w:tr>')
    # A paragraph after a table keeps following tables separate in Word and
    # supplies the required final paragraph when this block is inside a cell.
    out.append('</w:tbl><w:p><w:pPr><w:spacing w:after="0" w:line="120" '
               'w:lineRule="exact"/></w:pPr></w:p>')
    return ''.join(out)
