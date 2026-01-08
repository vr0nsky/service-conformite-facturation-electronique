from pydantic import BaseModel, Field
from typing import List, Optional


class ValidateMessageRequest(BaseModel):
    format: str = Field(..., description="ubl|cii|facturx|cdv|ereporting|annuaire")
    profile: Optional[str] = Field(None, description="base|full where applicable")
    flow: Optional[str] = Field(None, description="f1|f6|f10|f13|f14")
    payload: str = Field(..., description="XML content as string or base64; caller handles encoding")


class RuleIssue(BaseModel):
    ruleId: str
    severity: str
    xpath: Optional[str] = None
    message: str


class ValidationReport(BaseModel):
    syntax: List[str]
    rules: List[RuleIssue]
    codelists: List[RuleIssue]


class AuditCapabilitiesRequest(BaseModel):
    formats: List[str] = []
    profiles: List[str] = []
    cdv_statuses: List[str] = []
    cadres: List[str] = []
    annuaire: bool = False
    facturx: bool = False


class GapSummary(BaseModel):
    missingFormats: List[str]
    missingProfiles: List[str]
    missingCDV: List[str]
    missingCadres: List[str]
    notes: List[str] = []


class NextStatusRequest(BaseModel):
    current: Optional[str] = None
    scenario: Optional[str] = None


class NextStatusResponse(BaseModel):
    allowed: List[str]
