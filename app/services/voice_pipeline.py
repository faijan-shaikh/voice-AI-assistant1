import time
from pathlib import Path
from uuid import uuid4
from google.genai import types
from gtts import gTTS
from app.services.gemini_client import client, LLM_MODEL, TTS_LANGUAGE

AUDIO_DIR = Path("data/audio")
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = (
    "You are a helpful AI voice assistant for college students. "
    "Answer clearly and naturally. Keep responses concise enough to be comfortable when spoken aloud. "
    "Avoid unnecessary markdown and tables."
)

MODELS_FALLBACK = [LLM_MODEL, "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]

def generate_content_with_retry(contents, config=None):
    """Execute Gemini call with model fallback and rate limit retry handling."""
    last_err = None
    for model_name in MODELS_FALLBACK:
        for attempt in range(3):
            try:
                if config:
                    return client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config
                    )
                else:
                    return client.models.generate_content(
                        model=model_name,
                        contents=contents
                    )
            except Exception as e:
                last_err = e
                err_msg = str(e).lower()
                if "429" in err_msg or "resource_exhausted" in err_msg:
                    time.sleep(2 * (attempt + 1))
                else:
                    break
    raise last_err

def transcribe_audio(audio_path: Path) -> str:
    suffix = audio_path.suffix.lower().lstrip(".")
    mime_map = {
        "mp3": "audio/mp3",
        "wav": "audio/wav",
        "webm": "audio/webm",
        "ogg": "audio/ogg",
        "m4a": "audio/m4a",
    }
    mime_type = mime_map.get(suffix, "audio/webm")
                
    with audio_path.open("rb") as f:
        audio_bytes = f.read()

    try:
        response = generate_content_with_retry(
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Transcribe the following audio recording accurately. Return only the verbatim transcribed text without commentary.",
            ]
        )
        return (response.text or "").strip()
    except Exception as e:
        print(f"Transcription error: {e}")
        return "Audio transcription could not be completed."

def answer_from_text(user_text: str) -> str:
    try:
        response = generate_content_with_retry(
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
            ),
        )
        return (response.text or "").strip()
    except Exception as e:
        print(f"Answer generation error: {e}")
        return f"Processed query: {user_text}"

def generate_speech(text: str) -> Path:
    output = AUDIO_DIR / f"response_{uuid4().hex}.mp3"
    tts = gTTS(text=text, lang=TTS_LANGUAGE)
    tts.save(str(output))
    return output
