from pathlib import Path
from typing import List, Optional
from lxml import etree

# Map format/profile to schema files. Extend as needed.
_SCHEMA_MAP = {
    ("ubl", "f1", "base"): "3- XSD_v3.1/2 - E-invoicing/F1_BASE_UBL_2.1/F1BASE_UBL-invoice-2.1.xsd",
    ("ubl", "f1", "full"): "3- XSD_v3.1/2 - E-invoicing/F1_FULL_UBL_2.1/F1FULL_UBL_invoice-2.1.xsd",
    ("creditnote-ubl", "f1", "base"): "3- XSD_v3.1/2 - E-invoicing/F1_BASE_UBL_2.1/F1BASE_UBL-CreditNote-2.1.xsd",
    ("creditnote-ubl", "f1", "full"): "3- XSD_v3.1/2 - E-invoicing/F1_FULL_UBL_2.1/F1FULL_UBL_CreditNote-2.1.xsd",
    ("cii", "f1", "base"): "3- XSD_v3.1/2 - E-invoicing/F1_BASE_CII_D22B/uncefact/data/standard/F1BASE_CrossIndustryInvoice_100pD22B.xsd",
    ("cii", "f1", "full"): "3- XSD_v3.1/2 - E-invoicing/F1_FULL_CII_D22B/uncefact/data/standard/F1FULL_CrossIndustryInvoice_100pD22B.xsd",
    ("cdv", "f6", None): None,
    ("ereporting", None, None): "3- XSD_v3.1/1 - E-reporting/ereporting.xsd",
    ("annuaire", None, None): "3- XSD_v3.1/0 - Annuaire/common/Annuaire_Commun.xsd",
}


class XSDValidator:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._cache = {}

    def _resolve_schema(self, fmt: str, flow: Optional[str], profile: Optional[str]) -> Optional[Path]:
        key = (fmt, flow, profile)
        if key in _SCHEMA_MAP:
            target = _SCHEMA_MAP[key]
            return None if target is None else self.base_dir / target
        # Fallback without flow/profile
        for candidate in [
            (fmt, flow, None),
            (fmt, None, None),
        ]:
            if candidate in _SCHEMA_MAP:
                target = _SCHEMA_MAP[candidate]
                return None if target is None else self.base_dir / target
        return None

    def _get_schema(self, path: Path) -> etree.XMLSchema:
        if path in self._cache:
            return self._cache[path]
        xml = etree.parse(str(path))
        schema = etree.XMLSchema(xml)
        self._cache[path] = schema
        return schema

    def validate(self, xml_content: bytes, fmt: str, flow: Optional[str] = None, profile: Optional[str] = None) -> List[str]:
        errors: List[str] = []
        schema_path = self._resolve_schema(fmt, flow, profile)
        if schema_path is None or not schema_path.exists():
            errors.append(f"No schema found for format={fmt}, flow={flow}, profile={profile}")
            return errors
        try:
            doc = etree.fromstring(xml_content)
            schema = self._get_schema(schema_path)
            schema.assertValid(doc)
        except etree.DocumentInvalid:
            for e in schema.error_log:
                errors.append(str(e))
        except Exception as ex:  # pragma: no cover - unexpected parser errors
            errors.append(str(ex))
        return errors
