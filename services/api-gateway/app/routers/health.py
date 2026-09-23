from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    @returns Status dict
    """
    return {"status": "ok", "service": "aifya-api-gateway"}
