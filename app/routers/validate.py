from fastapi import APIRouter, HTTPException
from ..models.schemas import ValidateMessageRequest, ValidationReport
from ..services.xsd_validator import XSDValidator
from ..services import rules_engine
from pathlib import Path
import base64

router = APIRouter()


def extract_facturx_xml(pdf_bytes: bytes) -> bytes:
    """Very simple extraction: locate embedded XML inside a Factur-X PDF."""
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Payload is not a PDF (missing %PDF header)")
    start = pdf_bytes.find(b"<?xml")
    if start == -1:
        raise ValueError("No embedded XML found in Factur-X payload")
    # Try to cut at the end of CrossIndustryInvoice or Invoice tag to avoid trailing PDF bytes
    end = -1
    for marker in [b"</rsm:CrossIndustryInvoice>", b"</Invoice>"]:
        idx = pdf_bytes.find(marker, start)
        if idx != -1:
            end = idx + len(marker)
            break
    if end == -1:
        end = len(pdf_bytes)
    return pdf_bytes[start:end]


@router.post("/validate_message", response_model=ValidationReport)
def validate_message(req: ValidateMessageRequest):
    # payload may be raw XML string or base64-encoded
    raw = req.payload
    # Accept either raw XML (string) or base64; allow BOM/UTF-8 characters.
    try:
        stripped = raw.strip()
        if stripped.startswith("<") or stripped.startswith("\ufeff<"):
            xml_bytes = stripped.encode("utf-8")
        else:
            xml_bytes = base64.b64decode(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid payload encoding: {exc}")

    fmt_for_schema = req.format
    fmt_for_rules = req.format
    # Handle Factur-X (PDF + embedded XML) by extracting the embedded XML and validating as CII
    if req.format.lower() == "facturx":
        try:
            xml_bytes = extract_facturx_xml(xml_bytes)
            fmt_for_schema = "cii"
            fmt_for_rules = "cii"
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to extract Factur-X XML: {exc}")

    validator = XSDValidator(base_dir=Path(__file__).resolve().parents[2] / "data/xsd")
    syntax_errors = validator.validate(xml_bytes, fmt_for_schema, req.flow, req.profile)

    rule_issues, codelist_issues = rules_engine.evaluate(xml_bytes, fmt_for_rules, req.flow)

    return ValidationReport(
        syntax=syntax_errors,
        rules=rule_issues,
        codelists=codelist_issues,
    )
