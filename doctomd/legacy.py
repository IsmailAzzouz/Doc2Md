"""Non-docx Word-like files (.doc .rtf .odt .dot .wps ...) -> docx via LibreOffice or MS Word."""
import os
import shutil
import subprocess
import tempfile
import zipfile

from .package import DocError

_OLE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
_WORD_PS = r"""
$ErrorActionPreference = 'Stop'
$w = New-Object -ComObject Word.Application
$w.Visible = $false
$w.DisplayAlerts = 0
try {
  $d = $w.Documents.Open($env:D2M_IN, $false, $true)
  [IO.File]::WriteAllText($env:D2M_OUT, $d.Content.WordOpenXML, (New-Object Text.UTF8Encoding $false))
  $d.Close($false)
} finally { $w.Quit() }
"""


def sniff(path):
    """-> 'docx' | 'flatopc' | 'convert' (needs external converter). Raises DocError for non-documents."""
    try:
        with open(path, 'rb') as f:
            head = f.read(512)
    except OSError as e:
        raise DocError('cannot read %s: %s' % (path, e))
    if head[:4] == b'PK\x03\x04':
        try:
            with zipfile.ZipFile(path) as z:
                names = {n.lower() for n in z.namelist()}
        except zipfile.BadZipFile:
            raise DocError('corrupt zip container')
        if 'word/document.xml' in names or '_rels/.rels' in names and any(n.startswith('word/') for n in names):
            return 'docx'
        if 'mimetype' in names or 'content.xml' in names:
            return 'convert'  # OpenDocument
        raise DocError('zip file is not a Word document')
    if b'xmlPackage' in head:
        return 'flatopc'
    if head[:8] == _OLE or head[:5] == b'{\\rtf':
        return 'convert'
    if os.path.splitext(path)[1].lower() in ('.doc', '.dot', '.rtf', '.odt', '.wps', '.wpd', '.xml', '.htm', '.html'):
        return 'convert'
    raise DocError('unrecognized file format (not a Word document)')


def _soffice():
    exe = shutil.which('soffice') or shutil.which('libreoffice')
    if exe:
        return exe
    for p in (r'C:\Program Files\LibreOffice\program\soffice.exe',
              r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
              '/Applications/LibreOffice.app/Contents/MacOS/soffice'):
        if os.path.exists(p):
            return p
    return None


def to_docx_bytes(path):
    """Convert with whichever backend exists; returns docx bytes."""
    path = os.path.abspath(path)
    errors = []
    with tempfile.TemporaryDirectory(prefix='doctomd_') as tmp:
        out = os.path.join(tmp, os.path.splitext(os.path.basename(path))[0] + '.docx')
        so = _soffice()
        if so:
            try:
                profile = 'file:///' + tmp.replace('\\', '/') + '/profile'
                subprocess.run([so, '-env:UserInstallation=' + profile, '--headless', '--convert-to', 'docx',
                                '--outdir', tmp, path], check=True, capture_output=True, timeout=180)
                if os.path.exists(out):
                    return _read(out)
                errors.append('LibreOffice produced no output')
            except (subprocess.SubprocessError, OSError) as e:
                errors.append('LibreOffice failed: %s' % e)
        if os.name == 'nt':
            flat = os.path.join(tmp, 'word.flat.xml')   # SaveAs can block on sensitivity-label prompts; dump XML instead
            env = dict(os.environ, D2M_IN=path, D2M_OUT=flat)
            try:
                r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', _WORD_PS],
                                   env=env, capture_output=True, text=True, timeout=120)
                if r.returncode == 0 and os.path.exists(flat):
                    from . import flatopc
                    return flatopc.to_docx_bytes(_read(flat))
                errors.append('MS Word failed: %s' % (r.stderr.strip().splitlines() or ['unknown'])[0])
            except (subprocess.SubprocessError, OSError) as e:
                errors.append('MS Word failed: %s' % e)
    raise DocError('this format needs LibreOffice or MS Word installed to be converted to .docx (%s)'
                   % '; '.join(errors or ['no converter found']))


def _read(p):
    with open(p, 'rb') as f:
        return f.read()
