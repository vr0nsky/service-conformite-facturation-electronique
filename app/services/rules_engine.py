import re
from typing import List, Tuple
from lxml import etree
from ..models.schemas import RuleIssue
from ..routers import reference


ALLOWED_TYPE_CODES = {entry["code"] for entry in reference.CODELISTS.get("UNTDID1001", [])}
ID_PATTERN = re.compile(r"^[A-Za-z0-9\\s\\-+_/]{1,35}$".replace("\\-", "-"))  # avoid bad range parsing
DATE_PATTERN = re.compile(r"^\\d{4}-\\d{2}-\\d{2}$")


def _text_or_none(root: etree._Element, xpath: str, ns: dict) -> str | None:
    node = root.find(xpath, ns)
    if node is None or node.text is None:
        return None
    return node.text.strip()


def evaluate(xml_content: bytes, fmt: str, flow: str | None = None) -> Tuple[List[RuleIssue], List[RuleIssue]]:
    """Basic business and codelist checks for F1 UBL."""
    if fmt != "ubl" or (flow and flow.lower() != "f1"):
        return [], []

    issues: List[RuleIssue] = []
    codelist_issues: List[RuleIssue] = []
    ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}

    try:
        root = etree.fromstring(xml_content)
    except Exception as exc:
        issues.append(RuleIssue(ruleId="PARSER", severity="error", xpath=None, message=str(exc)))
        return issues, codelist_issues

    # G1.05: Identifiant de facture (longueur + caractères)
    inv_id = _text_or_none(root, ".//cbc:ID", ns)
    if not inv_id:
        issues.append(RuleIssue(ruleId="G1.05", severity="error", xpath=".//cbc:ID", message="Identifiant de facture manquant"))
    elif not ID_PATTERN.match(inv_id):
        issues.append(RuleIssue(ruleId="G1.05", severity="error", xpath=".//cbc:ID", message="Identifiant de facture invalide (caractères ou longueur >35)"))

    # G1.09/G1.07: Date AAAA-MM-JJ
    issue_date = _text_or_none(root, ".//cbc:IssueDate", ns)
    if not issue_date:
        issues.append(RuleIssue(ruleId="G1.09", severity="error", xpath=".//cbc:IssueDate", message="Date d'émission manquante"))
    elif not DATE_PATTERN.match(issue_date):
        issues.append(RuleIssue(ruleId="G1.09", severity="error", xpath=".//cbc:IssueDate", message="Date d'émission non au format AAAA-MM-JJ"))

    # G1.01: Code type facture autorisé
    inv_type = _text_or_none(root, ".//cbc:InvoiceTypeCode", ns)
    if not inv_type:
        issues.append(RuleIssue(ruleId="G1.01", severity="error", xpath=".//cbc:InvoiceTypeCode", message="Code type de facture manquant"))
    elif inv_type not in ALLOWED_TYPE_CODES:
        codelist_issues.append(RuleIssue(ruleId="UNTDID1001", severity="error", xpath=".//cbc:InvoiceTypeCode", message=f"Code {inv_type} non autorisé"))

    return issues, codelist_issues
