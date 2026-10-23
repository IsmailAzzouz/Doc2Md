"""Resolve Word list definitions, then count each numbering instance separately.

An abstract definition is a reusable template. A numId selects that template,
applies instance-specific overrides and owns its own counters. Keeping those
three steps separate prevents unrelated lists from sharing state.
"""
import re
from dataclasses import dataclass, replace
from typing import Optional

from .xmlns import ILVL, NUMID, VAL, W


_ROMAN = (('m', 1000), ('cm', 900), ('d', 500), ('cd', 400), ('c', 100), ('xc', 90),
          ('l', 50), ('xl', 40), ('x', 10), ('ix', 9), ('v', 5), ('iv', 4), ('i', 1))
_NUMBER_FORMATS = {'decimal', 'decimalZero', 'upperRoman', 'lowerRoman', 'upperLetter', 'lowerLetter'}
_LEVEL_REFERENCE = re.compile(r'%([1-9])')


def _integer(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _value(element, name, default=None):
    child = element.find(W + name)
    return child.get(VAL, default) if child is not None else default


def _enabled(element):
    return element is not None and element.get(VAL) not in ('0', 'false', 'off')


def format_number(number_format: str, number: int) -> str:
    """Format supported Word counters; unknown formats fall back to decimal."""
    if number_format == 'decimalZero':
        return f'{number:02d}'
    if number <= 0:
        return str(number)
    if number_format in ('upperRoman', 'lowerRoman'):
        parts = []
        for symbol, value in _ROMAN:
            count, number = divmod(number, value)
            parts.append(symbol * count)
        text = ''.join(parts)
        return text.upper() if number_format == 'upperRoman' else text
    if number_format in ('upperLetter', 'lowerLetter'):
        # Word repeats letters after Z: AA, BB, ... ZZ, AAA (not spreadsheet columns).
        letter = chr(ord('a') + (number - 1) % 26)
        text = letter * ((number - 1) // 26 + 1)
        return text.upper() if number_format == 'upperLetter' else text
    return str(number)


@dataclass(frozen=True)
class _Level:
    number_format: str
    text: str
    start: int
    restart_after: Optional[int]
    paragraph_style: Optional[str]
    legal: bool


@dataclass(frozen=True)
class ListNumber:
    """The resolved value and visible label for one numbered paragraph."""

    num_id: int
    level: int
    value: int
    label: str
    number_format: str
    unsupported_formats: tuple[str, ...] = ()

    @property
    def is_bullet(self):
        return self.number_format == 'bullet'

    @property
    def has_marker(self):
        return self.number_format != 'none' and (self.is_bullet or bool(self.label))


def _read_level(element, index):
    # lvlRestart is one-based; omitted means the previous level, zero means never.
    # Invalid references are ignored, so they retain the default restart rule.
    restart = _integer(_value(element, 'lvlRestart'), index)
    if not 0 <= restart <= index:
        restart = index
    text_element = element.find(W + 'lvlText')
    text = _value(element, 'lvlText', f'%{index + 1}.')
    if text_element is not None and text_element.get(W + 'null') in ('1', 'true', 'on'):
        text = ''
    return _Level(
        number_format=_value(element, 'numFmt', 'decimal'),
        text=text,
        start=max(0, _integer(_value(element, 'start'), 0)),
        restart_after=restart - 1 if restart else None,
        paragraph_style=_value(element, 'pStyle'),
        legal=_enabled(element.find(W + 'isLgl')),
    )


class Numbering:
    def __init__(self, root, styles=None):
        self._styles = styles
        self._abstract_levels = {}
        self._style_references = {}
        self._style_definitions = {}
        self._instances = {}
        self._resolved_levels = {}
        self._counters = {}
        if root is None:
            return
        for abstract in root.iterfind(W + 'abstractNum'):
            abstract_id = abstract.get(W + 'abstractNumId')
            levels = {}
            for element in abstract.iterfind(W + 'lvl'):
                index = _integer(element.get(ILVL), -1)
                if 0 <= index <= 8:
                    levels[index] = _read_level(element, index)
            self._abstract_levels[abstract_id] = levels
            style_reference = _value(abstract, 'numStyleLink')
            if style_reference:
                self._style_references[abstract_id] = style_reference
            style_definition = _value(abstract, 'styleLink')
            if style_definition:
                self._style_definitions[style_definition] = abstract_id
        for instance in root.iterfind(W + 'num'):
            num_id = _integer(instance.get(NUMID), 0)
            if num_id > 0:
                self._instances[num_id] = instance

    def _levels(self, num_id, visiting=None):
        """Resolve a template and overrides once, without creating counter state."""
        if num_id in self._resolved_levels:
            return self._resolved_levels[num_id]
        visiting = set() if visiting is None else visiting
        instance = self._instances.get(num_id)
        if instance is None or num_id in visiting:
            return {}
        visiting = visiting | {num_id}
        abstract_id = _value(instance, 'abstractNumId')
        levels = dict(self._abstract_levels.get(abstract_id, {}))
        style_id = self._style_references.get(abstract_id)
        if not levels and style_id:
            if self._styles is not None:
                linked_id = self._styles.para(style_id).numid
                levels = dict(self._levels(linked_id, visiting))
            if not levels:
                linked_abstract = self._style_definitions.get(style_id)
                levels = dict(self._abstract_levels.get(linked_abstract, {}))
        for override in instance.iterfind(W + 'lvlOverride'):
            index = _integer(override.get(ILVL), -1)
            if not 0 <= index <= 8:
                continue
            replacement = override.find(W + 'lvl')
            if replacement is not None:
                # A nested lvl replaces the definition; it is not a property patch.
                levels[index] = _read_level(replacement, index)
            start = _integer(_value(override, 'startOverride'), None)
            if index in levels and start is not None and start >= 0:
                # startOverride takes precedence even over the replacement lvl's start.
                levels[index] = replace(levels[index], start=start)
        self._resolved_levels[num_id] = levels
        return levels

    def style_level(self, style_id, num_id):
        """Resolve paragraph-style levels within the selected numbering instance."""
        if style_id is None:
            return 0
        for index, level in self._levels(num_id).items():
            if level.paragraph_style == style_id:
                return index
        return 0

    def step(self, num_id: int, level_index: int) -> Optional[ListNumber]:
        """Count one paragraph and reset only levels triggered by this level."""
        levels = self._levels(num_id)
        definition = levels.get(level_index)
        if definition is None:
            return None
        counters = self._counters.setdefault(num_id, {})
        value = counters[level_index] + 1 if level_index in counters else definition.start
        counters[level_index] = value
        for index, level in levels.items():
            if level.restart_after == level_index:
                counters.pop(index, None)
        label, unsupported = self._label(level_index, levels, counters)
        return ListNumber(num_id, level_index, value, label, definition.number_format, unsupported)

    @staticmethod
    def _label(index, levels, counters):
        definition = levels[index]
        if definition.number_format in ('bullet', 'none'):
            return '', ()
        unsupported = set()

        def substitute(match):
            referenced_index = int(match.group(1)) - 1
            # A label may reference its own level or an ancestor, never a descendant.
            referenced_level = levels.get(referenced_index)
            if referenced_index > index or referenced_level is None:
                return ''
            number = counters.get(referenced_index, referenced_level.start)
            number_format = 'decimal' if definition.legal else referenced_level.number_format
            if number_format not in _NUMBER_FORMATS:
                unsupported.add(number_format)
            return format_number(number_format, number)

        label = _LEVEL_REFERENCE.sub(substitute, definition.text).strip()
        return label, tuple(sorted(unsupported))
