import io
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Union
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def create_pdf_report(data: Dict[str, Any], output_path: Union[Path, str]) -> Path:
    """Generate a clean executive PDF report for single or batch voice note action items."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=15
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155')
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#334155'),
        leftIndent=15
    )

    task_style = ParagraphStyle(
        'TaskText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#0F172A')
    )

    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#64748B')
    )

    story = []

    # Header section
    doc_title = data.get("title") or data.get("master_summary_title") or "Voice Notes → Action Items Report"
    story.append(Paragraph(doc_title, title_style))
    date_str = datetime.now().strftime("%B %d, %Y - %I:%M %p")
    story.append(Paragraph(f"Generated on {date_str} | AI Audio Intelligence Report", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#6366F1'), spaceAfter=15))

    # Master / Primary Summary Box
    summary_text = data.get("summary") or data.get("master_summary") or "No summary provided."
    story.append(Paragraph("Executive Summary", section_heading))
    
    summary_p = Paragraph(f"<i>{summary_text}</i>", body_style)
    summary_table = Table([[summary_p]], colWidths=[letter[0] - 80])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 15))

    # Key Takeaways if available
    takeaways = data.get("key_takeaways", [])
    if takeaways:
        story.append(Paragraph("Key Takeaways", section_heading))
        for point in takeaways:
            story.append(Paragraph(f"• {point}", bullet_style))
        story.append(Spacer(1, 15))

    # Action Items Table
    action_items = data.get("action_items") or data.get("master_action_items") or []
    if action_items:
        story.append(Paragraph(f"Action Items ({len(action_items)} Tasks)", section_heading))

        table_data = [
            [
                Paragraph("<b>Status</b>", meta_style),
                Paragraph("<b>Task & Context</b>", meta_style),
                Paragraph("<b>Priority</b>", meta_style),
                Paragraph("<b>Category</b>", meta_style),
                Paragraph("<b>Deadline / Assignee</b>", meta_style),
            ]
        ]

        for item in action_items:
            task_desc = item.get("task", "") if isinstance(item, dict) else item.task
            prio = (item.get("priority") if isinstance(item, dict) else item.priority) or "Medium"
            cat = (item.get("category") if isinstance(item, dict) else item.category) or "General"
            assignee = (item.get("assignee") if isinstance(item, dict) else item.assignee) or "Self"
            deadline = (item.get("deadline") if isinstance(item, dict) else item.deadline) or "N/A"
            status = (item.get("status") if isinstance(item, dict) else item.status) or "Pending"

            chk_symbol = "[ ✓ ]" if status.lower() == "completed" else "[   ]"
            
            prio_color = "#EF4444" if prio.lower() == "high" else "#F59E0B" if prio.lower() == "medium" else "#3B82F6"
            prio_paragraph = Paragraph(f"<font color='{prio_color}'><b>{prio}</b></font>", body_style)

            meta_info = f"{deadline}<br/><font color='#94A3B8'>Assignee: {assignee}</font>"

            table_data.append([
                Paragraph(f"<b>{chk_symbol}</b>", body_style),
                Paragraph(task_desc, task_style),
                prio_paragraph,
                Paragraph(cat, body_style),
                Paragraph(meta_info, meta_style)
            ])

        t = Table(table_data, colWidths=[0.6 * inch, 3.5 * inch, 0.9 * inch, 0.9 * inch, 1.3 * inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8FAFC')),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 15))

    # Transcript section if single note
    transcript = data.get("transcript")
    if transcript:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Verbatim Transcript", section_heading))
        t_paragraph = Paragraph(f"<font color='#475569'>{transcript}</font>", body_style)
        t_table = Table([[t_paragraph]], colWidths=[letter[0] - 80])
        t_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FAFAFA')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        story.append(t_table)

    # Batch Individual Notes section if batch
    individual_notes = data.get("individual_notes", [])
    if individual_notes:
        story.append(Spacer(1, 15))
        story.append(Paragraph("Individual Note Breakdown", section_heading))
        for idx, note in enumerate(individual_notes, 1):
            n_title = note.get("title") if isinstance(note, dict) else note.title
            n_summary = note.get("summary") if isinstance(note, dict) else note.summary
            n_filename = note.get("filename") if isinstance(note, dict) else getattr(note, 'filename', '')
            
            note_content = [
                Paragraph(f"<b>Note #{idx}: {n_title}</b> ({n_filename or 'Audio'})", task_style),
                Spacer(1, 3),
                Paragraph(n_summary, body_style),
                Spacer(1, 6)
            ]
            story.append(KeepTogether(note_content))

    doc.build(story)
    return output_path
