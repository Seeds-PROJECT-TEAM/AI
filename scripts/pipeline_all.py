# AI/scripts/pipeline_all.py
import os, sys, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

# ---------------- paths & env ----------------
SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT        = SCRIPTS_DIR.parent
APP_DIR     = ROOT / "app"
OUT_ROOT    = ROOT / "out"

# .env: 루트 우선 → app/.env
if (ROOT/".env").exists():
    load_dotenv(ROOT/".env")
elif (APP_DIR/".env").exists():
    load_dotenv(APP_DIR/".env")

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
MATHPIX_APP_ID  = os.getenv("MATHPIX_APP_ID")
MATHPIX_APP_KEY = os.getenv("MATHPIX_APP_KEY")

def run(cmd: List[str], cwd: Path = ROOT, env: Optional[dict] = None) -> None:
    print("+", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr}")

def step_mathpix() -> None:
    if not (MATHPIX_APP_ID and MATHPIX_APP_KEY):
        raise RuntimeError("MATHPIX_APP_ID / MATHPIX_APP_KEY가 .env에 없습니다.")
    # sat_mathpix_single.py가 out/problem.json 또는 out/<PDF>/problems.json 생성한다고 가정
    run([sys.executable, str(SCRIPTS_DIR / "sat_mathpix_single.py")], cwd=ROOT)

def step_transform() -> None:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 .env에 없습니다.")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)  # 모듈 임포트 보장
    # ai_transformer는 무인자 실행 시 out/problem(s).json 자동 탐색 → out/converted_with_schema.json 저장
    run([sys.executable, "-m", "app.services.ai_transformer"], cwd=ROOT, env=env)

def ensure_outputs() -> None:
    """최소 산출물 점검: out/problem.json 또는 out/**/problems.json, 그리고 out/converted_with_schema.json"""
    p1 = OUT_ROOT / "problem.json"
    p2_list = list(OUT_ROOT.rglob("problems.json"))
    p3 = OUT_ROOT / "converted_with_schema.json"
    p3_list = list(OUT_ROOT.rglob("converted_with_schema.json"))

    if not (p1.exists() or p2_list):
        raise FileNotFoundError("Mathpix 산출물이 없습니다. out/problem.json 또는 out/**/problems.json 이 생성되어야 합니다.")
    if not (p3.exists() or p3_list):
        raise FileNotFoundError("변환 산출물이 없습니다. out/converted_with_schema.json 또는 out/**/converted_with_schema.json 이 생성되어야 합니다.")

def main() -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    # 간단한 락으로 중복 실행 방지
    lock = OUT_ROOT / ".pipeline.lock"
    try:
        if lock.exists():
            age = (datetime.now(timezone.utc) - datetime.fromtimestamp(lock.stat().st_mtime, tz=timezone.utc)).total_seconds()
            if age < 3600:
                raise RuntimeError(f"이미 실행 중인 작업이 있는 것 같습니다: {lock}")
        lock.write_text("running", encoding="utf-8")

        print("=== [1/2] Mathpix 변환 ===")
        step_mathpix()

        print("=== [2/2] OpenAI 변환 ===")
        step_transform()

        ensure_outputs()
        print("✅ 파이프라인 완료 (out/problem.json & out/converted_with_schema.json)")
        print("ok")
    finally:
        try:
            if lock.exists():
                lock.unlink()
        except Exception:
            pass

if __name__ == "__main__":
    main()
