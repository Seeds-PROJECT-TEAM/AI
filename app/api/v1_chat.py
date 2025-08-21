from fastapi import APIRouter, BackgroundTasks
import subprocess, sys, os
from pathlib import Path

router = APIRouter(prefix="/problems", tags=["problems"])
ROOT = Path(__file__).resolve().parents[2]

@router.post("/pipeline/run")
def run_pipeline(background_tasks: BackgroundTasks):
    def _task():
        subprocess.run([sys.executable, str(ROOT/"scripts/pipeline_all.py")],
                       cwd=str(ROOT), env={**os.environ, "PYTHONPATH": str(ROOT)}, check=False)
    background_tasks.add_task(_task)
    return {"status": "started"}
