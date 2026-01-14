import re
from typing import List, Tuple
from lxml import etree
from ..models.schemas import RuleIssue
from ..routers import reference


ALLOWED_TYPE_CODES = {entry["code"] for entry in reference.CODELISTS.get("UNTDID1001", [])}
ALLOWED_CADRES = set(reference.CODELISTS.get("CADRES", []))
ALLOWED_DEV_CODES = None
ID_PATTERN = re.compile(r"^[A-Za-z0-9\s\-+_/]{1,35}$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_COMPACT_PATTERN = re.compile(r"^\d{8}$")


def _text_or_none(root: etree._Element, xpath: str, ns: dict) -> str | None:
    node = root.find(xpath, ns)
    if node is None or node.text is None:
        return None
    return node.text.strip()


def check_ubl_f1(root: etree._Element) -> Tuple[List[RuleIssue], List[RuleIssue]]:
    issues: List[RuleIssue] = []
    codelist_issues: List[RuleIssue] = []
    ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}

    inv_id = _text_or_none(root, ".//cbc:ID", ns)
    if not inv_id:
        issues.append(RuleIssue(ruleId="G1.05", severity="error", xpath=".//cbc:ID", message="Identifiant de facture manquant"))
    elif not ID_PATTERN.match(inv_id):
        issues.append(RuleIssue(ruleId="G1.05", severity="error", xpath=".//cbc:ID", message="Identifiant de facture invalide (caractères ou longueur >35)"))

    issue_date = _text_or_none(root, ".//cbc:IssueDate", ns)
    if not issue_date:
        issues.append(RuleIssue(ruleId="G1.09", severity="error", xpath=".//cbc:IssueDate", message="Date d'émission manquante"))
    elif not DATE_PATTERN.match(issue_date):
        issues.append(RuleIssue(ruleId="G1.09", severity="error", xpath=".//cbc:IssueDate", message="Date d'émission non au format AAAA-MM-JJ"))

    inv_type = _text_or_none(root, ".//cbc:InvoiceTypeCode", ns)
    if not inv_type:
        issues.append(RuleIssue(ruleId="G1.01", severity="error", xpath=".//cbc:InvoiceTypeCode", message="Code type de facture manquant"))
    elif inv_type not in ALLOWED_TYPE_CODES:
        codelist_issues.append(RuleIssue(ruleId="UNTDID1001", severity="error", xpath=".//cbc:InvoiceTypeCode", message=f"Code {inv_type} non autorisé"))

    # Cadre de facturation (G1.02) si présent dans un champ standard (non normatif, mais contrôlable via un attribut)
    cadre = _text_or_none(root, ".//cbc:BuyerReference", ns)
    if cadre and ALLOWED_CADRES and cadre not in ALLOWED_CADRES:
        codelist_issues.append(RuleIssue(ruleId="G1.02", severity="error", xpath=".//cbc:BuyerReference", message=f"Cadre de facturation {cadre} non autorisé"))

    return issues, codelist_issues


def check_cii_f1(root: etree._Element) -> Tuple[List[RuleIssue], List[RuleIssue]]:
    issues: List[RuleIssue] = []
    codelist_issues: List[RuleIssue] = []
    ns = {
        "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
        "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
        "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    }

    inv_id = _text_or_none(root, ".//rsm:ExchangedDocument/ram:ID", ns)
    if not inv_id:
        issues.append(RuleIssue(ruleId="G1.05", severity="error", xpath=".//rsm:ExchangedDocument/ram:ID", message="Identifiant de facture manquant"))
    elif not ID_PATTERN.match(inv_id):
        issues.append(RuleIssue(ruleId="G1.05", severity="error", xpath=".//rsm:ExchangedDocument/ram:ID", message="Identifiant de facture invalide (caractères ou longueur >35)"))

    issue_date = _text_or_none(root, ".//rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString", ns)
    if not issue_date:
        issues.append(RuleIssue(ruleId="G1.09", severity="error", xpath=".//ram:IssueDateTime/udt:DateTimeString", message="Date d'émission manquante"))
    elif not DATE_COMPACT_PATTERN.match(issue_date):
        issues.append(RuleIssue(ruleId="G1.09", severity="error", xpath=".//ram:IssueDateTime/udt:DateTimeString", message="Date d'émission non au format AAAAMMJJ"))

    inv_type = _text_or_none(root, ".//rsm:ExchangedDocument/ram:TypeCode", ns)
    if not inv_type:
        issues.append(RuleIssue(ruleId="G1.01", severity="error", xpath=".//rsm:ExchangedDocument/ram:TypeCode", message="Code type de facture manquant"))
    elif inv_type not in ALLOWED_TYPE_CODES:
        codelist_issues.append(RuleIssue(ruleId="UNTDID1001", severity="error", xpath=".//rsm:ExchangedDocument/ram:TypeCode", message=f"Code {inv_type} non autorisé"))

    return issues, codelist_issues


def evaluate(xml_content: bytes, fmt: str, flow: str | None = None) -> Tuple[List[RuleIssue], List[RuleIssue]]:
    """Apply basic business and codelist checks based on format/flow."""
    fmt = fmt.lower() if fmt else fmt
    flow = flow.lower() if flow else flow

    issues: List[RuleIssue] = []
    codelist_issues: List[RuleIssue] = []

    try:
        root = etree.fromstring(xml_content)
    except Exception as exc:
        issues.append(RuleIssue(ruleId="PARSER", severity="error", xpath=None, message=str(exc)))
        return issues, codelist_issues

    if fmt == "ubl" and flow == "f1":
        return check_ubl_f1(root)
    if fmt == "cii" and flow == "f1":
        return check_cii_f1(root)

    # Minimal generic checks for e-reporting: dates AAAAMMJJ
    if fmt == "ereporting":
        issues = []
        for elem in root.iter():
            lname = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""
            if "Date" in lname or "date" in lname:
                txt = (elem.text or "").strip()
                if txt and not DATE_COMPACT_PATTERN.match(txt):
                    issues.append(RuleIssue(ruleId="G1.09", severity="error", xpath=f".//{elem.tag}", message="Date non au format AAAAMMJJ"))
        return issues, codelist_issues

    # Minimal generic checks pour l'annuaire : SIREN/SIRET longueurs
    if fmt == "annuaire":
        issues = []
        for elem in root.iter():
            lname = etree.QName(elem.tag).localname if isinstance(elem.tag, str) else ""
            txt = (elem.text or "").strip()
            if not txt:
                continue
            if lname.upper() == "SIREN" and len(txt) != 9:
                issues.append(RuleIssue(ruleId="ANN-SIREN", severity="error", xpath=f".//{elem.tag}", message="SIREN doit contenir 9 chiffres"))
            if lname.upper() == "SIRET" and len(txt) != 14:
                issues.append(RuleIssue(ruleId="ANN-SIRET", severity="error", xpath=f".//{elem.tag}", message="SIRET doit contenir 14 chiffres"))
        return issues, codelist_issues

    return issues, codelist_issues
