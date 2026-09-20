"""Reviews Route."""
from fastapi import APIRouter

router = APIRouter(prefix="/reviews", tags=["Reviews"])

@router.get("/")
def list_reviews():
    return []