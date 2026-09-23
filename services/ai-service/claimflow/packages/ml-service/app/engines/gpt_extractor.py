from __future__ import annotations

import base64
import json
import os
from io import BytesIO
from typing import Any

from openai import OpenAI
from PIL import Image

# Initialize OpenAI client
# Note: In a production environment, this might be handled via dependency injection
_client: OpenAI | None = None

def get_openai_client() -> OpenAI | None:
    global _client
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    
    if _client is None:
        _client = OpenAI(api_key=api_key)
    
    return _client

def _encode_image(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def extract_fields_with_gpt(image: Image.Image, ocr_text: str | None = None) -> list[dict[str, Any]]:
    client = get_openai_client()
    if not client:
        return []

    base64_image = _encode_image(image)

    prompt = """
    Extract the following fields from this medical claim document. 
    Return the result as a STRICT JSON object containing a "fields" array.
    Each object in the "fields" array MUST have 'field_key', 'value', and 'confidence' (0.0 to 1.0).
    
    CRITICAL: 
    - NEVER return a single field called "Result" containing the whole list.
    - NEVER return strings that look like Python lists or JSON. 
    - Each piece of information (e.g., patient name, date, provider id) MUST be a separate object in the "fields" array.
    
    Fields to extract:
    - patient_sha_id (format: CR000000000-0)
    - provider_id (format: FID-00-000000-0)
    - patient_name
    - physician_name
    - diagnosis (primary diagnosis description)
    - icd_code (ICD-10 code)
    - admission_date (YYYY-MM-DD)
    - discharge_date (YYYY-MM-DD)
    - claim_amount (total amount, numeric only)

    If a field is not found, omit it from the array.
    """

    if ocr_text:
        prompt += f"\n\nHere is the OCR text from the document to help you:\n<ocr_text>\n{ocr_text}\n</ocr_text>\n"

    prompt += "\nOnly return the JSON object, no other text."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a specialized medical claim data extractor. You excel at extracting structured data from claim forms. You always return flat, individual fields in the requested schema. You NEVER wrap the whole result in a single string or a generic 'Result' field."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=1000,
        )

        content = response.choices[0].message.content
        if not content:
            return []

        data = json.loads(content)
        
        # Robust parsing of the JSON response
        result = []
        if isinstance(data, dict):
            # 1. Main path: {"fields": [...]}
            if "fields" in data and isinstance(data["fields"], list):
                result = data["fields"]
            else:
                # 2. Key-value pair fallback: {"patient_name": "...", ...}
                for k, v in data.items():
                    if k == "fields": continue
                    if isinstance(v, dict) and "value" in v:
                        result.append({"field_key": k, **v})
                    elif isinstance(v, (str, int, float, bool)):
                        result.append({"field_key": k, "value": str(v), "confidence": 0.9})
        elif isinstance(data, list):
            # 3. Direct list fallback: [{"field_key": "...", ...}, ...]
            result = data

        # Final Cleanup: Ensure no field itself contains stringified JSON or is called 'Result'
        cleaned = []
        for field in result:
            if not isinstance(field, dict): continue
            key = field.get("field_key", field.get("fieldKey", field.get("key", "")))
            if not key or key.lower() == "result": continue
            
            val = field.get("value", field.get("field_value", field.get("fieldValue", "")))
            if isinstance(val, (list, dict)): continue # Skip nested structures
            if isinstance(val, str) and (val.startswith("[") or val.startswith("{")):
                continue # Skip stringified JSON
                
            cleaned.append({
                "field_key": key,
                "value": str(val) if val is not None else "",
                "confidence": float(field.get("confidence", 0.9))
            })
            
        return cleaned

    except Exception as e:
        print(f"Error during GPT extraction: {e}")
        return []
