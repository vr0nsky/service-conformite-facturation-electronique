from fastapi import APIRouter, HTTPException
from typing import Dict, List
from pathlib import Path
import json

router = APIRouter()

RULES: Dict[str, Dict] = {}

CODELISTS: Dict[str, List[Dict]] = {}

REQUIRED_FIELDS = {
    ("base", "f1"): ["BT-1", "BT-2", "BT-3", "BT-5", "BT-27", "BT-44"],
    ("full", "f1"): ["BT-1", "BT-2", "BT-3", "BT-5", "BT-27", "BT-44"],
}

NEXT_STATUS_MAP = {
    None: ["CDV-200"],
    "CDV-200": ["CDV-202"],
    "CDV-202": ["CDV-203", "CDV-213"],
    "CDV-203": ["CDV-205", "CDV-207"],
    "CDV-205": ["CDV-211"],
    "CDV-211": ["CDV-212"],
}


def _load_caches():
    """Load codelists from annex cache if available; fall back to embedded defaults."""
    base = Path(__file__).resolve().parents[2] / "data/annexes_cache"
    embedded = Path(__file__).resolve().parents[2] / "data/annexes_cache_embedded"
    defaults = {
        "UNTDID1001": [
            {"code": "380", "label": "Facture"},
            {"code": "381", "label": "Avoir"},
            {"code": "384", "label": "Facture rectificative"},
            {"code": "389", "label": "Facture auto-facturée"},
            {"code": "393", "label": "Facture affacturée"},
            {"code": "501", "label": "Facture auto-facturée affacturée"},
            {"code": "386", "label": "Facture d'acompte"},
            {"code": "500", "label": "Facture d’acompte auto-facturée"},
            {"code": "471", "label": "Facture rectificative auto-facturée"},
            {"code": "472", "label": "Facture rectificative affacturée"},
            {"code": "473", "label": "Facture rectificative auto-facturée affacturée"},
            {"code": "261", "label": "Avoir auto-facturé"},
            {"code": "396", "label": "Avoir affacturé"},
            {"code": "502", "label": "Avoir auto-facturé affacturé"},
            {"code": "503", "label": "Avoir de facture d'acompte"},
        ],
        "CDV_REFUS": [
            {"code": "DEST_ERR", "label": "Erreur de destinataire"},
            {"code": "DOUBLE_FACT", "label": "Données réglementaire F1 en doublon"},
            {"code": "JUSTIF_ABS", "label": "Justificatif absent ou insuffisant"},
            {"code": "ERR_VALIDEUR", "label": "Mauvais valideur"},
            {"code": "CMD_EJ_ERR", "label": "Commande/Engagement incorrect ou manquant"},
        ],
        "CADRES": ["B1", "S1", "M1", "B2", "S2", "M2", "B4", "S4", "M4", "S5", "S6", "B7", "S7"],
    }
    if base.exists():
        cache_base = base
    elif embedded.exists():
        cache_base = embedded
    else:
        CODELISTS.update(defaults)
        return
    # Motifs de refus depuis l'annexe 7 si présent
    motifs_path = cache_base / "20251031_Annexe 7 - Règles de gestion - V1.8.json"
    if motifs_path.exists():
        try:
            data = json.loads(motifs_path.read_text(encoding="utf-8"))
            sheet = data.get("Tableau des motifs de refus", [])
            if sheet and len(sheet) > 1:
                header = sheet[0]
                codes = []
                for row in sheet[1:]:
                    if not row or len(row) < 2:
                        continue
                    code = row[0]
                    label = row[1]
                    if code:
                        codes.append({"code": str(code), "label": label or ""})
                if codes:
                    defaults["CDV_REFUS"] = codes
        except Exception:
            pass
    CODELISTS.update(defaults)

    # Rules from Annexe 7 - Règles de gestion
    rules_path = base / "20251031_Annexe 7 - Règles de gestion - V1.8.json"
    flows_map = {3: "f1", 4: "f6", 5: "f10", 6: "f13", 7: "f14"}
    if rules_path.exists():
        try:
            data = json.loads(rules_path.read_text(encoding="utf-8"))
            sheet = data.get("Règles de gestion", [])
            for row in sheet[2:]:
                if not row or len(row) < 2:
                    continue
                rid = row[1]
                title = row[0]
                label = row[2] if len(row) > 2 else ""
                if not rid or not isinstance(rid, str):
                    continue
                flows = []
                for idx, f in flows_map.items():
                    if len(row) > idx and row[idx] == "X":
                        flows.append(f)
                RULES[rid] = {"title": title or "", "description": label or "", "flows": flows, "severity": "error"}
        except Exception:
            pass

    # Required fields from Annexe 6 (e-reporting)
    annex6 = cache_base / "20251031_Annexe 6 - Format sémantique FE e-reporting - V1.9.json"
    if annex6.exists():
        try:
            data = json.loads(annex6.read_text(encoding="utf-8"))
            sheet = data.get("E-REPORTING - Flux 10", [])
            req = []
            for row in sheet:
                if not row or len(row) < 2:
                    continue
                bt = row[0]
                card = str(row[1]).strip() if row[1] is not None else ""
                if bt and isinstance(bt, str) and card.startswith("1.."):
                    req.append(bt)
            if req:
                REQUIRED_FIELDS[("base", "f10")] = req
                REQUIRED_FIELDS[("full", "f10")] = req
        except Exception:
            pass

    # Required fields from Annexe 3 (annuaire)
    annex3 = cache_base / "20251031_Annexe 3 - Format sémantique FE annuaire - V1.7.json"
    if annex3.exists():
        try:
            data = json.loads(annex3.read_text(encoding="utf-8"))
            for sheet_name, flow in [("FE - F13 (Actualisation)", "f13"), ("FE - F14 (Consultation)", "f14")]:
                sheet = data.get(sheet_name, [])
                req = []
                for row in sheet:
                    if not row or len(row) < 2:
                        continue
                    bt = row[0]
                    card = str(row[1]).strip() if row[1] is not None else ""
                    if bt and isinstance(bt, str) and card.startswith("1.."):
                        req.append(bt)
                if req:
                    REQUIRED_FIELDS[("base", flow)] = req
                    REQUIRED_FIELDS[("full", flow)] = req
        except Exception:
            pass

    # Required fields from Annexe 1 (FE - Flux 1 - UBL)
    annex1 = cache_base / "20251031_Annexe 1 - Format sémantique FE e-invoicing - Flux 1 v1.1.json"
    if annex1.exists():
        try:
            data = json.loads(annex1.read_text(encoding="utf-8"))
            sheet = data.get("FE - Flux 1 - UBL", [])
            req_base = []
            req_full = []
            for row in sheet:
                if not row or len(row) < 2:
                    continue
                bt = row[0]
                card = str(row[1]).strip() if row[1] is not None else ""
                base_flag = row[17] if len(row) > 17 else None
                full_flag = row[18] if len(row) > 18 else None
                if not bt or not isinstance(bt, str):
                    continue
                if card.startswith("1.."):  # obligatoire
                    if base_flag == "X":
                        req_base.append(bt)
                    if full_flag == "X":
                        req_full.append(bt)
            if req_base:
                REQUIRED_FIELDS[("base", "f1")] = req_base
            if req_full:
                REQUIRED_FIELDS[("full", "f1")] = req_full
        except Exception:
            pass

    # Extract ISO codes from EN16931 Codelists (best-effort)
    codelists_sheet = cache_base / "20251031_Annexe 7 - Règles de gestion - V1.8.json"
    if codelists_sheet.exists():
        try:
            data = json.loads(codelists_sheet.read_text(encoding="utf-8"))
            rows = data.get("EN16931 Codelists", [])
            iso4217 = []
            iso3166 = []
            for row in rows:
                if not row or len(row) < 24:
                    continue
                # Currency code sometimes in col 23, country alpha2 in col 16/17, country name in 19/20.
                currency_code = row[23]
                if currency_code and isinstance(currency_code, str) and len(currency_code.strip()) == 3:
                    iso4217.append({"code": currency_code.strip(), "label": str(row[20] if len(row) > 20 else "")})
                country_alpha2 = row[16] if len(row) > 16 else None
                if country_alpha2 and isinstance(country_alpha2, str) and len(country_alpha2.strip()) == 2:
                    iso3166.append({"code": country_alpha2.strip(), "label": str(row[19] if len(row) > 19 else "")})
            if iso4217:
                CODELISTS["ISO4217"] = iso4217
            if iso3166:
                CODELISTS["ISO3166"] = iso3166
        except Exception:
            pass


_load_caches()


@router.get("/rules/{rule_id}")
def get_rule(rule_id: str):
    if rule_id not in RULES:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"id": rule_id, **RULES[rule_id]}


@router.get("/codelists/{name}")
def get_codelist(name: str):
    if name not in CODELISTS:
        raise HTTPException(status_code=404, detail="Codelist not found")
    return CODELISTS[name]


@router.get("/required_fields")
def get_required_fields(profile: str, flow: str):
    key = (profile, flow)
    if key not in REQUIRED_FIELDS:
        raise HTTPException(status_code=404, detail="No required fields for profile/flow")
    return REQUIRED_FIELDS[key]


@router.get("/refusal_codes")
def refusal_codes():
    return CODELISTS.get("CDV_REFUS", [])


@router.post("/next_status")
def next_status(payload: Dict):
    current = payload.get("current")
    allowed = NEXT_STATUS_MAP.get(current, [])
    return {"allowed": allowed}
