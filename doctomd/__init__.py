"""Word -> Markdown; default table output needs only lxml."""
import io

from .convert import Result, convert_package
from .package import DocError, Package

__all__ = ['convert_file', 'convert_bytes', 'Result', 'DocError']


def convert_bytes(data, media_dir='media', embed_images=False, *, table_format='markdown'):
    """Convert .docx bytes; table_format='html' preserves merged-cell spans."""
    return convert_package(Package(io.BytesIO(data)), media_dir, embed_images, table_format=table_format)


def convert_file(path, media_dir='media', embed_images=False, *, table_format='markdown'):
    """Convert a Word-like file. .docx/.docm/.dotx and Flat-OPC .xml are parsed natively; other
    formats (.doc .rtf .odt ...) go through LibreOffice or MS Word (if installed) first.
    Use table_format='html' to preserve merged-cell spans in HTML tables.
    """
    from . import flatopc, legacy
    kind = legacy.sniff(path)
    if kind == 'docx':
        return convert_package(Package(path), media_dir, embed_images, table_format=table_format)
    if kind == 'flatopc':
        with open(path, 'rb') as f:
            return convert_bytes(flatopc.to_docx_bytes(f.read()), media_dir, embed_images, table_format=table_format)
    return convert_bytes(legacy.to_docx_bytes(path), media_dir, embed_images, table_format=table_format)
