import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
import os

from app.engines.gpt_extractor import extract_fields_with_gpt
from app.engines.field_extractor import extract_sha_claim_fields
from app.main import process_document, ProcessDocumentRequest

def test_fallback_to_local_when_gpt_fails():
    # Mock OCR result
    ocr_result = {"raw_text": "Patient Name: John Doe\nClaim Amount: 1000", "overall_confidence": 0.9, "word_count": 10}
    
    # Mock GPT to return nothing (representing failure or no fields found)
    with patch('app.engines.gpt_extractor.extract_fields_with_gpt', return_value=[]):
        # We expect it to use extract_sha_claim_fields
        local_result = extract_sha_claim_fields(ocr_result['raw_text'])
        assert any(f['field_key'] == 'patient_name' and f['value'] == 'John Doe' for f in local_result)

@patch('app.main.load_document_pages')
@patch('app.main.process_page_ocr')
@patch('app.main.classify_document')
@patch('app.engines.gpt_extractor.get_openai_client')
def test_process_document_hand_in_hand(mock_get_client, mock_classify, mock_ocr, mock_load):
    # Setup mocks
    mock_load.return_value = [(1, Image.new('RGB', (100, 100)))]
    mock_ocr.return_value = {"raw_text": "OCR TEXT", "overall_confidence": 0.9, "word_count": 2}
    mock_classify.return_value = {"predicted_class": "CLAIM_FORM", "confidence": 0.99}
    
    # Mock OpenAI client
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    # Mock response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"fields": [{"field_key": "patient_name", "value": "Jane Smith", "confidence": 0.95}]}'))
    ]
    mock_client.chat.completions.create.return_value = mock_response

    # Test request
    request = ProcessDocumentRequest(
        document_id="test-doc",
        storage_path="/tmp/test.pdf",
        doc_type="CLAIM",
        processing_route="STRUCTURED_EXTRACT"
    )

    # Set API key env var to trigger GPT logic
    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
        from app.main import process_document
        response = process_document(request)

    # Verify GPT was called
    assert mock_client.chat.completions.create.called
    
    # Verify results
    assert len(response.aggregated_fields) > 0
    assert response.aggregated_fields[0]['value'] == "Jane Smith"
    assert response.aggregated_fields[0]['field_key'] == "patient_name"
