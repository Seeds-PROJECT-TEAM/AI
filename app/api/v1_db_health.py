# app/api/v1_db_health.py
from fastapi import APIRouter
from app.db.mongo import _client  # MongoClient 인스턴스
# _client가 아니라 get_db()만 있다면: from app.db.mongo import get_db as _get_db

router = APIRouter(prefix="/api/health", tags=["health"])

@router.get("/mongo")
def mongo_health():
    try:
        # 클라이언트 핑이 가장 확실
        ok = _client.admin.command("ping").get("ok", 0) == 1
        return {"ok": ok}
    except Exception as e:
        return {"ok": False, "error": str(e)}
