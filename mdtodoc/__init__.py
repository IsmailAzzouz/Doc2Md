"""Markdown -> .docx, including HTML tables parsed with lxml."""
from .build import Result, convert

__all__ = ['convert', 'Result']
