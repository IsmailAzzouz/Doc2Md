"""mdtodoc: Markdown -> .docx (inverse of doctomd). Needs lxml-free OOXML writer + markdown-it-py + mdit-py-plugins."""
from .build import Result, convert

__all__ = ['convert', 'Result']
