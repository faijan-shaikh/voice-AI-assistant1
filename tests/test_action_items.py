import os
from pathlib import Path
# pyrefly: ignore [missing-import]
import pytest
from app.services.action_items import ActionItem, VoiceNoteResult, process_voice_note_text
from app.services.pdf_exporter import create_pdf_report

def test_action_item_model():
    item = ActionItem(
        task="Finish report",
        priority="High",
        category="Work",
        assignee="Self",
        deadline="Today"
    )
    assert item.task == "Finish report"
    assert item.priority == "High"
    assert item.status == "Pending"
    assert item.id.startswith("task_")

def test_voice_note_result_model():
    note = VoiceNoteResult(
        title="Team Standup",
        transcript="We discussed Q3 goals.",
        summary="Summary of Q3 goals.",
        key_takeaways=["Goal 1", "Goal 2"],
        action_items=[
            ActionItem(task="Deploy feature", priority="High")
        ],
        sentiment="Productive"
    )
    assert note.title == "Team Standup"
    assert len(note.action_items) == 1
    assert note.action_items[0].task == "Deploy feature"

def test_pdf_report_generation(tmp_path):
    output_pdf = tmp_path / "test_report.pdf"
    test_data = {
        "title": "Test Voice Note Summary",
        "summary": "This is a test summary for PDF generation.",
        "key_takeaways": ["Takeaway 1", "Takeaway 2"],
        "action_items": [
            {
                "task": "Review API endpoints",
                "priority": "High",
                "category": "Tech",
                "assignee": "Self",
                "deadline": "Today",
                "status": "Pending"
            },
            {
                "task": "Update documentation",
                "priority": "Medium",
                "category": "Docs",
                "assignee": "Team",
                "deadline": "Tomorrow",
                "status": "Completed"
            }
        ],
        "transcript": "Test verbatim transcript for PDF verification."
    }

    generated_path = create_pdf_report(test_data, output_pdf)
    assert generated_path.exists()
    assert generated_path.stat().st_size > 0

def test_live_text_extraction():
    memo = "Please remember to schedule the team sync meeting for tomorrow at 10 AM, send the budget report to John by Friday, and update the API documentation."
    result = process_voice_note_text(memo)
    assert result.title
    assert result.summary
    assert len(result.action_items) > 0
    print(f"Extracted Title: {result.title}")
    print(f"Extracted Action Items: {[t.task for t in result.action_items]}")
