from fastapi import FastAPI
from app.api.v1_chat import router as chat_router
from app.api.v1_problems import router as problems_router
from app.api.v1_learning_path import router as lp_router
from app.api.v1_db_health import router as health_router
from app.db import mongo

app = FastAPI(
    title="nerdmath",
    version="1.0.0",
    description="Chatbot, Variant Problem Generation, Personalized Learning Path"
)

# 기능별 라우터 등록
app.include_router(chat_router)
app.include_router(problems_router)
app.include_router(lp_router)
app.include_router(health_router)

# 헬스체크
@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
def on_startup():
    try:
        mongo.ensure_indexes()
        print("✅ Mongo indexes ensured")
    except Exception as e:
        print("⚠️ Mongo ensure_indexes failed:", e)