"""
Document loaders — one function per file type, all return plain text + metadata.
"""
import os
import tempfile
from pathlib import Path


def load_pdf(file_path: str) -> tuple[str, dict]:
    import pdfplumber
    import pytesseract
    from pdf2image import convert_from_path

    text_parts = []
    metadata = {}
    ocr_pages = 0

    with pdfplumber.open(file_path) as pdf:
        metadata["page_count"] = len(pdf.pages)
        metadata["pdf_metadata"] = pdf.metadata or {}

        for page_num, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").strip()

            if len(text) < 100:
                # Scanned page — render at 300 dpi and OCR
                try:
                    images = convert_from_path(
                        file_path,
                        dpi=300,
                        first_page=page_num + 1,
                        last_page=page_num + 1,
                    )
                    if images:
                        text = pytesseract.image_to_string(images[0], lang="bul+eng").strip()
                        ocr_pages += 1
                except Exception:
                    pass

            if text:
                text_parts.append(text)

    metadata["ocr_pages"] = ocr_pages
    return "\n\n".join(text_parts), metadata


def load_docx(file_path: str) -> tuple[str, dict]:
    from docx import Document
    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    metadata = {
        "paragraph_count": len(paragraphs),
        "core_properties": {
            "author": doc.core_properties.author,
            "title": doc.core_properties.title,
        }
    }
    return "\n\n".join(paragraphs), metadata


def load_txt(file_path: str) -> tuple[str, dict]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return text, {"char_count": len(text)}


def load_image(file_path: str) -> tuple[str, dict]:
    """OCR extraction from images using pytesseract."""
    import pytesseract
    from PIL import Image
    img = Image.open(file_path)
    text = pytesseract.image_to_string(img)
    metadata = {
        "image_size": img.size,
        "image_mode": img.mode,
    }
    return text.strip(), metadata


def load_video(file_path: str) -> tuple[str, dict]:
    """
    Extract audio from video and transcribe with faster-whisper.
    Requires ffmpeg installed in the container.
    """
    from faster_whisper import WhisperModel
    import subprocess

    # Extract audio to a temp wav file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = tmp.name

    try:
        subprocess.run(
            ["ffmpeg", "-i", file_path, "-ar", "16000", "-ac", "1",
             "-c:a", "pcm_s16le", audio_path, "-y"],
            check=True,
            capture_output=True,
        )

        # Transcribe — use tiny model in dev to save RAM, switch to base/small in prod
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, beam_size=5)
        text = " ".join(seg.text.strip() for seg in segments)
        metadata = {
            "language": info.language,
            "duration_seconds": round(info.duration, 1),
        }
        return text, metadata
    finally:
        os.unlink(audio_path)


def load_csv(file_path: str) -> tuple[str, dict]:
    """Convert CSV to readable text — each row becomes a sentence."""
    import csv
    rows = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        for i, row in enumerate(reader):
            row_text = ", ".join(f"{k}: {v}" for k, v in row.items() if v)
            rows.append(row_text)
    return "\n".join(rows), {"row_count": len(rows), "columns": headers}


# ── Router ───────────────────────────────────────────────────────────────────

LOADERS = {
    "pdf":   load_pdf,
    "docx":  load_docx,
    "doc":   load_docx,
    "txt":   load_txt,
    "md":    load_txt,
    "png":   load_image,
    "jpg":   load_image,
    "jpeg":  load_image,
    "tiff":  load_image,
    "mp4":   load_video,
    "mov":   load_video,
    "avi":   load_video,
    "mkv":   load_video,
    "mp3":   load_video,  # whisper handles audio too
    "wav":   load_video,
    "csv":   load_csv,
    "tsv":   load_csv,
}


def load_document(file_path: str) -> tuple[str, dict]:
    """Dispatch to the right loader based on file extension."""
    ext = Path(file_path).suffix.lstrip(".").lower()
    loader = LOADERS.get(ext)
    if not loader:
        raise ValueError(f"Unsupported file type: .{ext}")
    return loader(file_path)
