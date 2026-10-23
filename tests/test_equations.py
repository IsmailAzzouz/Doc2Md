"""Equations in every supported container share rendering and diagnostics."""
import pytest

from doctomd import convert_bytes


EQUATION = '<m:oMath><m:r><m:t>x+1</m:t></m:r></m:oMath>'
DISPLAY_EQUATION = '<m:oMathPara>' + EQUATION + '</m:oMathPara>'


@pytest.mark.parametrize('body', [
    DISPLAY_EQUATION,
    EQUATION,
    '<w:p>' + DISPLAY_EQUATION + '</w:p>',
    '<w:sdt><w:sdtContent>' + DISPLAY_EQUATION + '</w:sdtContent></w:sdt>',
    '<w:tbl><w:tr><w:tc>' + DISPLAY_EQUATION + '</w:tc></w:tr></w:tbl>',
])
def test_display_equations_survive_block_containers(docx_factory, body):
    result = convert_bytes(docx_factory(
        '<w:p><w:r><w:t>Before</w:t></w:r></w:p>' + body +
        '<w:p><w:r><w:t>After</w:t></w:r></w:p>'
    ))
    assert result.markdown == 'Before\n\n$$\nx+1\n$$\n\nAfter\n'
    assert result.report.warnings == []
    assert result.report.percent == 100


def test_inline_equation_stays_inline(docx_factory):
    result = convert_bytes(docx_factory(
        '<w:p><w:r><w:t>Before </w:t></w:r>' + EQUATION +
        '<w:r><w:t> after.</w:t></w:r></w:p>'
    ))
    assert result.markdown == 'Before $x+1$ after.\n'


def test_multiple_display_equations_keep_separation(docx_factory):
    result = convert_bytes(docx_factory('<m:oMathPara>' + EQUATION * 2 + '</m:oMathPara>'))
    assert result.markdown == '$$\nx+1 \\\\\nx+1\n$$\n'


@pytest.mark.parametrize('display', [False, True])
def test_unsupported_math_preserves_text_and_reports_approximation(docx_factory, display):
    equation = '<m:oMath><m:phant><m:e><m:r><m:t>x</m:t></m:r></m:e></m:phant></m:oMath>'
    body = '<m:oMathPara>' + equation + '</m:oMathPara>' if display else '<w:p>' + equation + '</w:p>'
    result = convert_bytes(docx_factory(body))
    assert 'x' in result.markdown
    assert result.report.percent == 50
    assert result.report.warnings[0].code == 'unsupported-math'
    assert 'phant' in result.report.warnings[0].message


def test_unconvertible_math_has_a_placeholder(docx_factory):
    result = convert_bytes(docx_factory('<m:oMath><m:unknown/></m:oMath>'))
    assert 'Equation could not be converted' in result.markdown
    assert result.report.percent == 0


def test_common_fraction_does_not_trigger_unsupported_warning(docx_factory):
    result = convert_bytes(docx_factory(
        '<m:oMath><m:f><m:fPr><m:type m:val="bar"/></m:fPr>'
        '<m:num><m:r><m:t>a</m:t></m:r></m:num>'
        '<m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></m:oMath>'
    ))
    assert '\\frac{a}{b}' in result.markdown
    assert result.report.warnings == []
