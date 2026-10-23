"""OPC package access: zip container + relationships."""
import posixpath
import zipfile

from lxml import etree

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True,
                          remove_comments=True, remove_pis=True)
_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'
_OFFICE_DOC = '/officeDocument'
_CONTENT_TYPES = '{http://schemas.openxmlformats.org/package/2006/content-types}'


class DocError(Exception):
    """Input is not a readable Word document."""


class Package:
    def __init__(self, src):
        try:
            self.zip = zipfile.ZipFile(src)
        except (zipfile.BadZipFile, OSError, ValueError) as e:
            raise DocError('not a valid .docx (zip) file: %s' % e)
        self._names = {n.lower(): n for n in self.zip.namelist()}
        self._rels = {}
        self._content_types = None
        self.main = self._find_main()

    # -- raw access
    def has(self, name):
        return name.lstrip('/').lower() in self._names

    def read(self, name):
        real = self._names.get(name.lstrip('/').lower())
        if real is None:
            return None
        try:
            return self.zip.read(real)
        except (zipfile.BadZipFile, KeyError, RuntimeError, OSError):
            return None

    def xml(self, name):
        data = self.read(name) if name else None
        if data is None:
            return None
        try:
            return etree.fromstring(data, _PARSER)
        except etree.XMLSyntaxError:
            return None

    # -- content types
    def content_type(self, part: str) -> str:
        """Return a part's declared MIME type, preferring overrides to extensions."""
        if self._content_types is None:
            defaults, overrides = {}, {}
            root = self.xml('[Content_Types].xml')
            if root is not None:
                for element in root:
                    content_type = element.get('ContentType', '')
                    if element.tag == _CONTENT_TYPES + 'Default':
                        defaults[element.get('Extension', '').lower()] = content_type
                    elif element.tag == _CONTENT_TYPES + 'Override':
                        name = element.get('PartName', '').lstrip('/').lower()
                        overrides[name] = content_type
            self._content_types = defaults, overrides
        defaults, overrides = self._content_types
        name = part.lstrip('/').lower()
        extension = posixpath.splitext(name)[1].lstrip('.')
        return overrides.get(name, defaults.get(extension, ''))

    # -- relationships
    def rels(self, part):
        """{rId: (target, is_external, type)} with internal targets resolved to zip names."""
        got = self._rels.get(part)
        if got is not None:
            return got
        d, f = posixpath.split(part)
        root = self.xml(posixpath.join(d, '_rels', f + '.rels'))
        out = {}
        if root is not None:
            for r in root.iter(_REL):
                tgt = r.get('Target') or ''
                ext = r.get('TargetMode') == 'External'
                if not ext:
                    tgt = tgt.lstrip('/') if tgt.startswith('/') else posixpath.normpath(posixpath.join(d, tgt))
                out[r.get('Id')] = (tgt, ext, r.get('Type') or '')
        self._rels[part] = out
        return out

    def related(self, part, kind):
        """Zip name of the first internal relationship of `part` whose type ends with /kind."""
        for tgt, ext, typ in self.rels(part).values():
            if not ext and typ.endswith('/' + kind):
                return tgt
        return None

    def _find_main(self):
        root = self.xml('_rels/.rels')
        if root is not None:
            for r in root.iter(_REL):
                if (r.get('Type') or '').endswith(_OFFICE_DOC):
                    return (r.get('Target') or '').lstrip('/') or 'word/document.xml'
        if self.has('word/document.xml'):
            return 'word/document.xml'
        raise DocError('zip file has no Word document part (word/document.xml)')
