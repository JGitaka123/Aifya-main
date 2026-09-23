import unittest
from unittest.mock import MagicMock, patch
from PIL import Image
import os
import sys

# Add the app directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'packages/ml-service'))

from app.engines.gpt_extractor import extract_fields_with_gpt
from app.engines.field_extractor import extract_sha_claim_fields
from app.main import process_document, ProcessDocumentRequest

class TestMLIntegration(unittest.TestCase):
    def test_fallback_to_local_when_gpt_fails(self):
        # Mock OCR result
        ocr_text = "Patient Name: John Doe\nClaim Amount: 1000"
        
        # Mock GPT to return nothing
        with patch('app.engines.gpt_extractor.extract_fields_with_gpt', return_value=[]):
            # We expect it to use extract_sha_claim_fields
            local_result = extract_sha_claim_fields(ocr_text)
            self.assertTrue(any(f['field_key'] == 'patient_name' and f['value'] == 'John Doe' for f in local_result))

    @patch('app.main.load_document_pages')
    @patch('app.main.process_page_ocr')
    @patch('app.main.classify_document')
    @patch('app.main.assess_image_quality')
    @patch('app.engines.gpt_extractor.get_openai_client')
    def test_process_document_hand_in_hand(self, mock_get_client, mock_quality, mock_classify, mock_ocr, mock_load):
        # Setup mocks
        mock_load.return_value = [(1, Image.new('RGB', (100, 100)))]
        mock_ocr.return_value = {"raw_text": "OCR TEXT", "overall_confidence": 0.9, "word_count": 2}
        mock_classify.return_value = {"predicted_class": "CLAIM_FORM", "confidence": 0.99}
        mock_quality.return_value = {"score": 0.9}
        
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
            # Reload main to pick up the patch
            import app.main
            response = app.main.process_document(request)

        # Verify GPT was called
        self.assertTrue(mock_client.chat.completions.create.called)
        
        # Verify results
        self.assertGreater(len(response.aggregated_fields), 0)
        self.assertEqual(response.aggregated_fields[0]['value'], "Jane Smith")
        self.assertEqual(response.aggregated_fields[0]['field_key'], "patient_name")

    @patch('app.main.load_document_pages')
    @patch('app.main.process_page_ocr')
    @patch('app.main.classify_document')
    @patch('app.main.assess_image_quality')
    @patch('app.engines.gpt_extractor.extract_fields_with_gpt')
    def test_process_document_fallback_logic(self, mock_gpt, mock_quality, mock_classify, mock_ocr, mock_load):
        # Setup mocks
        mock_load.return_value = [(1, Image.new('RGB', (100, 100)))]
        mock_ocr.return_value = {"raw_text": "Patient Name: Fallback User", "overall_confidence": 0.9, "word_count": 2}
        mock_classify.return_value = {"predicted_class": "CLAIM_FORM", "confidence": 0.99}
        mock_quality.return_value = {"score": 0.9}
        
        # Mock GPT to return nothing
        mock_gpt.return_value = []

        # Test request
        request = ProcessDocumentRequest(
            document_id="test-doc",
            storage_path="/tmp/test.pdf",
            doc_type="CLAIM",
            processing_route="STRUCTURED_EXTRACT"
        )

        # Set API key env var to trigger GPT logic
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key"}):
            import app.main
            response = app.main.process_document(request)

        # Verify results - should have fallback data
        self.assertGreater(len(response.aggregated_fields), 0)
        self.assertTrue(any(f['field_key'] == 'patient_name' and f['value'] == 'Fallback User' for f in response.aggregated_fields))

if __name__ == '__main__':
    unittest.main()
