import json
import io
from datetime import datetime
from typing import Dict, Any
from openai import AsyncOpenAI, APIError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from structlog import get_logger

from app.models import DischargeSummary, Medication, Procedure
from app.config import get_settings
from app.adapters.qafya_adapter import QAfyaAdapter

logger = get_logger(__name__)
settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """
You are a Senior Physician at Mary Help of the Sick Mission Hospital in Thika, Kenya.
Your primary duty is to synthesize complex inpatient records into a concise, professional, and COMPLETE "Discharge Summary and Clinical Abstract Sheet".

CRITICAL INSTRUCTIONS:
1. FINAL DIAGNOSIS: MUST be explicitly stated. If not found, synthesize the most likely diagnosis from the chief complaint and hospital course. Never return "Unknown".
2. CLINICAL SUMMARY: This is the most important section. Synthesize a coherent narrative combining the History of Present Illness (HPI) and the Hospital Course. Describe the clinical progression, major interventions, and response to treatment.
3. LAB INVESTIGATIONS: List the most relevant laboratory and imaging results. Include baseline and trend values (e.g., "Hb improved from 8.2 to 10.5 g/dL").
4. DISCHARGE PRESCRIPTION: Provide a formatted list of all medications the patient should take at home, including Dose, Frequency, and Duration.
5. RECOMMENDATIONS: Be specific about the follow-up plan (which clinic, when) and "RED FLAGS" (specific symptoms for which the patient must return immediately).

JSON SCHEMA REQUIREMENTS:
- age, sex, ward: Strings.
- attending_doctors: List lead clinicians as a comma-separated string.
- final_diagnosis: A clear, concise clinical diagnosis.
- other_illness: Secondary diagnoses or comorbidities.
- complications: Any adverse events during stay.
- history_of_present_illness: The 'why' and 'how' they arrived.
- hospital_course: The 'what happened' during the stay.
- key_investigations: List of {name, value}.
- discharge_medications: List of {name, dose, frequency, duration, is_new}.
- follow_up_plan: Specific clinic and timing.
- red_flags: List of urgent symptoms.
- condition_at_discharge: Overall status (e.g., Stable).

If data is missing, use your clinical judgment to infer a reasonable professional placeholder based on the context, but NEVER leave clinical sections empty.
"""

PDF_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<style>
    body {{ font-family: 'Times New Roman', serif; margin: 30px; color: #000; font-size: 11pt; line-height: 1.4; }}
    .header {{ text-align: center; margin-bottom: 20px; font-weight: bold; border-bottom: 1px solid #000; padding-bottom: 10px; }}
    .hospital-name {{ font-size: 16pt; }}
    .motto {{ text-decoration: underline; font-style: italic; margin: 5px 0; }}
    .address {{ font-size: 9pt; font-weight: normal; }}
    
    .title-row {{ display: flex; justify-content: space-between; align-items: baseline; margin: 15px 0; font-weight: bold; }}
    .title {{ text-decoration: underline; font-size: 11pt; }}
    
    .field-row {{ margin-bottom: 8px; display: flex; width: 100%; }}
    .field-label {{ font-weight: normal; margin-right: 5px; white-space: nowrap; }}
    .field-value {{ border-bottom: 1px dotted #444; flex-grow: 1; padding-left: 5px; min-height: 1.2em; }}
    
    .grid-row {{ display: flex; gap: 20px; margin-bottom: 8px; }}
    .grid-item {{ flex: 1; display: flex; }}
    
    .section-header {{ font-weight: bold; text-decoration: underline; margin: 15px 0 5px 0; font-size: 11pt; }}
    .section-content {{ min-height: 100px; line-height: 1.8; background-image: linear-gradient(#eee 1px, transparent 1px); background-size: 100% 1.8em; }}
    
    .footer-table {{ width: 100%; margin-top: 50px; border: none; }}
    .footer-table td {{ border: none; padding: 0 10px; text-align: left; vertical-align: top; }}
    .signature-line {{ border-top: 1px solid #000; margin-top: 30px; padding-top: 5px; font-size: 9pt; font-weight: bold; text-align: center; }}
    
    @media print {{
        body {{ margin: 0; }}
        .section-content {{ background-image: linear-gradient(#ccc 1px, transparent 1px); }}
    }}
</style>
</head>
<body>
    <div class="header">
        <div class="hospital-name">MARY HELP OF THE SICK MISSION HOSPITAL</div>
        <div class="motto">MOTTO: YOUR HEALTH, OUR CONCERN</div>
        <div class="address">
            P.O. BOX 792 - 01000, THIKA - KENYA<br>
            TELEPHONE: 020 800 8257/ MOBILE 0724 936 177/ EMAIL: info@maryhelphospital.org
        </div>
    </div>

    <div class="title-row">
        <div class="title">DISCHARGE SUMMARY AND CLINICAL ABSTRACT SHEET</div>
        <div>IP NO: <span style="text-decoration: underline;">{ip_no}</span></div>
    </div>

    <div class="grid-row">
        <div class="grid-item" style="flex: 2;">
            <span class="field-label">SURNAME:</span>
            <span class="field-value">{surname}</span>
        </div>
        <div class="grid-item" style="flex: 3;">
            <span class="field-label">OTHER NAMES:</span>
            <span class="field-value">{other_names}</span>
        </div>
    </div>

    <div class="grid-row">
        <div class="grid-item" style="flex: 1;">
            <span class="field-label">AGE:</span>
            <span class="field-value">{age}</span>
        </div>
        <div class="grid-item" style="flex: 1;">
            <span class="field-label">SEX:</span>
            <span class="field-value">{sex}</span>
        </div>
        <div class="grid-item" style="flex: 2;">
            <span class="field-label">WARD:</span>
            <span class="field-value">{ward}</span>
        </div>
    </div>

    <div class="grid-row">
        <div class="grid-item">
            <span class="field-label">D.O.A:</span>
            <span class="field-value">{admission_date}</span>
        </div>
        <div class="grid-item">
            <span class="field-label">D.O.D:</span>
            <span class="field-value">{discharge_date}</span>
        </div>
    </div>

    <div class="field-row">
        <span class="field-label">ATTENDING DOCTORS:</span>
        <span class="field-value">{attending_doctors}</span>
    </div>

    <div class="field-row">
        <span class="field-label">FINAL DIAGNOSIS:</span>
        <span class="field-value">{final_diagnosis}</span>
    </div>

    <div class="field-row">
        <span class="field-label">OTHER ILLNESS:</span>
        <span class="field-value">{other_illness}</span>
    </div>

    <div class="field-row">
        <span class="field-label">COMPLICATIONS:</span>
        <span class="field-value">{complications}</span>
    </div>

    <div class="field-row">
        <span class="field-label">OPERATIONS 1.</span>
        <span class="field-value">{operation_1}</span>
    </div>
    <div class="field-row">
        <span class="field-label" style="opacity: 0;">OPERATIONS</span>
        <span class="field-label">2.</span>
        <span class="field-value">{operation_2}</span>
    </div>

    <div class="section-header">CLINICAL SUMMARY</div>
    <div class="section-content">{clinical_summary}</div>

    <div class="section-header">LAB INVESTIGATIONS</div>
    <div class="section-content">{lab_investigations}</div>

    <div class="section-header">DISCHARGE PRESCRIPTION</div>
    <div class="section-content">{discharge_prescription}</div>

    <div class="section-header">FURTHER INSTRUCTIONS / RECOMMENDATIONS</div>
    <div class="section-content">{recommendations}</div>

    <table class="footer-table">
        <tr>
            <td>
                <div class="signature-line">DOCTOR'S NAME</div>
                <div style="text-align: center; margin-top: 10px;">{doctor_name}</div>
            </td>
            <td>
                <div class="signature-line">DOCTOR'S SIGNATURE</div>
            </td>
            <td>
                <div class="signature-line">DATE</div>
                <div style="text-align: center; margin-top: 10px;">{current_date}</div>
            </td>
        </tr>
    </table>
    
    <div class="field-row" style="margin-top: 20px;">
        <span class="field-label">QUALIFICATION:</span>
        <span class="field-value">{qualification}</span>
    </div>

    <div style="font-size: 7pt; color: #888; text-align: center; margin-top: 30px;">
        Synthesized by Aifya Health Platform | Document ID: {doc_id}
    </div>
</body>
</html>
"""


class DischargeEngineException(Exception):
    pass


class DischargeEngine:
    def __init__(self, qafya: QAfyaAdapter):
        self.qafya = qafya

    async def _gather_context(self, admission_id: str, patient_id: str) -> Dict[str, Any]:
        patient = await self.qafya.get_patient(patient_id)
        if not patient:
            raise DischargeEngineException("Patient not found in EMR")

        # Use the canonical internal ID (national_id) for subsequent lookups
        internal_id = patient.get("national_id", patient_id)
        encounters = await self.qafya.get_patient_encounters(internal_id)
        admission_encounters = [e for e in encounters if e.get("admission_id") == admission_id]

        if not admission_encounters:
            raise DischargeEngineException("No encounters found for this admission ID")

        admission_encounters.sort(key=lambda x: x.get("encounter_date", datetime.min))

        all_labs = []
        all_meds = []
        for e in admission_encounters:
            enc_id = e["encounter_id"]
            labs = await self.qafya.get_encounter_labs(enc_id)
            meds = await self.qafya.get_encounter_medications(enc_id)
            all_labs.extend(labs)
            all_meds.extend(meds)

        return {
            "patient": patient,
            "encounters": admission_encounters,
            "labs": all_labs,
            "medications": all_meds,
        }

    @retry(
        retry=retry_if_exception_type((APIError, APIConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _synthesize_llm(self, context: Dict[str, Any]) -> str:
        context_str = json.dumps(context, default=str)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context_str},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=45.0,
        )
        return response.choices[0].message.content

    def _structure_summary(self, raw_json: str, context: Dict[str, Any], admission_id: str) -> DischargeSummary:
        parsed = json.loads(raw_json)
        encounters = context["encounters"]
        patient = context["patient"]

        admission_date = encounters[0].get("encounter_date", datetime.utcnow())
        discharge_date = encounters[-1].get("encounter_date", datetime.utcnow())
        los_days = max(1, (discharge_date - admission_date).days)

        def to_str(val) -> str:
            if val is None: return ""
            if isinstance(val, list): return ", ".join(map(str, val))
            return str(val)

        return DischargeSummary(
            patient_name=patient.get("full_name", "Unknown"),
            sha_member_no=patient.get("insurance_no", "Unknown"),
            admission_date=admission_date,
            discharge_date=discharge_date,
            length_of_stay_days=los_days,
            admission_diagnosis=to_str(parsed.get("admission_diagnosis", "Unknown")),
            final_diagnosis=to_str(parsed.get("final_diagnosis", "Unknown")),
            
            # Facility fields mapping
            age=to_str(parsed.get("age", "")),
            sex=to_str(parsed.get("sex", "")),
            ward=to_str(parsed.get("ward", "")),
            ip_no=admission_id,
            attending_doctors=to_str(parsed.get("attending_doctors", "")),
            other_illness=to_str(parsed.get("other_illness", "")),
            complications=to_str(parsed.get("complications", "")),
            doctor_qualification=to_str(parsed.get("doctor_qualification", "MBChB")),

            history_of_present_illness=to_str(parsed.get("history_of_present_illness", parsed.get("brief_history", ""))),
            hospital_course=to_str(parsed.get("hospital_course", "")),
            clinical_narrative=to_str(parsed.get("clinical_narrative", "")), # Fallback
            procedures=[Procedure(**p) for p in parsed.get("procedures", [])],
            key_investigations=parsed.get("key_investigations", []),
            discharge_medications=[Medication(**m) for m in parsed.get("discharge_medications", [])],
            condition_at_discharge=to_str(parsed.get("condition_at_discharge", "")),
            follow_up_plan=to_str(parsed.get("follow_up_plan", "")),
            red_flags=to_str(parsed.get("red_flags", "")),
        )

    def generate_pdf(self, discharge_data: Dict[str, Any]) -> bytes:
        """Generate PDF bytes from discharge data using WeasyPrint or fallback to bytes."""
        # 1. Procedures
        procs = discharge_data.get("procedures", [])
        if isinstance(procs, str):
            try:
                procs = json.loads(procs)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    "invalid_discharge_procedures_json",
                    error=str(exc),
                )
                procs = []
        
        procs_section = ""
        if procs:
            rows = "".join(f"<tr><td>{p.get('name','')}</td><td>{p.get('ichi_code','N/A')}</td></tr>" for p in procs)
            procs_section = f'<div class="section"><h2>Procedures Performed</h2><table><tr><th>Procedure Name</th><th>ICHI Code</th></tr>{rows}</table></div>'

        # 2. Investigations
        invs = discharge_data.get("key_investigations", [])
        if isinstance(invs, str):
            try:
                invs = json.loads(invs)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    "invalid_discharge_investigations_json",
                    error=str(exc),
                )
                invs = []
        
        invs_section = ""
        if invs:
            rows = "".join(f"<tr><td>{i.get('name', i.get('test_name',''))}</td><td><strong>{i.get('value', i.get('result',''))}</strong></td></tr>" for i in invs)
            invs_section = f'<div class="section"><h2>Key Investigations & Trends</h2><table><tr><th>Investigation</th><th>Result / Narrative</th></tr>{rows}</table></div>'

        # 3. Medications
        meds = discharge_data.get("discharge_medications", discharge_data.get("discharge_meds", []))
        if isinstance(meds, str):
            try:
                meds = json.loads(meds)
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning(
                    "invalid_discharge_medications_json",
                    error=str(exc),
                )
                meds = []
        
        meds_section = ""
        if meds:
            rows = "".join(f"<tr><td>{m.get('name','')}</td><td>{m.get('dose','')}</td><td>{m.get('frequency','')}</td><td>{m.get('duration','')}</td></tr>" for m in meds)
            meds_section = f'<div class="section"><h2>Discharge Medications</h2><table><tr><th>Drug Name</th><th>Dose</th><th>Frequency</th><th>Duration</th></tr>{rows}</table></div>'

        # 4. Dates
        adm_date = discharge_data.get("admission_date", "")
        dis_date = discharge_data.get("discharge_date", "")
        if isinstance(adm_date, datetime): adm_date = adm_date.strftime("%d %B %Y")
        if isinstance(dis_date, datetime): dis_date = dis_date.strftime("%d %B %Y")

        # 4. Operations
        op1 = procs[0].get("name", "") if len(procs) > 0 else ""
        op2 = procs[1].get("name", "") if len(procs) > 1 else ""

        # 5. Narrative Formatting
        clinical_summary = f"{discharge_data.get('history_of_present_illness', '')}\\n{discharge_data.get('hospital_course', '')}"
        
        lab_invs = "\\n".join([f"- {i.get('name', i.get('test_name',''))}: {i.get('value', i.get('result',''))}" for i in invs])
        
        presc = "\\n".join([f"- {m.get('name')} {m.get('dose')} {m.get('frequency')} x {m.get('duration')}" for m in meds])
        
        recs = f"{discharge_data.get('condition_at_discharge', '')}\\nPLAN: {discharge_data.get('follow_up_plan', '')}\\nRED FLAGS: {discharge_data.get('red_flags', '')}"

        # 6. Dates
        adm_date = discharge_data.get("admission_date", "")
        dis_date = discharge_data.get("discharge_date", "")
        if isinstance(adm_date, datetime): adm_date = adm_date.strftime("%d/%m/%Y")
        if isinstance(dis_date, datetime): dis_date = dis_date.strftime("%d/%m/%Y")

        name_parts = discharge_data.get("patient_name", "").split(" ")
        surname = name_parts[-1] if len(name_parts) > 0 else ""
        other_names = " ".join(name_parts[:-1]) if len(name_parts) > 1 else (name_parts[0] if len(name_parts) > 0 else "")

        html = PDF_TEMPLATE.format(
            ip_no=discharge_data.get("ip_no", "N/A"),
            surname=surname,
            other_names=other_names,
            age=discharge_data.get("age", ""),
            sex=discharge_data.get("sex", ""),
            ward=discharge_data.get("ward", ""),
            admission_date=adm_date,
            discharge_date=dis_date,
            attending_doctors=discharge_data.get("attending_doctors", ""),
            final_diagnosis=discharge_data.get("final_diagnosis", "N/A"),
            other_illness=discharge_data.get("other_illness", ""),
            complications=discharge_data.get("complications", ""),
            operation_1=op1,
            operation_2=op2,
            clinical_summary=clinical_summary,
            lab_investigations=lab_invs,
            discharge_prescription=presc,
            recommendations=recs,
            doctor_name=settings.doctor_name,
            current_date=datetime.now().strftime("%d/%m/%Y"),
            qualification=discharge_data.get("doctor_qualification", ""),
            doc_id=str(discharge_data.get("id", "DRAFT"))
        )

        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html).write_pdf()
            return pdf_bytes
        except ImportError:
            logger.warning("weasyprint_unavailable", fallback="returning HTML as bytes")
            return html.encode("utf-8")

    async def generate(self, admission_id: str, patient_id: str) -> DischargeSummary:
        logger.info("discharge_generation_started", admission_id=admission_id)
        try:
            context = await self._gather_context(admission_id, patient_id)
            raw_synthesis = await self._synthesize_llm(context)
            summary = self._structure_summary(raw_synthesis, context, admission_id)
            logger.info("discharge_generation_success", los=summary.length_of_stay_days)
            return summary
        except DischargeEngineException:
            raise
        except Exception as exc:
            logger.error(
                "discharge_generation_failed",
                error=str(exc),
                exc_info=True,
            )
            raise DischargeEngineException(
                f"Failed to generate discharge summary: {exc}"
            ) from exc
