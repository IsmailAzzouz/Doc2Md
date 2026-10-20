"""Image loading + dimension sniffing without Pillow (Pillow only used to convert exotic formats)."""
import base64
import os
import struct
from urllib.parse import unquote

MIME = {'png': 'image/png', 'jpeg': 'image/jpeg', 'gif': 'image/gif', 'bmp': 'image/bmp'}


def sniff(data):
    """-> (ext, width_px, height_px, dpi or None) or None if not a Word-embeddable raster image."""
    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        w, h = struct.unpack('>II', data[16:24])
        dpi = None
        i = data.find(b'pHYs')
        if i > 0 and len(data) >= i + 13 and data[i + 12] == 1:
            ppu = struct.unpack('>I', data[i + 4:i + 8])[0]
            dpi = ppu * 0.0254
        return 'png', w, h, dpi
    if data[:2] == b'\xff\xd8':
        i, n, dpi = 2, len(data), None
        while i + 9 < n:
            if data[i] != 0xFF:
                i += 1
                continue
            m = data[i + 1]
            if m == 0xFF:
                i += 1
                continue
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                i += 2
                continue
            ln = struct.unpack('>H', data[i + 2:i + 4])[0]
            if m == 0xE0 and data[i + 4:i + 9] == b'JFIF\0' and ln >= 14:
                units, dx = data[i + 11], struct.unpack('>H', data[i + 12:i + 14])[0]
                if units == 1 and dx:
                    dpi = dx
                elif units == 2 and dx:
                    dpi = dx * 2.54
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack('>HH', data[i + 5:i + 9])
                return 'jpeg', w, h, dpi
            i += 2 + ln
        return None
    if data[:4] == b'GIF8' and len(data) >= 10:
        w, h = struct.unpack('<HH', data[6:10])
        return 'gif', w, h, None
    if data[:2] == b'BM' and len(data) >= 26:
        w, h = struct.unpack('<ii', data[18:26])
        return 'bmp', w, abs(h), None
    return None


def _to_png(data):
    """webp/tiff/ico/... -> PNG bytes via Pillow when available, else None."""
    try:
        import io
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        im.load()
        out = io.BytesIO()
        im.save(out, 'PNG')
        return out.getvalue()
    except Exception:
        return None


def load(src, base_dir):
    """-> ('ok', bytes) | ('remote', url) | ('missing', reason)."""
    s = src.strip().strip('<>')
    if s.startswith('data:'):
        try:
            head, payload = s.split(',', 1)
            data = base64.b64decode(unquote(payload)) if ';base64' in head else unquote(payload).encode('latin-1')
        except Exception:
            return 'missing', 'bad data URI'
        return 'ok', data
    if s.lower().startswith(('http://', 'https://', 'ftp://')):
        return 'remote', s
    if s.lower().startswith('file:///'):
        s = s[8:] if os.name == 'nt' else s[7:]
    path = os.path.normpath(os.path.join(base_dir, unquote(s)))
    try:
        with open(path, 'rb') as f:
            return 'ok', f.read()
    except OSError as e:
        return 'missing', '%s' % e.strerror


def prepare(data):
    """-> (ext, data, w, h, dpi) ready for embedding, or None."""
    info = sniff(data)
    if info is None:
        data = _to_png(data)
        info = sniff(data) if data else None
        if info is None:
            return None
    ext, w, h, dpi = info
    if not w or not h:
        return None
    return ext, data, w, h, dpi
