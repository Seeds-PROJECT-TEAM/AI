# sat_mathpix_single.py
import os, time, re, json
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


# 환경 설정


BASE_DIR = Path(__file__).resolve().parent

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

APP_ID  = os.getenv("MATHPIX_APP_ID")
APP_KEY = os.getenv("MATHPIX_APP_KEY")

def _mask(s): return (s[:3]+"..."+s[-3:]) if s else "<EMPTY>"
print("[env]", _mask(APP_ID), _mask(APP_KEY))
if not APP_ID or not APP_KEY:
    raise RuntimeError("❌ .env의 MATHPIX_APP_ID / MATHPIX_APP_KEY가 비어 있습니다.")

PDF_PATH = (BASE_DIR / ".." / "data" / "SAT Suite Question Bank - Results.pdf").resolve()
OUT_DIR  = (BASE_DIR / ".." / "out").resolve()
IMG_DIR  = OUT_DIR / "images"
OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"app_id": APP_ID.strip(), "app_key": APP_KEY.strip()}


# 업로드 / 폴링 / 다운로드
def submit_pdf_for_markdown(pdf_path: Path) -> str:
    options = {
        "format": "markdown",
        "include_latex": True,
        "include_table_markdown": True,
        "math_inline_delimiters": ["$", "$"],
        "math_block_delimiters": ["$$", "$$"],
        "pdf_options": {"extract_images": True},
    }
    with pdf_path.open("rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        data  = {"options_json": json.dumps(options)}
        r = requests.post("https://api.mathpix.com/v3/pdf",
                          headers=HEADERS, files=files, data=data, timeout=120)
    print("[upload]", r.status_code, r.text[:300])
    r.raise_for_status()
    return r.json()["pdf_id"]

def poll_result(pdf_id: str, interval=4, timeout=900) -> None:
    url = f"https://api.mathpix.com/v3/pdf/{pdf_id}"
    t0 = time.time()
    while True:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        st = r.json().get("status")
        if st in ("completed", "error"):
            if st == "error":
                raise RuntimeError(f"Mathpix 처리 오류: {r.text[:300]}")
            return
        if time.time() - t0 > timeout:
            raise TimeoutError(f" 변환 대기 초과(pdf_id={pdf_id})")
        print(f"[poll] status={st} ...")
        time.sleep(interval)

def get_pdf_markdown(pdf_id: str) -> str:
    # .md 우선, 없으면 .mmd
    url_md = f"https://api.mathpix.com/v3/pdf/{pdf_id}.md"
    r = requests.get(url_md, headers=HEADERS, timeout=120)
    if r.status_code == 200 and r.text.strip():
        return r.text
    url_mmd = f"https://api.mathpix.com/v3/pdf/{pdf_id}.mmd"
    r = requests.get(url_mmd, headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.text


# 파싱 유틸 (정규식/도우미)
IMG_MD_RE   = re.compile(r'!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)')
CHOICE_RE   = re.compile(r'(?m)^\s*([A-D])[)\.]\s*(.+)$')
ANSWER_RE   = re.compile(r'(?im)(?:^|\n)\s*(?:Correct\s*Answer|Answer)\s*:\s*([A-D0-9\.]+)')
# 난이도: ## 유무/공백/대소문자 허용
DIFF_RE     = re.compile(r'(?im)^(?:##\s*)?(?:Question\s*Difficulty|Difficulty)\s*:\s*(Easy|Medium|Hard)\b')
# 라셔널: "## Rationale" 섹션 전체
RATIONALE_RE= re.compile(r'(?is)^(?:##\s*)?Rationale\s*\n+(.+?)(?=^##|\Z)', re.MULTILINE)

def _to_rel_from_out(p: Path) -> str:
    try:
        return Path(os.path.relpath(p, start=OUT_DIR)).as_posix()
    except Exception:
        return p.as_posix()

def download_image(url: str, dst_dir: Path) -> Path:
    name = os.path.basename(urlparse(url).path) or f"img_{int(time.time()*1000)}.png"
    out = dst_dir / name
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    out.write_bytes(r.content)
    return out

def strip_meta(md: str) -> str:
    """상단 메타 표/헤더 제거 (Assessment-table, Question ID/ID:/Question Difficulty 헤더 등)."""
    md = re.sub(r'(?ms)^\|\s*Assessment\s*\|.*?\|\s*$\n(?:^\|.*\|\s*$\n)+', '', md)
    md = re.sub(r'(?mi)^\s*##\s*Question ID[^\n]*\n?', '', md)
    md = re.sub(r'(?mi)^\s*##\s*ID\s*:[^\n]*\n?', '', md)
    md = re.sub(r'(?mi)^\s*##\s*Question Difficulty\s*:[^\n]*\n?', '', md)  # 헤더형 난이도 제거(본문용)
    return md.strip()

def extract_images(md: str):
    """마크다운에서 이미지 수집(중복 제거), 로컬 저장, question_text에서는 모두 제거."""
    seen = set()
    imgs = []
    for m in IMG_MD_RE.finditer(md):
        alt = (m.group("alt") or "figure").strip()
        src = (m.group("src") or "").strip()
        if src in seen:
            continue
        seen.add(src)
        if src.startswith("http"):
            try:
                local = download_image(src, IMG_DIR)
                imgs.append({"alt": alt, "src": _to_rel_from_out(local)})
            except Exception:
                pass
    # 본문에서 모든 이미지 태그 제거
    md_no_img = IMG_MD_RE.sub('', md)
    return md_no_img, imgs


# 핵심 파서: 한 문서 = 한 문항
def parse_single_question(md_text: str, problem_id: str, origin_pdf: str):
    # 0) 난이도/라셔널은 메타 제거 전에 먼저 시도 (문서 끝/헤더 섹션 보장)
    difficulty = None
    m = DIFF_RE.search(md_text)
    if m:
        difficulty = m.group(1).capitalize()

    rationale = None
    m = RATIONALE_RE.search(md_text)
    if m:
        rationale = m.group(1).strip()

    # 1) 메타 제거
    md = strip_meta(md_text)

    # 2) 이미지 추출 & 본문에서 제거
    md, images = extract_images(md)

    # 3) 정답 추출 (객관식 문자 or 숫자)
    answer = None
    m = ANSWER_RE.search(md)
    if m:
        answer = m.group(1).strip()

    # 4) 난이도/라셔널 재시도(위에서 못 잡았을 때)
    if not difficulty:
        m = DIFF_RE.search(md)
        if m:
            difficulty = m.group(1).capitalize()
    if not rationale:
        m = RATIONALE_RE.search(md)
        if m:
            rationale = m.group(1).strip()

    # 5) 선택지 추출
    choices = {}
    for m in CHOICE_RE.finditer(md):
        label = m.group(1).upper()
        text  = re.sub(r'\s+', ' ', m.group(2).strip())
        choices[label] = text
    if not choices:
        choices = None

    # 6) question_text 만들기: 선지/정답/난이도/라셔널/헤더 제거 → 본문만
    qt = md
    qt = re.sub(r'(?im)^(?:Correct\s*Answer|Answer)\s*:\s*[^\n]*$', '', qt)
    qt = re.sub(r'(?im)^(?:##\s*)?(?:Question\s*Difficulty|Difficulty)\s*:\s*[^\n]*$', '', qt)
    qt = CHOICE_RE.sub('', qt)
    qt = RATIONALE_RE.sub('', qt)
    qt = re.sub(r'\n{3,}', '\n\n', qt).strip()

    return {
        "problem_id": problem_id,
        "question_text": qt,
        "choices": choices,
        "answer": answer,
        "rationale": rationale,
        "difficulty": difficulty,
        "images": images,
        "source": {"origin": origin_pdf, "page": 1},
    }

# 메인
def main():
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"❌ PDF가 없습니다: {PDF_PATH}")
    pdf_id = submit_pdf_for_markdown(PDF_PATH)
    poll_result(pdf_id)
    md_text = get_pdf_markdown(pdf_id)
    if not md_text.strip():
        raise RuntimeError("변환된 마크다운이 비어 있습니다.")
    # 한 문서 = 한 문항
    obj = parse_single_question(md_text, problem_id="6d99b141", origin_pdf=PDF_PATH.name)
    out_path = OUT_DIR / "problem.json"
    out_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Saved 1 problem to {out_path}")

if __name__ == "__main__":
    main()
