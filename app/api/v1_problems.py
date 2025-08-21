from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/problems", tags=["Problems"])

@router.get("/ping")
def ping():
    return {"problems": "pong"}
