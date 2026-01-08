import unittest
from pathlib import Path
from MCP.app.routers.validate import validate_message
from MCP.app.routers.audit import audit_capabilities
from MCP.app.models.schemas import ValidateMessageRequest, AuditCapabilitiesRequest


class MCPValidateTests(unittest.TestCase):
    def test_validate_ubl_invoice_example(self):
        sample = Path(__file__).resolve().parents[2] / "xp_z12-012_annexes_a_v1.2_et_b_exemples_v1.2/XP_Z12-012_Annexes_A_V1.2_et_B_EXEMPLES_V1.2/XP_Z12-012_Annexe_B_EXEMPLES_V1.2/Factures/F202500003/UC1_F202500003_00-INV_20250701_UBL.xml"
        if not sample.exists():
            self.skipTest("Sample UBL file not present")
        payload = sample.read_text(encoding="utf-8")
        req = ValidateMessageRequest(format="ubl", profile="base", flow="f1", payload=payload)
        report = validate_message(req)
        self.assertTrue(hasattr(report, "syntax"))
        self.assertTrue(hasattr(report, "rules"))

    def test_audit_capabilities(self):
        req = AuditCapabilitiesRequest(formats=["ubl"], profiles=["base"], cdv_statuses=["CDV-200"], cadres=["B1"], annuaire=True, facturx=False)
        gaps = audit_capabilities(req)
        self.assertTrue(hasattr(gaps, "missingFormats"))


if __name__ == "__main__":
    unittest.main()
