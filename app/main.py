import json
from pathlib import Path
from typing import List, Optional
from uuid import uuid4
from fastapi import FastAPI, File, HTTPException, UploadFile, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.services.voice_pipeline import answer_from_text, transcribe_audio, generate_speech
from app.services.action_items import (
    process_voice_note_audio,
    process_voice_note_text,
    process_batch_voice_notes,
    VoiceNoteResult,
    BatchProcessingResult
)
from app.services.pdf_exporter import create_pdf_report

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path("data")
AUDIO_DIR = DATA_DIR / "audio"
PDF_DIR = DATA_DIR / "pdf"

AUDIO_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Voice Notes → Action Items AI System", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

class TextRequest(BaseModel):
    text: str

class ExportPdfRequest(BaseModel):
    data: dict

@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")

@app.get("/health")
def health():
    return {"status": "ok", "system": "Voice Notes to Action Items Engine"}

# Original Pipeline Endpoints (Maintained)
@app.post("/api/text")
def text_pipeline(request: TextRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Please enter some text.")
    try:
        answer = answer_from_text(text)
        audio = generate_speech(answer)
        return {"transcript": text, "answer": answer, "audio_url": f"/api/audio/{audio.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model/Pipeline Error: {str(e)}")

@app.post("/api/voice")
async def voice_pipeline(audio: UploadFile = File(...)):
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Audio file is required.")
    suffix = Path(audio.filename).suffix or ".webm"
    temp = AUDIO_DIR / f"input_{uuid4().hex[:8]}{suffix}"
    try:
        temp.write_bytes(await audio.read())
        transcript = transcribe_audio(temp)
        if not transcript:
            raise HTTPException(status_code=400, detail="Could not transcribe audio. Please try speaking clearly.")
        answer = answer_from_text(transcript)
        output = generate_speech(answer)
        return {"transcript": transcript, "answer": answer, "audio_url": f"/api/audio/{output.name}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice Processing Error: {str(e)}")
    finally:
        temp.unlink(missing_ok=True)

# Project 1: Voice Notes → Action Items Endpoints

@app.post("/api/action-items/audio")
async def action_items_from_audio(audio: UploadFile = File(...)):
    """Transcribe single audio file & extract title, summary, key takeaways, and structured action items."""
    if not audio.filename:
        raise HTTPException(status_code=400, detail="Audio file is required.")
    
    suffix = Path(audio.filename).suffix or ".webm"
    temp_path = AUDIO_DIR / f"note_{uuid4().hex[:8]}{suffix}"
    
    try:
        temp_path.write_bytes(await audio.read())
        result = process_voice_note_audio(temp_path)
        
        # Keep stored audio for browser playback
        audio_name = f"recording_{result.id}{suffix}"
        saved_audio = AUDIO_DIR / audio_name
        temp_path.rename(saved_audio)
        
        result_dict = result.model_dump()
        result_dict["audio_url"] = f"/api/audio/{audio_name}"
        return result_dict
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Action Items Processing Error: {str(e)}")

@app.post("/api/action-items/text")
def action_items_from_text(request: TextRequest):
    """Extract title, summary, key takeaways, and structured action items from plain text voice memo."""
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Please enter or paste your voice note text.")
    try:
        result = process_voice_note_text(text)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text Analysis Error: {str(e)}")

@app.post("/api/action-items/batch")
async def action_items_batch(files: List[UploadFile] = File(...)):
    """Upload multiple audio recordings for batch processing into individual & master consolidated summary + action items."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one audio file is required for batch processing.")
    
    saved_temp_paths: List[Path] = []
    try:
        for file in files:
            if not file.filename:
                continue
            suffix = Path(file.filename).suffix or ".webm"
            temp_file = AUDIO_DIR / f"batch_{uuid4().hex[:8]}{suffix}"
            temp_file.write_bytes(await file.read())
            saved_temp_paths.append(temp_file)

        if not saved_temp_paths:
            raise HTTPException(status_code=400, detail="No valid audio files were uploaded.")

        batch_result = process_batch_voice_notes(saved_temp_paths)
        return batch_result.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch Processing Error: {str(e)}")
    finally:
        # Clean up batch temp files
        for p in saved_temp_paths:
            p.unlink(missing_ok=True)

@app.post("/api/action-items/pdf")
def export_pdf(payload: ExportPdfRequest):
    """Generate executive PDF summary report with formatted tables and action items list."""
    data = payload.data
    if not data:
        raise HTTPException(status_code=400, detail="Report data cannot be empty.")
    
    pdf_filename = f"report_{uuid4().hex[:8]}.pdf"
    pdf_path = PDF_DIR / pdf_filename
    
    try:
        create_pdf_report(data, pdf_path)
        return FileResponse(
            path=pdf_path,
            filename=f"Action_Items_Report_{uuid4().hex[:4]}.pdf",
            media_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF Export Error: {str(e)}")

@app.get("/api/audio/{filename}")
def get_audio(filename: str):
    path = AUDIO_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio not found.")
    return FileResponse(path, media_type="audio/mpeg", filename=filename)
