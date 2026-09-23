import yaml
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from structlog import get_logger

from app.models import ClinicalExtraction, ScrubResult, ScrubStatus, RuleViolation, Severity

logger = get_logger(__name__)

class SHARulesEngine:
    """
    100% deterministic rules engine. 
    Never touches an LLM. Driven purely by the sha_rules.yaml configuration.
    """
    def __init__(self, config_path: str = "app/rules/sha_rules.yaml"):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"SHA Engine: Rules configuration file missing at {config_path}")
            
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
            self.rules = config.get('rules', {})
            logger.info("sha_engine_initialized", loaded_categories=list(self.rules.keys()))

    def _create_violation(self, rule: Dict[str, Any], dynamic_message: Optional[str] = None) -> RuleViolation:
        return RuleViolation(
            rule_id=rule['id'],
            rule_name=rule['name'],
            severity=Severity(rule['severity']),
            message=dynamic_message or rule['message'],
            suggested_fix=rule['fix']
        )

    def scrub(
        self,
        extraction: ClinicalExtraction,
        patient_sha_status: str,
        patient_sha_package: str,
        amount_billed: float,
        encounter_date: datetime,
        encounter_type: str = "outpatient",
        has_preauth: bool = False,
        existing_claims: Optional[List[Dict[str, Any]]] = None
    ) -> ScrubResult:
        """
        Main entrypoint for evaluating all configured rules against a clinical extraction.
        """
        violations: List[RuleViolation] = []
        
        # Evaluators
        violations.extend(self._check_membership(patient_sha_status))
        violations.extend(self._check_preauth(extraction, amount_billed, encounter_type, has_preauth))
        violations.extend(self._check_coding(extraction))
        violations.extend(self._check_evidence(extraction))
        violations.extend(self._check_duplicates(extraction, encounter_date, existing_claims))
        violations.extend(self._check_timeliness(encounter_date))
        # tariff check (Phase 2 proxy implemented here)
        violations.extend(self._check_tariff(extraction, amount_billed))

        # Compile final status based on the severity cascade
        status = ScrubStatus.PASSED
        can_submit = True
        
        if any(v.severity == Severity.BLOCK for v in violations):
            status = ScrubStatus.BLOCKED
            can_submit = False
        elif any(v.severity == Severity.WARNING for v in violations):
            status = ScrubStatus.WARNINGS_ONLY
            can_submit = True

        return ScrubResult(
            status=status,
            violations=violations,
            scrubbed_at=datetime.utcnow(),
            can_submit=can_submit
        )

    def _check_membership(self, sha_status: str) -> List[RuleViolation]:
        violations = []
        for r in self.rules.get('membership', []):
            if r['id'] == 'SHA-R1' and sha_status.upper() != 'ACTIVE':
                violations.append(self._create_violation(r))
        return violations

    def _check_preauth(
        self, 
        extraction: ClinicalExtraction, 
        amount: float, 
        encounter_type: str, 
        has_preauth: bool
    ) -> List[RuleViolation]:
        if has_preauth:
            return [] # skip checks if they already have preauth
            
        violations = []
        for r in self.rules.get('preauth', []):
            applies = r.get('applies_to', {})
            
            # SHA-R2a/b (Procedure categories / pricing)
            cats = applies.get('procedure_categories', [])
            if r['id'] == 'SHA-R2a' or r['id'] == 'SHA-R2b':
                # Since we don't have full CPT dictionaries yet, just matching names loosely in this dummy impl
                # A full impl would map ichi_codes to surgical/imaging.
                is_surgical_or_imaging = any("surgery" in p.name.lower() or "imaging" in p.name.lower() or "x-ray" in p.name.lower() for p in extraction.procedures)
                
                if is_surgical_or_imaging and r['id'] == 'SHA-R2a':
                    violations.append(self._create_violation(r))
                elif is_surgical_or_imaging and r['id'] == 'SHA-R2b' and amount > applies.get('amount_min', 999999):
                    violations.append(self._create_violation(r))
                    
            # SHA-R2c (Inpatient length of stay simulation, usually validated against discharge engine limits)
            if r['id'] == 'SHA-R2c' and encounter_type.lower() == 'inpatient':
                 # In a real system we'd calculate admission time - current time
                 pass
                 
        return violations

    def _check_coding(self, extraction: ClinicalExtraction) -> List[RuleViolation]:
        violations = []
        primary_dx = next((dx for dx in extraction.diagnoses if dx.is_primary), None)
        
        for r in self.rules.get('coding', []):
            if r['id'] == 'SHA-R4':
                if not primary_dx or not primary_dx.icd11_validated:
                    violations.append(self._create_violation(r))
        return violations

    def _check_evidence(self, extraction: ClinicalExtraction) -> List[RuleViolation]:
        violations = []
        # Get all validated ICD prefix substrings up to 4 chars e.g. "BA00.1" -> "BA00"
        dx_prefixes = [dx.icd11_validated[:4] for dx in extraction.diagnoses if dx.icd11_validated]
        loinc_codes = [v.loinc_code for v in extraction.vitals if v.loinc_code] + [l.loinc_code for l in extraction.lab_orders if l.loinc_code]
        
        for r in self.rules.get('clinical_evidence', []):
            trigger_icds = r.get('trigger_icds', [])
            require_loincs = r.get('require_loincs', [])
            require_fields = r.get('require_fields', [])
            
            # Does the patient have the triggered diagnosis?
            if any(dx_prefix in trigger_icds for dx_prefix in dx_prefixes):
                if require_loincs:
                    if not any(loinc in loinc_codes for loinc in require_loincs):
                         violations.append(self._create_violation(r))
                if require_fields:
                    for field in require_fields:
                        if getattr(extraction, field, None) is None:
                             violations.append(self._create_violation(r))
                             
        return violations

    def _check_tariff(self, extraction: ClinicalExtraction, amount: float) -> List[RuleViolation]:
        violations = []
        # Soft proxy implementation for phase 2. 
        # Typically requires matching the tariff gazetted schedule DB table.
        for r in self.rules.get('tariff', []):
            if r['id'] == 'SHA-R6' and amount > 100000: # Simple blanket rule setup
                violations.append(self._create_violation(r))
        return violations

    def _check_duplicates(self, extraction: ClinicalExtraction, encounter_date: datetime, existing_claims: Optional[List[Dict[str, Any]]]) -> List[RuleViolation]:
        if not existing_claims:
            return []
            
        violations = []
        primary_dx = next((dx.icd11_validated for dx in extraction.diagnoses if dx.is_primary), None)
        
        for r in self.rules.get('duplicate', []):
            if r['id'] == 'SHA-R7' and primary_dx:
                for past_claim in existing_claims:
                    past_date = past_claim.get('encounter_date')
                    past_dx = past_claim.get('icd11_primary')
                    if past_dx == primary_dx and past_date and past_date.date() == encounter_date.date():
                        violations.append(self._create_violation(r))
                        break
        return violations

    def _check_timeliness(self, encounter_date: datetime) -> List[RuleViolation]:
        violations = []
        now = datetime.now(timezone.utc)
        
        # Need to ensure encounter dates have timezones to properly check
        if encounter_date.tzinfo is None:
            encounter_date = encounter_date.replace(tzinfo=timezone.utc)
            
        days_passed = (now - encounter_date).days
        
        for r in self.rules.get('timeliness', []):
            if r['id'] == 'SHA-R9':
                if days_passed > r.get('block_threshold_days', 30):
                    violations.append(self._create_violation(r, f"Claim is {days_passed} days old, exceeding 30-day block window."))
                elif days_passed > r.get('warning_threshold_days', 25):
                    v = self._create_violation(r, f"Claim is {days_passed} days old. Approaching 30-day SHA submission deadline.")
                    v.severity = Severity.WARNING
                    violations.append(v)
                    
        return violations
