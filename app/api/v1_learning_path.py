from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/learning-path", tags=["LearningPath"])

@router.get("/ping")
def ping():
    return {"learning_path": "pong"}
