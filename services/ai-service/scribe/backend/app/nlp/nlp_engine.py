import json
from pydantic import ValidationError
from openai import AsyncOpenAI, APIError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from structlog import get_logger

from app.models import ClinicalExtraction
from app.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

client = AsyncOpenAI(api_key=settings.openai_api_key)

KENYA_MED_DICT = """
SWAHILI/SHENG CLINICAL DICTIONARY:
- kichwa inaniuma = headache
- homa = fever (Note: "sina homa" = denies fever)
- tumbo = abdomen / abdominal pain
- kifua = chest
- kupumua vibaya = dyspnea / shortness of breath
- damu = blood
- mimba = pregnancy
- kuharisha = diarrhea
- kutapika = vomiting
- presha = blood pressure
- sukari = diabetes / blood sugar
- malaria = malaria
- mwili kuuma = body aches / myalgia
- mgongo = back / back pain
- macho = eyes
- sikio = ear
- koo = throat
- ngozi = skin
- mkojo = urine
- kikohozi = cough
"""

SYSTEM_PROMPT = f"""
You are an Expert Clinical Informatician at a Kenyan Level 5 hospital.
Your task is to extract highly structured clinical information from a diarized transcript of a doctor-patient encounter.

CRITICAL INSTRUCTIONS:
1. ZERO HALLUCINATION: Only extract explicitly stated information. Do not invent details.
2. NEGATION DETECTION: Clearly distinguish between positive findings and negative findings.
3. SPEAKER ATTRIBUTION: Understand [PATIENT] vs [CLINICIAN] roles.
4. PROACTIVE SUGGESTIONS: If a medication is prescribed (e.g. for heart issues, lung issues, or chronic pain), check if a corresponding diagnostic test (e.g. ECG, X-ray, Ultrasound) was mentioned. If NOT mentioned, add it to "suggested_tests" and include a clinical reason.
5. SWAHILI/SHENG: Use the dictionary to map local terms to English medical standards.

{KENYA_MED_DICT}

OUTPUT FORMAT:
Output MUST be valid JSON adhering strictly to the schema provided.

REQUIRED JSON SCHEMA:
{{
    "chief_complaint": "string or null (Primary reason for visit)",
    "reporting_problem": "string or null (Summary of the core issue reported by patient)",
    "symptoms": "string or null (List of physical symptoms mentioned)",
    "hpi": "string or null (History of present illness)",
    "vitals": [{{ "name": "string", "value": "string", "loinc_code": "string or null", "confidence": 0.0-1.0 }}],
    "physical_exam": "string or null",
    "diagnoses": [{{ "name": "string", "icd11_suggested": "string or null", "icd11_validated": null, "is_primary": boolean, "confidence": 0.0-1.0 }}],
    "lab_orders": [{{ "test_name": "string", "loinc_code": "string or null", "urgency": "routine|stat" }}],
    "suggested_tests": ["string (Format: 'Test Name: Reason for suggestion')"],
    "medications": [{{ "name": "string", "dose": "string", "route": "string", "frequency": "string", "duration": "string", "is_new": boolean }}],
    "procedures": [{{ "name": "string", "ichi_code": "string or null", "requires_preauth": boolean }}],
    "disposition": "string or null",
    "follow_up": "string or null (Specific return instructions)",
    "warnings": ["string"]
}}
"""


class NLPError(Exception):
    pass


class NLPEngine:
    def __init__(self):
        self._api_available = bool(settings.openai_api_key and settings.openai_api_key != "sk-proj-youropenaiapikeyhere...")

    @retry(
        retry=retry_if_exception_type((APIError, APIConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
    )
    async def transcribe(self, audio_file_tuple) -> str:
        """Transcribe audio using OpenAI Whisper."""
        try:
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file_tuple,
                response_format="text"
            )
            return str(response)
        except Exception as e:
            logger.error("nlp_transcription_failed", error=str(e))
            raise NLPError(f"Transcription failed: {str(e)}")

    @retry(
        retry=retry_if_exception_type((APIError, APIConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
    )
    async def _call_llm_extraction(self, transcript: str) -> str:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            timeout=30.0,
        )
        return response.choices[0].message.content

    def _get_fallback_extraction(self, transcript: str) -> ClinicalExtraction:
        """Graceful degradation when LLM is unavailable."""
        logger.warning("nlp_using_fallback", reason="LLM API unavailable or not configured")
        lower = transcript.lower()
        warnings = ["AI extraction unavailable. Manual clinical note entry required."]

        chief_complaint = None
        if "kichwa" in lower or "headache" in lower:
            chief_complaint = "Headache (extracted from keywords)"
        elif "homa" in lower or "fever" in lower:
            chief_complaint = "Fever (extracted from keywords)"
        elif "tumbo" in lower:
            chief_complaint = "Abdominal pain (extracted from keywords)"

        return ClinicalExtraction(
            chief_complaint=chief_complaint,
            reporting_problem="Patient reported concerns identified via keywords.",
            symptoms=chief_complaint,
            hpi=None,
            vitals=[],
            physical_exam=None,
            diagnoses=[],
            lab_orders=[],
            suggested_tests=[],
            medications=[],
            procedures=[],
            disposition=None,
            follow_up=None,
            warnings=warnings,
        )

    def _validate_icd11(self, extraction: ClinicalExtraction) -> ClinicalExtraction:
        """ICD-11 validation. Production: query local SQLite WHO database."""
        known_prefixes = {"BA", "1F", "5A", "CA", "JA", "KB", "MD", "MG", "DA", "AB", "1A", "1B", "1C", "1D", "2A", "2B", "2C"}
        for dx in extraction.diagnoses:
            if dx.icd11_suggested:
                prefix = dx.icd11_suggested[:2].upper()
                if prefix in known_prefixes:
                    dx.icd11_validated = dx.icd11_suggested
                else:
                    extraction.warnings.append(
                        f"Unvalidated ICD-11 code for '{dx.name}': {dx.icd11_suggested}. Manual verification required."
                    )
        return extraction

    def _calibrate_confidence(self, extraction: ClinicalExtraction) -> ClinicalExtraction:
        for vital in extraction.vitals:
            vital.confidence = round(max(0.0, vital.confidence * 0.9), 3)
        for dx in extraction.diagnoses:
            dx.confidence = round(min(1.0, dx.confidence * 1.1), 3)
        return extraction

    async def process_transcript(self, transcript: str) -> ClinicalExtraction:
        logger.info("nlp_extraction_started", transcript_length=len(transcript))

        if not self._api_available:
            return self._get_fallback_extraction(transcript)

        try:
            raw_json = await self._call_llm_extraction(transcript)
            logger.info("nlp_raw_response", raw_json=raw_json)
            extraction_dict = json.loads(raw_json)
            extraction = ClinicalExtraction(**extraction_dict)
            extraction = self._validate_icd11(extraction)
            extraction = self._calibrate_confidence(extraction)
            logger.info("nlp_extraction_completed", diagnoses_count=len(extraction.diagnoses))
            return extraction

        except ValidationError as ve:
            logger.error("nlp_pydantic_validation_error", errors=ve.errors())
            raise NLPError(f"Failed to validate LLM output: {str(ve)}")
        except NLPError:
            raise
        except Exception as e:
            logger.error("nlp_extraction_failed", error=str(e))
            logger.info("nlp_falling_back_to_keyword_extraction")
            return self._get_fallback_extraction(transcript)
