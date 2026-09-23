"""ClaimFlow ML Service - OCR, document classification, signature detection"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .engines import extract_sha_claim_fields, load_document_pages, extract_fields_with_gpt
from .routers import (
    assess_image_quality,
    classify_document,
    detect_signature_or_stamp,
    init_ocr_engines,
    process_page_ocr,
)


class ProcessDocumentRequest(BaseModel):
    document_id: str = Field(min_length=1)
    storage_path: str = Field(min_length=1)
    doc_type: str = Field(min_length=1)
    processing_route: Literal[
        'FULL_OCR_EXTRACT',
        'EXISTENCE_QUALITY_ONLY',
        'STRUCTURED_EXTRACT',
        'SIGNATURE_DETECT_ONLY',
    ]
    pages: list[int] | None = None
    filename: str | None = None
    license_tier: Literal['FREE', 'PRO'] = 'FREE'


class PageProcessResult(BaseModel):
    page_number: int
    status: Literal['COMPLETED', 'FAILED']
    quality: dict[str, Any] | None = None
    ocr: dict[str, Any] | None = None
    classification: dict[str, Any] | None = None
    extracted_fields: list[dict[str, Any]] | None = None
    signature: dict[str, Any] | None = None
    error: str | None = None


class ProcessDocumentResponse(BaseModel):
    document_id: str
    doc_type: str
    processing_route: str
    status: Literal['COMPLETED', 'PARTIAL']
    processed_at: str
    total_pages: int
    pages_processed: int
    pages_failed: int
    pages: list[PageProcessResult]
    aggregated_fields: list[dict[str, Any]]


# Disable OpenAPI/Swagger docs in production to avoid exposing API surface
_is_dev: bool = os.environ.get("APP_ENV", "development") == "development" or os.environ.get("DEBUG", "").lower() in ("true", "1")
_docs_url: str | None = "/docs" if _is_dev else None
_redoc_url: str | None = "/redoc" if _is_dev else None
_openapi_url: str | None = "/openapi.json" if _is_dev else None

app = FastAPI(
    title='ClaimFlow ML Service',
    version='1.0.0',
    description='OCR, document classification, signature detection and quality checks for SHA claims documents',
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

_cors_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['*'],
)


@app.on_event('startup')
def _startup() -> None:
    app.state.ocr_engines = init_ocr_engines()
    app.state.doc_classifier_loaded = True


@app.get('/health')
def health() -> dict[str, str]:
    """Minimal health check endpoint. Returns service status only.

    @returns: Dictionary with status indicator.
    """
    return {'status': 'ok', 'service': 'claimflow-ml-service'}


@app.post('/ml/process-document', response_model=ProcessDocumentResponse)
def process_document(request: ProcessDocumentRequest) -> ProcessDocumentResponse:
    try:
        pages = load_document_pages(request.storage_path, request.pages)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected loader failures
        raise HTTPException(status_code=400, detail=f'Unable to load document: {exc}') from exc

    if not pages:
        raise HTTPException(status_code=422, detail='No pages found to process')

    page_results: list[PageProcessResult] = []
    aggregated_fields: list[dict[str, Any]] = []
    failed_pages = 0

    for page_number, image in pages:
        try:
            quality = assess_image_quality(image)
            result = PageProcessResult(page_number=page_number, status='COMPLETED', quality=quality)

            if request.processing_route in {'FULL_OCR_EXTRACT', 'STRUCTURED_EXTRACT'}:
                # 1. Always perform OCR first
                ocr_result = process_page_ocr(image=image, license_tier=request.license_tier)
                result.ocr = ocr_result

                classifier_input = request.filename or request.storage_path
                result.classification = classify_document(classifier_input, ocr_result['raw_text'])

                # 2. Extract fields (Hand-in-hand GPT and Local)
                extracted = []
                if os.environ.get("OPENAI_API_KEY"):
                    # Use GPT-4o-mini with OCR text as hint
                    extracted = extract_fields_with_gpt(image, ocr_result['raw_text'])
                
                # 3. Fallback to Local Extraction if GPT failed or returned nothing
                if not extracted:
                    extracted = extract_sha_claim_fields(ocr_result['raw_text'])

                enriched = [
                    {
                        **field,
                        'page_number': page_number,
                    }
                    for field in extracted
                ]
                result.extracted_fields = enriched
                aggregated_fields.extend(enriched)

            if request.processing_route in {'FULL_OCR_EXTRACT', 'SIGNATURE_DETECT_ONLY'}:
                result.signature = detect_signature_or_stamp(image)

            page_results.append(result)
        except Exception as exc:
            failed_pages += 1
            page_results.append(
                PageProcessResult(
                    page_number=page_number,
                    status='FAILED',
                    error=str(exc),
                )
            )

    status: Literal['COMPLETED', 'PARTIAL'] = 'COMPLETED' if failed_pages == 0 else 'PARTIAL'

    return ProcessDocumentResponse(
        document_id=request.document_id,
        doc_type=request.doc_type,
        processing_route=request.processing_route,
        status=status,
        processed_at=datetime.now(timezone.utc).isoformat(),
        total_pages=len(pages),
        pages_processed=len(pages) - failed_pages,
        pages_failed=failed_pages,
        pages=page_results,
        aggregated_fields=aggregated_fields,
    )
