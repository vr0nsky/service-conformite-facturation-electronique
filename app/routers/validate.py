from fastapi import APIRouter, HTTPException
from ..models.schemas import ValidateMessageRequest, ValidationReport
from ..services.xsd_validator import XSDValidator
from ..services import rules_engine
from pathlib import Path
import base64

router = APIRouter()


@router.post("/validate_message", response_model=ValidationReport)
def validate_message(req: ValidateMessageRequest):
    # payload may be raw XML string or base64-encoded
    raw = req.payload
    try:
        if raw.strip().startswith("<"):
            xml_bytes = raw.encode("utf-8")
        else:
            xml_bytes = base64.b64decode(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid payload encoding: {exc}")

    validator = XSDValidator(base_dir=Path(__file__).resolve().parents[2] / "data/xsd")
    syntax_errors = validator.validate(xml_bytes, req.format, req.flow, req.profile)

    rule_issues, codelist_issues = rules_engine.evaluate(xml_bytes, req.format, req.flow)

    return ValidationReport(
        syntax=syntax_errors,
        rules=rule_issues,
        codelists=codelist_issues,
    )
