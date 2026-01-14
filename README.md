# MCP FE Compliance Service

Service FastAPI pour auditer la conformité Facturation Electronique (FR) : validation syntaxique/métier, référentiels (règles/codelists), audit de capacités, et chargement des annexes v3.1.

## Contenu du dépôt MCP
- `app/`: code FastAPI.
  - `main.py`: bootstrap FastAPI, routes.
  - `routers/`: `validate.py`, `audit.py`, `reference.py` (endpoints), `generate.py` (optionnel, absent).
  - `services/`: `xsd_validator.py` (validation XSD), `rules_engine.py` (règles métier/codelists UBL F1).
  - `models/`: modèles Pydantic.
- `data/`: ressources.
  - `xsd/3- XSD_v3.1`: schémas UBL e-invoicing (facture/avoir Base/Full), CII e-invoicing (Base/Full), e-reporting, annuaire. Pas de CDV dans le bundle actuel.
  - `annexes_cache/`: JSON générés depuis les annexes XLSX (formats sémantiques, règles, codelists, motifs de refus).
  - `examples/`: vide (à remplir si besoin).
- `scripts/`: utilitaires.
  - `build_annex_cache.py`: convertit les XLSX en JSON.
  - `run_tests.sh`: lance les tests unittest.
- `tests/`: tests unitaires (`test_validate_ubl.py`).
- `requirements.txt`: dépendances Python.
- `docs/mcp-fe-design.md`: design du service.

## Installation
Créer un virtualenv et installer les dépendances :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r MCP/requirements.txt
```

## Génération des caches annexes
Nécessite les annexes XLSX (déjà présentes sous `specifications-externes-v3.1/2- Annexes_v3.1`).
```bash
source .venv/bin/activate
python MCP/scripts/build_annex_cache.py --src "specifications-externes-v3.1/2- Annexes_v3.1" --out MCP/data/annexes_cache
```
Les codelists/motifs/champs obligatoires seront chargés automatiquement depuis ces JSON.

## Lancement du service
```bash
source .venv/bin/activate
uvicorn MCP.app.main:app --reload
```
Endpoints disponibles :
- `POST /validate_message`: `{format: ubl|cii|facturx|cdv|ereporting|annuaire, profile: base|full, flow: f1|f6|f10|f13|f14, payload: xml|base64}` → rapport `{syntax[], rules[], codelists[]}`.
- `POST /audit_capabilities`: `{formats, profiles, cdv_statuses, cadres, annuaire, facturx}` → gaps.
- `GET /rules/{id}`, `GET /codelists/{name}`, `GET /required_fields`, `POST /next_status`, `GET /refusal_codes`.

## Règles et validations
- XSD mappés : UBL e-invoicing facture/avoir Base/Full, CII e-invoicing (CrossIndustryInvoice Base/Full), e-reporting, annuaire. CDV : non mappé (XSD absent dans le bundle).
- Règles métier implémentées (UBL F1) :
  - G1.05 (ID facture : longueur/caractères), G1.09 (date AAAA-MM-JJ), G1.01 (code type UNTDID1001 autorisé).
- Codelists/motifs : chargés depuis Annexe 7 (15 codes UNTDID1001, ~40 motifs de refus). Champs obligatoires extraits : F1 Base/Full (Annexe 1), e-reporting F10 (Annexe 6), annuaire F13/F14 (Annexe 3).

## Détail des endpoints
- `POST /validate_message`
  - Entrée : `format` (ubl|cii|facturx|cdv|ereporting|annuaire), `profile` (base|full si pertinent), `flow` (f1|f6|f10|f13|f14 si pertinent), `payload` XML (string) ou base64 (si ça ne commence pas par `<`, tentative de base64.b64decode).
  - Traitement : décodage, validation XSD (UBL/CII F1, e-reporting, annuaire ; CDV non mappé → “No schema found…”), règles UBL/F1 (ID G1.05, date G1.09, type G1.01 via UNTDID1001), issues de codelist séparées.
  - Réponse : `{ "syntax": [...], "rules": [ {ruleId, severity, xpath, message} ], "codelists": [...] }`.
- `POST /audit_capabilities`
  - Entrée : `{formats, profiles, cdv_statuses, cadres, annuaire, facturx}`.
  - Exigences internes : formats `ubl, cii`; profils `base, full`; statuts CDV `CDV-200,202,203,205,207,211,212,213,220`; cadres `B1,S1,M1,B2,S2,M2,B4,S4,M4,S5,S6,B7,S7`.
  - Retour : `{missingFormats, missingProfiles, missingCDV, missingCadres, notes}`.
- `GET /rules/{id}` : stub de règles (G1.01, G1.02, G1.05) → 404 sinon.
- `GET /codelists/{name}` : codelists depuis caches (ex. UNTDID1001, CDV_REFUS) ou 404 si inconnu.
- `GET /required_fields?profile=base|full&flow=f1` : BT obligatoires (Annexe 1).
- `POST /next_status` : `{current, scenario?}` → statuts CDV autorisés (stub transitions : None→200→202→203/213→205/207→211→212).
- `GET /refusal_codes` : motifs de refus (env. 40 codes depuis Annexe 7).

## Utilisation par un AI
- Validation : `/validate_message` sur les XML ERP → corriger les erreurs XSD/règles/codelists, revalider.
- Audit : `/audit_capabilities` → lire les gaps (formats/profils/statuts/cadres) et générer la todo.
- Référentiels : `/codelists/{name}` et `/required_fields` pour alimenter DTO/contrôles ; `/next_status` pour guider les enchaînements CDV.

## Tests
Tests unitaires (sans dépendance httpx) :
```bash
source .venv/bin/activate
MCP/scripts/run_tests.sh
# ou
python -m unittest MCP.tests.test_validate_ubl
```

## TODO / Améliorations
- Ajouter les XSD CII et CDV si disponibles, étendre `_SCHEMA_MAP`.
- Enrichir `rules_engine` avec plus de règles Gx/BR (lectures des caches annexes) et codelists supplémentaires.
- Exposer d’autres endpoints (génération d’exemples UBL/CII, séquences CDV, annuaire simulé).
- Ajouter des jeux d’exemples dans `data/examples/` et des tests E2E couvrant plus de flux (F6, F10).
- Paramétrer les sévérités (blocant vs warning) et charger dynamiquement les règles depuis les caches plutôt que via des stubs.
