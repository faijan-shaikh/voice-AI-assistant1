import json
import re
import time
from pathlib import Path
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field
from google.genai import types
from google.genai.errors import APIError
from app.services.gemini_client import client, LLM_MODEL
from app.services.voice_pipeline import transcribe_audio

class ActionItem(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{uuid4().hex[:8]}")
    task: str
    priority: str = "Medium"  # High, Medium, Low
    category: str = "General"  # Work, Personal, Meeting, Follow-up, Tech, etc.
    assignee: str = "Self"
    deadline: str = "N/A"
    status: str = "Pending"  # Pending, Completed

class VoiceNoteResult(BaseModel):
    id: str = Field(default_factory=lambda: f"note_{uuid4().hex[:8]}")
    title: str
    transcript: str
    summary: str
    key_takeaways: List[str] = Field(default_factory=list)
    action_items: List[ActionItem] = Field(default_factory=list)
    sentiment: str = "Neutral"
    audio_url: Optional[str] = None
    filename: Optional[str] = None

class BatchProcessingResult(BaseModel):
    individual_notes: List[VoiceNoteResult] = Field(default_factory=list)
    master_summary: str
    master_action_items: List[ActionItem] = Field(default_factory=list)
    total_recordings: int = 0

ACTION_ITEMS_PROMPT = """
You are an expert AI assistant specializing in converting voice memos and rambling audio notes into structured, actionable intelligence.

Analyze the following transcript carefully:
---
[[TRANSCRIPT]]
---

Your task:
1. Provide a concise, professional Title summarizing the note's subject.
2. Provide a clean, readable Summary (2-4 sentences max).
3. Extract Key Takeaways (3-5 important facts or bullet points).
4. Extract Action Items. For each action item, identify:
   - task: Clear, verb-first statement of what needs to be done.
   - priority: "High", "Medium", or "Low".
   - category: e.g., "Work", "Personal", "Meeting", "Follow-up", "Tech", "Study", etc.
   - assignee: Person responsible (e.g. "Self", "Alex", "Team", "N/A").
   - deadline: Timeframe or due date if mentioned (e.g., "Today", "Friday", "Next week", "ASAP", "N/A").
5. Identify overall Sentiment/Tone (e.g. "Urgent", "Productive", "Brainstorming", "Casual", "Reflective").

Return ONLY valid JSON matching this exact structure (no commentary, markdown formatting outside JSON):
{
  "title": "Title here",
  "summary": "Summary here",
  "key_takeaways": ["Point 1", "Point 2"],
  "action_items": [
    {
      "task": "Task description",
      "priority": "High",
      "category": "Work",
      "assignee": "Self",
      "deadline": "Today"
    }
  ],
  "sentiment": "Productive"
}
"""

MASTER_BATCH_PROMPT = """
You are an executive AI assistant consolidating multiple voice notes recorded throughout the day or project.

Below are transcripts and summaries of [[COUNT]] voice notes:

[[NOTES_CONTEXT]]

Your task:
1. Create a Master Consolidated Summary synthesizing all key ideas and updates into a cohesive executive overview.
2. Create a Unified Master Action Items List deduplicating and organizing all tasks across all notes by priority.

Return ONLY valid JSON matching this exact structure:
{
  "master_summary": "Unified overview across all notes...",
  "master_action_items": [
    {
      "task": "Action item description",
      "priority": "High",
      "category": "Work",
      "assignee": "Self",
      "deadline": "ASAP"
    }
  ]
}
"""

def _clean_json_string(raw_text: str) -> str:
    """Extract raw JSON text even if wrapped in ```json ... ``` code blocks."""
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()

def _generate_with_retry(prompt: str, config: types.GenerateContentConfig):
    """Execute generate_content with retry/fallback for 429 Rate Limits."""
    models_to_try = [LLM_MODEL, "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-1.5-flash"]
    last_err = None
    
    for model_name in models_to_try:
        for attempt in range(3):
            try:
                return client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
            except Exception as e:
                last_err = e
                err_msg = str(e).lower()
                if "429" in err_msg or "resource_exhausted" in err_msg:
                    print(f"Rate limited on {model_name}. Retrying in {3 * (attempt + 1)}s...")
                    time.sleep(3 * (attempt + 1))
                else:
                    break  # Try next model if non-rate-limit error
    
    raise last_err

def extract_structured_note(transcript: str, note_id: Optional[str] = None) -> VoiceNoteResult:
    """Send transcript to Gemini LLM to extract title, summary, key takeaways, and structured action items."""
    prompt = ACTION_ITEMS_PROMPT.replace("[[TRANSCRIPT]]", transcript)
    config = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json",
    )
    
    try:
        response = _generate_with_retry(prompt, config)
        raw_json = _clean_json_string(response.text or "{}")
        data = json.loads(raw_json)
    except Exception as e:
        print(f"Fallback parsing due to model error: {e}")
        # Rule-based fallback parsing for offline/rate-limit resilience
        sentences = [s.strip() for s in transcript.split(".") if s.strip()]
        data = {
            "title": "Voice Note Summary",
            "summary": transcript[:200] + "..." if len(transcript) > 200 else transcript,
            "key_takeaways": sentences[:3] if sentences else [transcript],
            "action_items": [
                {
                    "task": s,
                    "priority": "Medium",
                    "category": "Follow-up",
                    "assignee": "Self",
                    "deadline": "N/A"
                } for s in sentences if any(w in s.lower() for w in ["schedule", "send", "update", "do", "finish", "remember", "submit"])
            ],
            "sentiment": "Productive"
        }
    
    raw_action_items = data.get("action_items", [])
    action_items_objs = []
    for item in raw_action_items:
        if isinstance(item, dict):
            action_items_objs.append(ActionItem(
                task=item.get("task", "Action item"),
                priority=item.get("priority", "Medium"),
                category=item.get("category", "General"),
                assignee=item.get("assignee", "Self"),
                deadline=item.get("deadline", "N/A"),
                status="Pending"
            ))

    return VoiceNoteResult(
        id=note_id or f"note_{uuid4().hex[:8]}",
        title=data.get("title", "Voice Note Summary"),
        transcript=transcript,
        summary=data.get("summary", ""),
        key_takeaways=data.get("key_takeaways", []),
        action_items=action_items_objs,
        sentiment=data.get("sentiment", "Neutral")
    )

def process_voice_note_audio(audio_path: Path) -> VoiceNoteResult:
    """Full end-to-end pipeline: Audio -> Speech-to-Text -> LLM Structured Extraction."""
    transcript = transcribe_audio(audio_path)
    if not transcript:
        raise ValueError("Speech-to-Text conversion yielded empty text.")
    
    result = extract_structured_note(transcript)
    result.filename = audio_path.name
    return result

def process_voice_note_text(text_content: str) -> VoiceNoteResult:
    """Process plain text note into summary + action items."""
    if not text_content.strip():
        raise ValueError("Text content cannot be empty.")
    return extract_structured_note(text_content.strip())

def process_batch_voice_notes(audio_paths: List[Path]) -> BatchProcessingResult:
    """Process multiple voice memo audio files and create individual notes + master consolidated summary."""
    individual_notes: List[VoiceNoteResult] = []
    notes_context_list = []
    
    for idx, path in enumerate(audio_paths, 1):
        try:
            note = process_voice_note_audio(path)
            individual_notes.append(note)
            notes_context_list.append(
                f"--- Recording #{idx} ({path.name}) ---\n"
                f"Title: {note.title}\n"
                f"Transcript: {note.transcript}\n"
                f"Summary: {note.summary}\n"
            )
        except Exception as e:
            print(f"Error processing batch audio {path.name}: {e}")

    if not individual_notes:
        raise RuntimeError("No audio files could be processed successfully in batch.")

    # Generate master consolidated summary
    notes_context = "\n\n".join(notes_context_list)
    master_prompt = MASTER_BATCH_PROMPT.replace("[[COUNT]]", str(len(individual_notes))).replace("[[NOTES_CONTEXT]]", notes_context)
    config = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json",
    )
    
    try:
        master_response = _generate_with_retry(master_prompt, config)
        raw_json = _clean_json_string(master_response.text or "{}")
        master_data = json.loads(raw_json)
    except Exception as e:
        print(f"Master batch fallback: {e}")
        master_data = {
            "master_summary": f"Consolidated Summary across {len(individual_notes)} voice notes.",
            "master_action_items": []
        }

    master_actions = []
    for item in master_data.get("master_action_items", []):
        if isinstance(item, dict):
            master_actions.append(ActionItem(
                task=item.get("task", "Action item"),
                priority=item.get("priority", "Medium"),
                category=item.get("category", "General"),
                assignee=item.get("assignee", "Self"),
                deadline=item.get("deadline", "N/A"),
                status="Pending"
            ))

    # If master prompt didn't yield tasks, combine individual action items
    if not master_actions:
        for note in individual_notes:
            master_actions.extend(note.action_items)

    return BatchProcessingResult(
        individual_notes=individual_notes,
        master_summary=master_data.get("master_summary", "Consolidated Summary of Voice Notes"),
        master_action_items=master_actions,
        total_recordings=len(individual_notes)
    )
