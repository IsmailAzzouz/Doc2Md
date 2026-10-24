"""Read HTML cell content as literal text and inline tokens, not as Markdown."""
import re

from markdown_it.token import Token

from .tables import Paragraph


_FORMATTING = {'strong': 'strong', 'b': 'strong', 'em': 'em', 'i': 'em',
               'del': 'del', 's': 'del', 'strike': 'del', 'u': 'u', 'ins': 'u',
               'sup': 'sup', 'sub': 'sub', 'mark': 'mark', 'code': 'code', 'kbd': 'code', 'tt': 'code'}
_BLOCKS = {'p', 'div', 'section', 'article', 'header', 'footer', 'blockquote', 'figure',
           'figcaption', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li'}
_SKIP = {'script', 'style', 'template', 'iframe'}


def _token(kind, content='', *, tag='', nesting=0, attrs=None):
    token = Token(kind, tag, nesting, attrs=attrs)
    token.content = content
    return token


class ContentReader:
    """Yield paragraphs, lists and tables in their original document order."""

    def __init__(self):
        self.blocks = []
        self.issues = []
        self.current = []
        self.active_formats = set()

    def read(self, element):
        self._children(element)
        self._flush()
        return self.blocks

    def _text(self, text):
        if text:
            self.current.append(_token('text', re.sub(r'[ \t\r\n\f]+', ' ', text)))

    def _flush(self):
        # Formatting tokens may surround whitespace; trim text at the edges
        # without discarding images or explicit line breaks in an empty cell.
        visible = [token for token in self.current if token.type in ('text', 'image', 'hardbreak')]
        if visible and visible[0].type == 'text':
            visible[0].content = visible[0].content.lstrip(' ')
        if visible and visible[-1].type == 'text':
            visible[-1].content = visible[-1].content.rstrip(' ')
        if any(token.type != 'text' or token.content for token in visible):
            self.blocks.append(Paragraph(self.current))
        self.current = []

    def _children(self, element):
        self._text(element.text)
        for child in element:
            self._element(child)
            self._text(child.tail)

    def _element(self, element):
        tag = element.tag
        if not isinstance(tag, str) or tag in _SKIP:
            return
        if tag in ('table', 'ol', 'ul'):
            self._flush()
            self.blocks.append(element)
            return
        if tag == 'pre':
            self._flush()
            lines = ''.join(element.itertext()).replace('\r\n', '\n').split('\n')
            children = []
            for index, line in enumerate(lines):
                if index:
                    children.append(_token('hardbreak'))
                children.append(_token('text', line))
            self.blocks.append(Paragraph(children, preformatted=True))
            return
        block = tag in _BLOCKS
        if block:
            self._flush()
        if tag == 'li':
            self.issues.append('An HTML list item without a list container was retained as text.')
            self._text('• ')
        if tag == 'br':
            self.current.append(_token('hardbreak'))
        elif tag == 'img':
            self.current.append(_token('image', element.get('alt', ''),
                                       attrs={'src': element.get('src', '')}))
        elif tag == 'a':
            self.current.append(_token('link_open', tag='a', nesting=1, attrs={'href': element.get('href', '')}))
            self._children(element)
            self.current.append(_token('link_close', tag='a', nesting=-1))
        elif tag in _FORMATTING:
            name = _FORMATTING[tag]
            already_active = name in self.active_formats
            if not already_active:
                self.active_formats.add(name)
                self.current.append(_token('html_inline', f'<{name}>'))
            self._children(element)
            if not already_active:
                self.current.append(_token('html_inline', f'</{name}>'))
                self.active_formats.remove(name)
        else:
            self._children(element)
        if block:
            self._flush()
