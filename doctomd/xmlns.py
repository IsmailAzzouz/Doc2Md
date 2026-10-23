"""Clark-notation tag/attribute constants used across the converter."""

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
WP_NS = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
PIC_NS = 'http://schemas.openxmlformats.org/drawingml/2006/picture'
M_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math'
MC_NS = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
V_NS = 'urn:schemas-microsoft-com:vml'
O_NS = 'urn:schemas-microsoft-com:office:office'
C_NS = 'http://schemas.openxmlformats.org/drawingml/2006/chart'
DGM_NS = 'http://schemas.openxmlformats.org/drawingml/2006/diagram'

W = '{%s}' % W_NS
R = '{%s}' % R_NS
WP = '{%s}' % WP_NS
A = '{%s}' % A_NS
PIC = '{%s}' % PIC_NS
M = '{%s}' % M_NS
MC = '{%s}' % MC_NS
V = '{%s}' % V_NS
O = '{%s}' % O_NS
C = '{%s}' % C_NS
DGM = '{%s}' % DGM_NS

# --- body / block level
BODY = W + 'body'
DOCUMENT = W + 'document'
P = W + 'p'
TBL = W + 'tbl'
ALTCHUNK = W + 'altChunk'
TR = W + 'tr'
TC = W + 'tc'
TCPR = W + 'tcPr'
GRIDSPAN = W + 'gridSpan'
VMERGE = W + 'vMerge'
SDT = W + 'sdt'
SDTCONTENT = W + 'sdtContent'
SDTPR = W + 'sdtPr'
PPR = W + 'pPr'
PSTYLE = W + 'pStyle'
NUMPR = W + 'numPr'
NUMID = W + 'numId'
ILVL = W + 'ilvl'
OUTLINELVL = W + 'outlineLvl'
PBDR = W + 'pBdr'
JC = W + 'jc'

# --- inline level
R_ = W + 'r'
RPR = W + 'rPr'
T = W + 't'
TAB = W + 'tab'
PTAB = W + 'ptab'
BR = W + 'br'
CR = W + 'cr'
NOBREAKHYPHEN = W + 'noBreakHyphen'
SYM = W + 'sym'
HYPERLINK = W + 'hyperlink'
FLDSIMPLE = W + 'fldSimple'
FLDCHAR = W + 'fldChar'
INSTRTEXT = W + 'instrText'
FFDATA = W + 'ffData'
CHECKBOX = W + 'checkBox'
CHECKED = W + 'checked'
DEFAULT = W + 'default'
INS = W + 'ins'
DEL = W + 'del'
MOVETO = W + 'moveTo'
MOVEFROM = W + 'moveFrom'
SMARTTAG = W + 'smartTag'
CUSTOMXML = W + 'customXml'
BDO = W + 'bdo'
DIR = W + 'dir'
BOOKMARKSTART = W + 'bookmarkStart'
FOOTNOTEREF = W + 'footnoteReference'
ENDNOTEREF = W + 'endnoteReference'
COMMENTREF = W + 'commentReference'
DRAWING = W + 'drawing'
PICT = W + 'pict'
OBJECT = W + 'object'
TXBXCONTENT = W + 'txbxContent'
FOOTNOTE = W + 'footnote'
ENDNOTE = W + 'endnote'

# --- attributes
VAL = W + 'val'
ID = W + 'id'
NAME = W + 'name'
ANCHOR = W + 'anchor'
TYPE = W + 'type'
FLDCHARTYPE = W + 'fldCharType'
INSTR = W + 'instr'
R_ID = R + 'id'
R_EMBED = R + 'embed'
R_LINK = R + 'link'

# --- run properties
B = W + 'b'
I = W + 'i'
STRIKE = W + 'strike'
DSTRIKE = W + 'dstrike'
U = W + 'u'
VERTALIGN = W + 'vertAlign'
RFONTS = W + 'rFonts'
HIGHLIGHT = W + 'highlight'
VANISH = W + 'vanish'
RSTYLE = W + 'rStyle'

# --- drawing / vml
WP_DOCPR = WP + 'docPr'
WP_ANCHOR = WP + 'anchor'
A_BLIP = A + 'blip'
PIC_BLIPFILL = PIC + 'blipFill'
C_CHART = C + 'chart'
DGM_RELIDS = DGM + 'relIds'
MC_ALT = MC + 'AlternateContent'
MC_CHOICE = MC + 'Choice'
MC_FALLBACK = MC + 'Fallback'
V_IMAGEDATA = V + 'imagedata'
O_RELID = O + 'relid'
O_TITLE = O + 'title'
O_HR = O + 'hr'
O_OLEOBJECT = O + 'OLEObject'

# --- math
M_OMATH = M + 'oMath'
M_OMATHPARA = M + 'oMathPara'
