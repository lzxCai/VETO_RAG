from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse

APP_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = APP_ROOT / "uploads"
PDF_DIR = APP_ROOT / "PDFoutput"
WEB_DIR = APP_ROOT / "web"
APP_MAIN = APP_ROOT / "app" / "main.py"
REPORT_CONTEXT_DIR = APP_ROOT / "data" / "output"

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

app = FastAPI(title="RAG Report API", version="1.0.0")

_run_lock = asyncio.Lock()


def _safe_filename(name: str) -> str:
    return Path(name).name or "upload.bin"


def _snapshot_mtime(directory: Path, pattern: str) -> dict[Path, float]:
    if not directory.exists():
        return {}
    return {p: p.stat().st_mtime for p in directory.glob(pattern)}


def _latest_updated_file(before: dict[Path, float], directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    candidates: list[tuple[float, Path]] = []
    for p in directory.glob(pattern):
        try:
            mtime = p.stat().st_mtime
        except FileNotFoundError:
            continue
        if mtime > before.get(p, 0):
            candidates.append((mtime, p))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[-1][1]


def _build_input_arg(paths: Iterable[Path]) -> str:
    return ",".join(str(p) for p in paths)


def _tail(text: str | None, limit: int = 2000) -> str:
    if not text:
        return ""
    return text[-limit:]


@app.get("/", response_model=None)
def root() -> Response:
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse({"message": "RAG Report API is running."})


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/api/run")
async def run_report(
    files: list[UploadFile] = File(...),
    parser: str = Form("auto"),
    top_k_per_kb: int = Form(3),
    enable_image_preprocess: bool = Form(False),
) -> FileResponse:
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件。")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_CONTEXT_DIR.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    batch_id = uuid.uuid4().hex

    for upload in files:
        filename = _safe_filename(upload.filename or "")
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {filename}")
        target = UPLOAD_DIR / f"{batch_id}_{filename}"
        try:
            with target.open("wb") as handle:
                shutil.copyfileobj(upload.file, handle)
        finally:
            upload.file.close()
        saved_paths.append(target)

    input_arg = _build_input_arg(saved_paths)
    report_context_path = REPORT_CONTEXT_DIR / f"report_context_{batch_id}.json"

    before_pdf = _snapshot_mtime(PDF_DIR, "*.pdf")

    cmd = [
        sys.executable,
        str(APP_MAIN),
        input_arg,
        "--parser",
        parser,
        "--top-k-per-kb",
        str(top_k_per_kb),
        "--report-context-out",
        str(report_context_path),
    ]
    if enable_image_preprocess:
        cmd.append("--enable-image-preprocess")

    async with _run_lock:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            cwd=str(APP_ROOT),
            capture_output=True,
            text=True,
        )

    if result.returncode != 0:
        detail = {
            "message": "处理失败，未生成 PDF。",
            "stdout": _tail(result.stdout),
            "stderr": _tail(result.stderr),
        }
        raise HTTPException(status_code=500, detail=detail)

    pdf_path = _latest_updated_file(before_pdf, PDF_DIR, "*.pdf")
    if not pdf_path or not pdf_path.exists():
        detail = {
            "message": "未找到新生成的 PDF 文件。",
            "stdout": _tail(result.stdout),
            "stderr": _tail(result.stderr),
        }
        raise HTTPException(status_code=500, detail=detail)

    return FileResponse(
        path=pdf_path,
        filename=pdf_path.name,
        media_type="application/pdf",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
