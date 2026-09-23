from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth import CurrentUser, get_current_user
from app.schemas.diagnosis import ICD10CodeItem, ICD10SearchResponse
from app.services.icd10_catalog import lookup_icd10, search_icd10

router = APIRouter()


@router.get("/search", response_model=ICD10SearchResponse)
async def search_icd10_codes(
    q: str = Query(..., min_length=1, description="Code fragment or description"),
    limit: int = Query(20, ge=1, le=50),
    current_user: CurrentUser = Depends(get_current_user),
) -> ICD10SearchResponse:
    """
    Type-ahead search over the bundled ICD-10 diagnosis catalog (D5).

    @param q: Search string — an ICD-10 code fragment or description words
    @param limit: Maximum number of results
    @param current_user: Authenticated user from JWT
    @returns Matching ICD-10 codes with canonical descriptions
    """
    results = search_icd10(q, limit=limit)
    return ICD10SearchResponse(
        items=[ICD10CodeItem(**r) for r in results]
    )


@router.get("/{code}", response_model=ICD10CodeItem)
async def get_icd10_code(
    code: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> ICD10CodeItem:
    """
    Resolve a single ICD-10 code to its canonical description (D5).

    @param code: ICD-10 code (e.g. "B54")
    @param current_user: Authenticated user from JWT
    @returns The canonical code/description, or 404 if not in the catalog
    """
    description = lookup_icd10(code)
    if description is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown ICD-10 code: {code}",
        )
    return ICD10CodeItem(code=code.strip().upper().replace(" ", ""), description=description)
