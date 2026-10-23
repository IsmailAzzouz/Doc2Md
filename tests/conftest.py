"""Small, inspectable OOXML packages for converter regression tests."""
import io
import zipfile

import pytest
from lxml import etree

import doctomd.convert as converter
from doctomd.xmlns import A_NS, M_NS, PIC_NS, R_NS, W_NS, WP_NS


@pytest.fixture(autouse=True)
def fail_on_converter_errors(monkeypatch):
    """Unexpected exceptions must fail tests rather than trigger text fallback."""
    monkeypatch.setattr(converter, 'STRICT', True)


@pytest.fixture
def relationships_xml():
    def build(relationships):
        """Map relationship IDs to (type suffix, target, is_external) tuples."""
        root = etree.Element(
            'Relationships',
            xmlns='http://schemas.openxmlformats.org/package/2006/relationships',
        )
        for relationship_id, (kind, target, external) in relationships.items():
            element = etree.SubElement(
                root, 'Relationship', Id=relationship_id,
                Type=R_NS + '/' + kind, Target=target,
            )
            if external:
                element.set('TargetMode', 'External')
        return etree.tostring(root)

    return build


@pytest.fixture
def docx_factory(relationships_xml):
    def build(body, *, relationships=None, parts=None, content_types=None):
        document = (
            f'<w:document xmlns:w="{W_NS}" xmlns:r="{R_NS}" xmlns:m="{M_NS}" '
            f'xmlns:wp="{WP_NS}" xmlns:a="{A_NS}" xmlns:pic="{PIC_NS}">'
            f'<w:body>{body}</w:body></w:document>'
        )
        types = etree.Element(
            'Types',
            xmlns='http://schemas.openxmlformats.org/package/2006/content-types',
        )
        etree.SubElement(
            types, 'Default', Extension='rels',
            ContentType='application/vnd.openxmlformats-package.relationships+xml',
        )
        etree.SubElement(
            types, 'Override', PartName='/word/document.xml',
            ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
        )
        for name, content_type in (content_types or {}).items():
            etree.SubElement(types, 'Override', PartName='/' + name, ContentType=content_type)
        files = {
            '[Content_Types].xml': etree.tostring(types),
            '_rels/.rels': relationships_xml({'main': ('officeDocument', 'word/document.xml', False)}),
            'word/document.xml': document,
            'word/_rels/document.xml.rels': relationships_xml(relationships or {}),
        }
        files.update(parts or {})
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        return output.getvalue()

    return build
