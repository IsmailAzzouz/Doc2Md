"""Readable text fallbacks for Word's embedded alternative-format imports.

HTML is deliberately converted to plain text, not passed through as raw markup.
Other document formats require their own converters and are reported by callers.
"""
import codecs
from email.message import Message

from lxml import etree, html


class ImportedContentError(ValueError):
    """An import cannot be decoded or its format has no text fallback."""


_BLOCK_TAGS = {
    'address', 'article', 'aside', 'blockquote', 'div', 'dl', 'dt', 'dd',
    'figcaption', 'figure', 'footer', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre', 'section',
    'table', 'tbody', 'td', 'th', 'thead', 'tr', 'ul',
}
_HIDDEN_TAGS = {'head', 'script', 'style', 'template'}


def _charset(content_type):
    header = Message()
    header['content-type'] = content_type
    return header.get_content_charset()


def _decode(data, content_type, is_html):
    # A BOM is authoritative, including when a producer writes a stale charset.
    for marker, encoding in (
        (codecs.BOM_UTF32_LE, 'utf-32'), (codecs.BOM_UTF32_BE, 'utf-32'),
        (codecs.BOM_UTF16_LE, 'utf-16'), (codecs.BOM_UTF16_BE, 'utf-16'),
        (codecs.BOM_UTF8, 'utf-8-sig'),
    ):
        if data.startswith(marker):
            return data.decode(encoding)

    encoding = _charset(content_type)
    if is_html and not encoding:
        # Parse only to discover an HTML charset; no linked resources are loaded.
        document = html.document_fromstring(data, parser=html.HTMLParser(no_network=True))
        for meta in document.iter('meta'):
            encoding = meta.get('charset')
            if not encoding and meta.get('http-equiv', '').lower() == 'content-type':
                encoding = _charset(meta.get('content', ''))
            if encoding:
                break
    return data.decode(encoding or 'utf-8')


def _visible_text(element):
    """Keep block boundaries and image labels without emitting HTML or CSS."""
    if not isinstance(element.tag, str) or element.tag in _HIDDEN_TAGS:
        return
    if element.tag == 'br':
        yield '\n'
        return
    if element.tag == 'img':
        yield element.get('alt') or '[Image omitted]'
        return
    if element.tag in _BLOCK_TAGS:
        yield '\n'
    if element.text:
        yield element.text
    for child in element:
        yield from _visible_text(child)
        if child.tail:
            yield child.tail
    if element.tag in _BLOCK_TAGS:
        yield '\n'


def extract_text(data: bytes, content_type: str) -> tuple[str, bool]:
    """Return (text, is_approximation), or explain why the import is unreadable.

    UTF-8, Unicode BOMs, MIME charsets and HTML meta charsets are supported.
    Invalid text is reported instead of silently replacing undecodable bytes.
    """
    media_type = content_type.split(';', 1)[0].strip().lower()
    is_html = media_type in ('text/html', 'application/xhtml+xml')
    if media_type != 'text/plain' and not is_html:
        raise ImportedContentError('Unsupported import format: %s.' % (media_type or 'unknown'))
    if not data.strip():
        return '', is_html
    try:
        text = _decode(data, content_type, is_html)
        if not is_html:
            return text.replace('\r\n', '\n').replace('\r', '\n'), False
        # Parse decoded text with a fixed encoding so stale meta/XML declarations
        # cannot reinterpret it (lxml also rejects XML declarations on str input).
        parser = html.HTMLParser(encoding='utf-8', no_network=True)
        document = html.document_fromstring(text.encode('utf-8'), parser=parser)
        lines = ''.join(_visible_text(document)).splitlines()
        return '\n\n'.join(' '.join(line.split()) for line in lines if line.strip()), True
    except (LookupError, etree.ParserError, ValueError) as error:
        raise ImportedContentError('Could not decode imported text: %s.' % error) from error
