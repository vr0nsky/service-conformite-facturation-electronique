# MCP FE Compliance Service Design

## Scope
- Server MCP pour auditer la conformité FE d'un ERP (e-invoicing F1, CDV F6, e-reporting F10, annuaire F13/F14).
- Fournit référentiels (règles, codelists), validation syntaxique/métier, analyse de capacités, helpers de génération minimale.

## API (FastAPI, JSON)
- `POST /validate_message` : `{format: ubl|cii|facturx|cdv|ereporting|annuaire, profile: base|full, flow: f1|f6|f10|f13|f14, payload: base64|url}` → rapport `{syntax[], rules[], codelists[]}` avec `ruleId, severity, xpath, message`.
- `POST /audit_capabilities` : `{formats, profiles, cdv_statuses, cadres, annuaire, facturx}` → gaps `{missingFormats, missingProfiles, missingCDV, missingCadres, notes}`.
- `GET /rules/{id}` (G1.xx, BR-xx) → texte, applicabilité, sévérité, exemples.
- `GET /codelists/{name}` (UNTDID1001/5305/4461/3035, ISO3166/4217/6523, motifs de refus) → codes/labels/notes.
- `GET /required_fields?profile=base|full&flow=f1` → BT/EXT-FR obligatoires + cardinalités.
- `POST /next_status` : `{current, scenario}` → statuts CDV autorisés. `GET /refusal_codes` → motifs acceptés.
- Optionnel : `POST /generate_invoice` (UBL/CII Base/Full minimal), `POST /generate_cdv_sequence`.

## Données embarquées
- `data/annexes_cache/`: JSON dérivés des XLSX (formats sémantiques, règles Gx, codelists, motifs de refus) générés par script.
- `data/xsd/`: XSD v3.1 (e-invoicing UBL/CII Base/Full, CDV, e-reporting, annuaire).
- `data/examples/`: UC1–UC5 XML/PDF pour tests.
- Versioning : clé de version (v3.1, v3.2…) pour recharger les référentiels.

## Modules
- `adapters/excel_loader.py`, `codelists_loader.py`, `examples_loader.py` : transformation XLSX → JSON.
- `services/xsd_validator.py` (lxml/xmllint, cache des schémas), `rules_engine.py` (Gx/BR + codelists), `profiles.py` (Base/Full champs obligatoires), `capabilities.py` (gap analysis), `annuaire.py` (lookup simulé).
- `routers/validate.py`, `audit.py`, `reference.py`, `generate.py` (optionnel).
- `models/schemas.py` (Pydantic requêtes/réponses), `models/domain.py` (RuleResult, ValidationReport, CapabilityGap).

## Build & scripts
- `scripts/build_annex_cache.py` : convertit les annexes XLSX en JSON utilisables par le service.
- `scripts/run_tests.sh` : lance tests unitaires + E2E.

## Tests
- Unitaires : règles critiques (G1.01, G1.02, G1.05/G1.104, G1.09, G1.10), codelists, statuts CDV.
- E2E : validation facture UBL/CII (F1 Base/Full), validation CDV, e-reporting de base, audit_capabilities.

## Décisions/risques
- Sévérité : blocant vs warning pour règles (à paramétrer).
- Performance : prévoir cache XSD et référentiels; batch possible.
- Formats : support UBL/CII et Factur-X (PDF+XML) en lecture; PDF optionnel pour la validation syntaxique.
- Auth : probablement none/local; prévoir token si exposé.
