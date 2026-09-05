import io
import os
import tempfile
from pathlib import Path
from typing import Optional

import streamlit as st
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.services.action_items import extract_structured_note
from app.services.gemini_client import LLM_MODEL, client
from app.services.voice_pipeline import transcribe_audio as gemini_transcribe_audio

load_dotenv()

st.set_page_config(page_title="Voice Notes to Action Items", page_icon="🎙️", layout="centered")


def transcribe_audio(audio_bytes: bytes, file_name: str) -> str:
    """Transcribe audio through the configured Gemini model."""
    suffix = Path(file_name).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
        audio_file.write(audio_bytes)
        temp_path = Path(audio_file.name)
    try:
        return gemini_transcribe_audio(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)


def process_transcript(transcript: str) -> str:
    """Extract Gemini's structured result and render it as readable markdown."""
    result = extract_structured_note(transcript)
    discussion_points = "\n".join(f"- {point}" for point in result.key_takeaways)
    action_items = "\n".join(
        f"- **{item.task}** (Assignee: {item.assignee}; Deadline: {item.deadline}; Priority: {item.priority})"
        for item in result.action_items
    )
    return (
        f"## TL;DR\n{result.summary}\n\n"
        f"## Core Discussion Points\n{discussion_points or '- None identified'}\n\n"
        f"## Action Items\n{action_items or '- No concrete action items identified'}"
    )


def create_pdf(transcript: str, summary: str) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
    )
    styles = getSampleStyleSheet()
    story = [Paragraph("Voice Notes to Action Items", styles["Title"]), Spacer(1, 12)]
    for line in summary.splitlines():
        if line.startswith("## "):
            story.append(Paragraph(line[3:], styles["Heading2"]))
        elif line.startswith("- "):
            story.append(Paragraph(f"• {line[2:]}", styles["BodyText"]))
        elif line.strip():
            story.append(Paragraph(line, styles["BodyText"]))
        story.append(Spacer(1, 4))
    story.extend([Spacer(1, 12), Paragraph("Raw Transcript", styles["Heading2"])])
    for paragraph in transcript.splitlines() or [transcript]:
        story.append(Paragraph(paragraph, styles["BodyText"]))
        story.append(Spacer(1, 4))
    document.build(story)
    return output.getvalue()


st.title("🎙️ Voice Notes to Action Items")
st.caption("Turn a short voice memo into a clear summary and a practical task list.")

with st.sidebar:
    st.header("Connection")
    if os.getenv("GEMINI_API_KEY", "").strip():
        st.success("Gemini connected")
        st.caption(f"Transcription and analysis use {LLM_MODEL}.")
    else:
        st.error("Gemini key not found")
        st.caption("Add GEMINI_API_KEY to .env before processing a recording.")

input_mode = st.radio("Audio source", ["Record Audio", "Upload File"], horizontal=True)
audio_bytes: Optional[bytes] = None
file_name = "recording.wav"

if input_mode == "Record Audio":
    recording = st.audio_input("Record your memo")
    if recording:
        audio_bytes = recording.getvalue()
        file_name = "recording.wav"
else:
    uploaded = st.file_uploader("Upload an audio memo", type=["mp3", "wav", "m4a"])
    if uploaded:
        audio_bytes = uploaded.getvalue()
        file_name = uploaded.name

if audio_bytes:
    st.audio(audio_bytes)
    if st.button("Transcribe and Generate Action Items", type="primary", use_container_width=True):
        try:
            with st.spinner("Transcribing audio..."):
                transcript = transcribe_audio(audio_bytes, file_name)
            if not transcript:
                st.error("No speech was detected. Please record or upload a clearer audio memo.")
                st.stop()
            with st.spinner("Extracting summary and action items..."):
                summary = process_transcript(transcript)
            st.session_state.transcript = transcript
            st.session_state.summary = summary
        except Exception as exc:
            st.error(f"Processing failed: {exc}")

if st.session_state.get("summary"):
    st.divider()
    summary_tab, transcript_tab = st.tabs(["Summary & Tasks", "Raw Transcript"])
    with summary_tab:
        st.markdown(st.session_state.summary)
        st.download_button(
            "Download PDF",
            data=create_pdf(st.session_state.transcript, st.session_state.summary),
            file_name="voice_action_items.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with transcript_tab:
        st.text_area("Transcript", st.session_state.transcript, height=260, disabled=True)
else:
    st.info("Record or upload a memo to get started.")
