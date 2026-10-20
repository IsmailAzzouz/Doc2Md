"""Flat OPC (single XML file, e.g. Word's Range.WordOpenXML or 'Word XML Document') -> .docx bytes."""
import base64
import io
import zipfile

from lxml import etree

PKG = '{http://schemas.microsoft.com/office/2006/xmlPackage}'


def is_flat_opc(head):
    return b'<?xml' in head[:64] and b'xmlPackage' in head or b'<pkg:package' in head


def to_docx_bytes(xml_bytes):
    root = etree.fromstring(xml_bytes, etree.XMLParser(resolve_entities=False, huge_tree=True))
    files, types = [], []
    for part in root.iter(PKG + 'part'):
        name = part.get(PKG + 'name').lstrip('/')
        xd = part.find(PKG + 'xmlData')
        if xd is not None and len(xd):
            data = etree.tostring(xd[0], xml_declaration=True, encoding='UTF-8', standalone=True)
        else:
            bd = part.find(PKG + 'binaryData')
            if bd is None or not bd.text:
                continue
            data = base64.b64decode(bd.text)
        files.append((name, data))
        if not name.endswith('.rels'):
            types.append((name, part.get(PKG + 'contentType') or 'application/octet-stream'))
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
          ''.join('<Override PartName="/%s" ContentType="%s"/>' % (n, t.replace('&', '&amp;')) for n, t in types) +
          '</Types>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', ct)
        for name, data in files:
            z.writestr(name, data)
    return buf.getvalue()
