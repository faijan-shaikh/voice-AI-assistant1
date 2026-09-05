from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from gtts import gTTS

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_api_text_pipeline():
    response = client.post("/api/text", json={"text": "Say hello in one word."})
    assert response.status_code == 200
    data = response.json()
    assert "transcript" in data
    assert "answer" in data
    assert "audio_url" in data
    assert data["transcript"] == "Say hello in one word."
    assert len(data["answer"]) > 0

    # Test downloading generated audio
    audio_res = client.get(data["audio_url"])
    assert audio_res.status_code == 200
    assert audio_res.headers["content-type"] == "audio/mpeg"

def test_api_voice_pipeline(tmp_path):
    # Create sample speech audio file
    sample_audio = tmp_path / "sample.mp3"
    tts = gTTS(text="What is machine learning?", lang="en")
    tts.save(str(sample_audio))

    with open(sample_audio, "rb") as f:
        response = client.post(
            "/api/voice",
            files={"audio": ("sample.mp3", f, "audio/mpeg")}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "transcript" in data
    assert "answer" in data
    assert "audio_url" in data
    assert len(data["transcript"]) > 0
    assert len(data["answer"]) > 0
