from fastapi import APIRouter
from ..models.schemas import AuditCapabilitiesRequest, GapSummary

router = APIRouter()

REQUIRED_FORMATS = ["ubl", "cii"]
REQUIRED_PROFILES = ["base", "full"]
REQUIRED_CDV = ["CDV-200", "CDV-202", "CDV-203", "CDV-205", "CDV-211", "CDV-212", "CDV-213", "CDV-220", "CDV-207"]
REQUIRED_CADRES = ["B1", "S1", "M1", "B2", "S2", "M2", "B4", "S4", "M4", "S5", "S6", "B7", "S7"]


@router.post("/audit_capabilities", response_model=GapSummary)
def audit_capabilities(req: AuditCapabilitiesRequest):
    missing_formats = [f for f in REQUIRED_FORMATS if f not in req.formats]
    missing_profiles = [p for p in REQUIRED_PROFILES if p not in req.profiles]
    missing_cdv = [s for s in REQUIRED_CDV if s not in req.cdv_statuses]
    missing_cadres = [c for c in REQUIRED_CADRES if c not in req.cadres]
    notes = []
    if not req.annuaire:
        notes.append("Annuaire non supporté")
    if not req.facturx:
        notes.append("Factur-X non supporté")
    return GapSummary(
        missingFormats=missing_formats,
        missingProfiles=missing_profiles,
        missingCDV=missing_cdv,
        missingCadres=missing_cadres,
        notes=notes,
    )
