# MCP FE Compliance Service

Service FastAPI pour auditer la conformité Facturation Electronique (FR) : validation syntaxique/métier, référentiels (règles/codelists), audit de capacités, et chargement des annexes v3.1.

---

## Service en ligne

Le service est disponible en ligne à l'adresse : **https://femcp.com2nice.fr/**

### API REST
- Documentation Swagger : https://femcp.com2nice.fr/docs
- Endpoints REST disponibles immédiatement (voir section "Détail des endpoints")

### Serveur MCP distant (SSE)
- Endpoint SSE : `https://femcp.com2nice.fr/sse`
- Endpoint messages : `https://femcp.com2nice.fr/messages/`

**Aucune installation requise !** Configurez simplement votre client MCP (Claude Desktop, Cursor, etc.) :

---

## Utilisation comme serveur MCP (Model Context Protocol)

Ce projet expose également un **serveur MCP** permettant aux assistants IA (Claude Desktop, Claude Code, Cursor, etc.) d'utiliser directement les outils de validation et référentiels.

### Utilisation du serveur MCP public (recommandé)

Ajouter dans votre fichier de configuration MCP :
- Claude Desktop : `~/.claude/claude_desktop_config.json` (macOS/Linux) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows)
- Cursor : `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "fe-compliance": {
      "url": "https://femcp.com2nice.fr/sse"
    }
  }
}
```

C'est tout ! Les outils de validation FE sont immédiatement disponibles.

### Mode local (stdio) - optionnel

Si vous préférez héberger le serveur localement :

```json
{
  "mcpServers": {
    "fe-compliance": {
      "command": "python",
      "args": ["/chemin/vers/MCP/mcp_server.py"]
    }
  }
}
```

### Héberger votre propre serveur SSE

```bash
# Cloner le projet
git clone https://github.com/vr0nsky/service-conformite-facturation-electronique.git
cd service-conformite-facturation-electronique

# Installer et lancer
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python mcp_server.py --sse --port 8001
```

### Outils MCP disponibles

| Outil | Description |
|-------|-------------|
| `validate_invoice` | Valide une facture électronique (UBL, CII, Factur-X, CDV, e-reporting, annuaire) |
| `get_codelist` | Récupère une codelist (UNTDID1001, CDV_REFUS, ISO4217, ISO3166, CADRES) |
| `get_required_fields` | Retourne les champs obligatoires (codes BT) pour un profil/flux donné |
| `get_rule` | Détails d'une règle métier (G1.01, G1.05, etc.) |
| `get_refusal_codes` | Liste des codes de refus CDV |
| `get_next_status` | Statuts CDV suivants autorisés depuis un statut donné |
| `audit_capabilities` | Audit des capacités d'une plateforme vs exigences FE |
| `list_available_codelists` | Liste les codelists disponibles |

### Exemple d'utilisation avec un assistant IA

Une fois configuré, vous pouvez demander à l'assistant :

> « Valide cette facture UBL : `<Invoice>...</Invoice>` »

L'assistant appellera automatiquement l'outil `validate_invoice` et vous retournera le rapport de validation (erreurs XSD, violations de règles métier, problèmes de codelists).

---

## Contenu du dépôt MCP
- `app/`: code FastAPI.
  - `main.py`: bootstrap FastAPI, routes.
  - `routers/`: `validate.py`, `audit.py`, `reference.py` (endpoints), `generate.py` (optionnel, absent).
  - `services/`: `xsd_validator.py` (validation XSD), `rules_engine.py` (règles métier/codelists UBL F1).
  - `models/`: modèles Pydantic.
- `data/`: ressources.
  - `xsd/3- XSD_v3.1`: schémas UBL e-invoicing (facture/avoir Base/Full), CII e-invoicing (Base/Full), e-reporting, annuaire. CDV : schéma pivot Chorus Pro `CPPStatutPivot_V1_19.xsd` ajouté sous `data/xsd/cpp/`.
  - `annexes_cache/`: JSON générés depuis les annexes XLSX (formats sémantiques, règles, codelists, motifs de refus).
  - `examples/`: vide (à remplir si besoin).
- `scripts/`: utilitaires.
  - `build_annex_cache.py`: convertit les XLSX en JSON.
  - `run_tests.sh`: lance les tests unittest.
- `tests/`: tests unitaires (`test_validate.py`).
- `mcp_server.py`: serveur MCP stdio exposant les outils (validate_invoice, codelists, required_fields, audit, etc.).
- `requirements.txt`: dépendances Python.
- `docs/mcp-fe-design.md`: design du service.

## Installation
Créer un virtualenv et installer les dépendances :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Génération des caches annexes
Des caches JSON sont fournis dans `data/annexes_cache_embedded/`. Si vous voulez régénérer depuis les annexes XLSX (fournies séparément, ex. dossier `specifications-externes-v3.1/2- Annexes_v3.1` placé à côté du projet) :
```bash
source .venv/bin/activate
python scripts/build_annex_cache.py --src "../specifications-externes-v3.1/2- Annexes_v3.1" --out data/annexes_cache
# ajuster --src selon l’emplacement réel des annexes
```
Les codelists/motifs/champs obligatoires seront chargés automatiquement depuis `data/annexes_cache` si présent, sinon depuis `data/annexes_cache_embedded`.

## Lancement du service
```bash
source .venv/bin/activate
uvicorn app.main:app --reload
# Serveur MCP (stdio) : python mcp_server.py
```
Endpoints disponibles :
- `POST /validate_message`: `{format: ubl|cii|facturx|cdv|ereporting|annuaire, profile: base|full, flow: f1|f6|f10|f13|f14, payload: xml|base64}` → rapport `{syntax[], rules[], codelists[]}`.
- `POST /audit_capabilities`: `{formats, profiles, cdv_statuses, cadres, annuaire, facturx}` → gaps.
- `GET /rules/{id}`, `GET /codelists/{name}`, `GET /required_fields`, `POST /next_status`, `GET /refusal_codes`.

## Règles et validations
- XSD mappés : UBL e-invoicing facture/avoir Base/Full, CII e-invoicing (CrossIndustryInvoice Base/Full), e-reporting, annuaire. CDV : mappé sur le schéma pivot Chorus Pro `CPPStatutPivot_V1_19.xsd` (à remplacer par le flux 6 officiel si disponible).
- Règles métier implémentées (partielles) :
  - UBL F1 : G1.05 (ID facture : longueur/caractères), G1.09 (date AAAA-MM-JJ), G1.01 (code type UNTDID1001 autorisé).
  - CII F1 : ID (G1.05, format/longueur), date AAAAMMJJ (G1.09), type facture (G1.01).
  - E-reporting (minimal) : dates au format AAAAMMJJ pour les éléments *Date*.
  - Annuaire (minimal) : longueurs SIREN/SIRET (9 / 14).
- Codelists/motifs : chargés depuis Annexe 7 (15 codes UNTDID1001, ~40 motifs de refus). Champs obligatoires extraits : F1 Base/Full (Annexe 1), e-reporting F10 (Annexe 6), annuaire F13/F14 (Annexe 3).

## Guide pratique : relier les API à une facture (F1)
1) Choisir le format et le profil : `format=ubl|cii|facturx`, `flow=f1`, `profile=base|full`.
2) Lister les champs obligatoires : `GET /required_fields?profile=base&flow=f1` (ou `full`). Utiliser cette liste de BT pour préparer l'XML.
3) Valider la facture : `POST /validate_message` avec `format`, `flow`, `profile` et `payload` (XML ou base64). Si `format=facturx`, le service extrait l'XML du PDF et valide en CII.
4) Lire le rapport :
   - `syntax[]` : erreurs XSD (structure, cardinalités, types).
   - `rules[]` : règles G1.xx (ID manquant, date au mauvais format, etc.).
   - `codelists[]` : valeurs hors codelist (type UNTDID1001, devise ISO4217, cadre CADRES).
5) Corriger l'XML et rejouer la validation jusqu'à ce que les trois tableaux soient vides.

Autres flux : F10 (e-reporting), F13/F14 (annuaire), F6 (cycle de vie CDV) utilisent les mêmes endpoints mais avec `flow=f10|f13|f14|f6` et leur format dédié (`ereporting`, `annuaire`, `cdv`).

## Détail des endpoints
- `POST /validate_message`
  - Entrée : `format` (ubl|cii|facturx|cdv|ereporting|annuaire), `profile` (base|full si pertinent), `flow` (f1|f6|f10|f13|f14 si pertinent), `payload` XML (string) ou base64 (si ça ne commence pas par `<`, tentative de base64.b64decode).
  - Traitement : décodage, validation XSD (UBL/CII F1, e-reporting, annuaire, CDV avec schéma pivot Chorus Pro). Si `format=facturx`, extraction de l’XML embarqué dans le PDF et validation comme CII. Règles métier appliquées UBL/CII F1 (ID, date, type), issues de codelist séparées.
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
scripts/run_tests.sh
# ou
python -m unittest MCP.tests.test_validate
```

## TODO / Améliorations
- Remplacer le schéma CDV pivot par le flux 6 officiel (si disponible) et affiner `_SCHEMA_MAP`.
- Enrichir `rules_engine` avec plus de règles Gx/BR (lectures des caches annexes) et codelists supplémentaires.
- Exposer d’autres endpoints (génération d’exemples UBL/CII, séquences CDV, annuaire simulé).
- Ajouter des jeux d’exemples dans `data/examples/` et des tests E2E couvrant plus de flux (F6, F10).
- Paramétrer les sévérités (blocant vs warning) et charger dynamiquement les règles depuis les caches plutôt que via des stubs.
