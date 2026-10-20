"""Static / generated OOXML parts: styles, numbering, settings, package plumbing."""
from xml.sax.saxutils import escape

HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
      'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"')
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
PAGES = {'a4': (11906, 16838), 'letter': (12240, 15840)}
MARGIN = 1440


def _heading(n, size, color, italic=False):
    return ('<w:style w:type="paragraph" w:styleId="Heading%d"><w:name w:val="heading %d"/><w:basedOn w:val="Normal"/>'
            '<w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/>'
            '<w:spacing w:before="%d" w:after="120"/><w:outlineLvl w:val="%d"/></w:pPr><w:rPr>'
            '<w:rFonts w:ascii="Calibri Light" w:hAnsi="Calibri Light" w:cs="Calibri Light"/>%s<w:color w:val="%s"/>'
            '<w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr></w:style>'
            % (n, n, 360 if n == 1 else 240, n - 1, '<w:i/>' if italic else '', color, size, size))


def styles_xml():
    border = ''.join('<w:%s w:val="single" w:sz="4" w:space="4" w:color="D9D9D9"/>' % s
                     for s in ('top', 'left', 'bottom', 'right'))
    grid = ''.join('<w:%s w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>' % s
                   for s in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
    return (HEAD + '<w:styles %s><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" '
            'w:eastAsia="Calibri" w:cs="Calibri"/><w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="en-US" '
            'w:eastAsia="en-US" w:bidi="ar-SA"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr>'
            '<w:spacing w:after="160" w:line="259" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>' % NS +
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
            '<w:style w:type="character" w:default="1" w:styleId="DefaultParagraphFont"><w:name w:val="Default Paragraph '
            'Font"/><w:uiPriority w:val="1"/><w:semiHidden/><w:unhideWhenUsed/></w:style>'
            '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/>'
            '<w:uiPriority w:val="99"/><w:semiHidden/><w:unhideWhenUsed/><w:tblPr><w:tblInd w:w="0" w:type="dxa"/>'
            '<w:tblCellMar><w:top w:w="0" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/>'
            '<w:right w:w="108" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>'
            '<w:style w:type="numbering" w:default="1" w:styleId="NoList"><w:name w:val="No List"/><w:uiPriority w:val="99"/>'
            '<w:semiHidden/><w:unhideWhenUsed/></w:style>' +
            _heading(1, 32, '2F5496') + _heading(2, 26, '2F5496') + _heading(3, 24, '1F3763') +
            _heading(4, 22, '2F5496', True) + _heading(5, 22, '2F5496') + _heading(6, 22, '1F3763') +
            '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
            '<w:next w:val="Normal"/><w:uiPriority w:val="10"/><w:qFormat/><w:pPr><w:spacing w:after="80" w:line="240" '
            'w:lineRule="auto"/><w:contextualSpacing/></w:pPr><w:rPr><w:rFonts w:ascii="Calibri Light" '
            'w:hAnsi="Calibri Light"/><w:sz w:val="56"/><w:szCs w:val="56"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/>'
            '<w:next w:val="Normal"/><w:uiPriority w:val="11"/><w:qFormat/><w:rPr><w:color w:val="5A5A5A"/>'
            '<w:sz w:val="28"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/>'
            '<w:next w:val="Normal"/><w:uiPriority w:val="29"/><w:qFormat/><w:pPr><w:pBdr><w:left w:val="single" '
            'w:sz="18" w:space="10" w:color="BFBFBF"/></w:pBdr><w:ind w:left="567"/></w:pPr><w:rPr><w:i/><w:iCs/>'
            '<w:color w:val="595959"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/>'
            '<w:uiPriority w:val="30"/><w:qFormat/><w:pPr><w:pBdr>%s</w:pBdr><w:shd w:val="clear" w:color="auto" '
            'w:fill="F5F5F5"/><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:contextualSpacing/></w:pPr>'
            '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:sz w:val="19"/>'
            '<w:szCs w:val="19"/></w:rPr></w:style>' % border +
            '<w:style w:type="character" w:styleId="CodeChar"><w:name w:val="Code Char"/><w:uiPriority w:val="30"/>'
            '<w:qFormat/><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:sz w:val="20"/>'
            '<w:szCs w:val="20"/><w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/></w:rPr></w:style>'
            '<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:uiPriority w:val="99"/>'
            '<w:unhideWhenUsed/><w:rPr><w:color w:val="0563C1"/><w:u w:val="single"/></w:rPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
            '<w:basedOn w:val="Normal"/><w:uiPriority w:val="34"/><w:qFormat/><w:pPr><w:ind w:left="720"/>'
            '<w:contextualSpacing/></w:pPr></w:style>'
            '<w:style w:type="paragraph" w:styleId="FootnoteText"><w:name w:val="footnote text"/>'
            '<w:basedOn w:val="Normal"/><w:uiPriority w:val="99"/><w:unhideWhenUsed/><w:pPr><w:spacing w:after="0" '
            'w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>'
            '<w:style w:type="character" w:styleId="FootnoteReference"><w:name w:val="footnote reference"/>'
            '<w:uiPriority w:val="99"/><w:unhideWhenUsed/><w:rPr><w:vertAlign w:val="superscript"/></w:rPr></w:style>'
            '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:basedOn w:val="TableNormal"/>'
            '<w:uiPriority w:val="39"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
            '<w:tblPr><w:tblBorders>%s</w:tblBorders></w:tblPr><w:tblStylePr w:type="firstRow"><w:rPr><w:b/><w:bCs/></w:rPr>'
            '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="D9E2F3"/></w:tcPr></w:tblStylePr></w:style></w:styles>'
            % grid)


def numbering_xml(nums):
    """abstract 0 = bullets, 1 = decimal-cycling; nums = [(numId, abstractId, ilvl, start)] (+ shared bullet numId 1)."""
    bullets = ('•', '◦', '▪')
    fmts = ('decimal', 'lowerLetter', 'lowerRoman')
    lv_b, lv_d = [], []
    for i in range(9):
        ind = '<w:pPr><w:ind w:left="%d" w:hanging="360"/></w:pPr>' % (720 * (i + 1))
        lv_b.append('<w:lvl w:ilvl="%d"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="%s"/>'
                    '<w:lvlJc w:val="left"/>%s<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:hint="default"/>'
                    '</w:rPr></w:lvl>' % (i, bullets[i % 3], ind))
        lv_d.append('<w:lvl w:ilvl="%d"><w:start w:val="1"/><w:numFmt w:val="%s"/><w:lvlText w:val="%%%d."/>'
                    '<w:lvlJc w:val="left"/>%s</w:lvl>' % (i, fmts[i % 3], i + 1, ind))
    out = [HEAD, '<w:numbering %s>' % NS,
           '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/>%s</w:abstractNum>' % ''.join(lv_b),
           '<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="hybridMultilevel"/>%s</w:abstractNum>' % ''.join(lv_d),
           '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>']
    for nid, ilvl, start in nums:
        out.append('<w:num w:numId="%d"><w:abstractNumId w:val="1"/><w:lvlOverride w:ilvl="%d"><w:startOverride '
                   'w:val="%d"/></w:lvlOverride></w:num>' % (nid, ilvl, start))
    out.append('</w:numbering>')
    return ''.join(out)


def settings_xml(has_footnotes):
    fn = '<w:footnotePr><w:footnote w:id="-1"/><w:footnote w:id="0"/></w:footnotePr>' if has_footnotes else ''
    return (HEAD + '<w:settings %s><w:zoom w:percent="100"/><w:defaultTabStop w:val="720"/>'
            '<w:characterSpacingControl w:val="doNotCompress"/>%s<w:compat><w:compatSetting w:name="compatibilityMode" '
            'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat></w:settings>' % (NS, fn))


def footnotes_xml(notes):
    sep = ('<w:footnote w:type="%s" w:id="%d"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr>'
           '<w:r><w:%s/></w:r></w:p></w:footnote>')
    return (HEAD + '<w:footnotes %s>' % NS + sep % ('separator', -1, 'separator') +
            sep % ('continuationSeparator', 0, 'continuationSeparator') + ''.join(notes) + '</w:footnotes>')


def core_xml(title):
    return (HEAD + '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>%s</dc:title><dc:creator>md2docx</dc:creator>'
            '</cp:coreProperties>' % escape(title))


def content_types(exts, has_footnotes):
    d = ''.join('<Default Extension="%s" ContentType="image/%s"/>' % (e, e) for e in sorted(exts))
    wm = 'application/vnd.openxmlformats-officedocument.wordprocessingml.'
    ov = [('/word/document.xml', wm + 'document.main+xml'), ('/word/styles.xml', wm + 'styles+xml'),
          ('/word/numbering.xml', wm + 'numbering+xml'), ('/word/settings.xml', wm + 'settings+xml'),
          ('/docProps/core.xml', 'application/vnd.openxmlformats-package.core-properties+xml')]
    if has_footnotes:
        ov.append(('/word/footnotes.xml', wm + 'footnotes+xml'))
    return (HEAD + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>%s%s</Types>' % (
                d, ''.join('<Override PartName="%s" ContentType="%s"/>' % o for o in ov)))


def root_rels():
    return (HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="%sofficeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/'
            'core-properties" Target="docProps/core.xml"/></Relationships>' % REL)


def doc_rels(rels):
    """rels: [(id, type_suffix, target, external)]"""
    base = [('rIdS', 'styles', 'styles.xml', False), ('rIdN', 'numbering', 'numbering.xml', False),
            ('rIdT', 'settings', 'settings.xml', False)]
    return (HEAD + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(
        '<Relationship Id="%s" Type="%s%s" Target="%s"%s/>' % (i, REL, t, escape(tg, {'"': '&quot;'}),
                                                               ' TargetMode="External"' if ex else '')
        for i, t, tg, ex in base + list(rels)) + '</Relationships>')
