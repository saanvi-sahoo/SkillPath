"""
Build the complete SkillPath AI implementation report as one PDF.

    python docs/build_pdf_report.py            # -> reports/SkillPath_AI_Implementation_Report.pdf

Part A: implementation summary (written here, numbers from docs/experiment_log.md).
Part B: every document in docs/ rendered as a chapter (markdown -> PDF: headings, lists, tables, code).
Re-run after any docs change; the PDF is regenerated from the current files.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Preformatted,
                                Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = ROOT / "reports" / "SkillPath_AI_Implementation_Report.pdf"

# ── fonts (Unicode coverage for arrows, ≥, ×, —, …) ─────────────────────────────
FONT_DIR = Path("/System/Library/Fonts/Supplemental")
try:
    pdfmetrics.registerFont(TTFont("UI", str(FONT_DIR / "Arial Unicode.ttf")))
    pdfmetrics.registerFont(TTFont("UI-Bold", str(FONT_DIR / "Arial Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Mono", str(FONT_DIR / "Courier New.ttf")))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("UI", normal="UI", bold="UI-Bold", italic="UI", boldItalic="UI-Bold")
    BASE, BOLD, MONO = "UI", "UI-Bold", "Mono"
except Exception:  # non-macOS fallback
    BASE, BOLD, MONO = "Helvetica", "Helvetica-Bold", "Courier"

INK, MUTED, ACCENT, LINE, SOFT = colors.HexColor("#1F2933"), colors.HexColor("#52606D"), colors.HexColor("#1D4ED8"), \
    colors.HexColor("#CBD2D9"), colors.HexColor("#F1F5F9")

ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("title", fontName=BOLD, fontSize=30, leading=36, textColor=INK, alignment=TA_CENTER),
    "subtitle": ParagraphStyle("subtitle", fontName=BASE, fontSize=14, leading=20, textColor=MUTED, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", fontName=BOLD, fontSize=20, leading=25, textColor=INK, spaceBefore=4, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=14, leading=18, textColor=ACCENT, spaceBefore=12, spaceAfter=6),
    "h3": ParagraphStyle("h3", fontName=BOLD, fontSize=11.5, leading=15, textColor=INK, spaceBefore=8, spaceAfter=4),
    "h4": ParagraphStyle("h4", fontName=BOLD, fontSize=10.5, leading=14, textColor=MUTED, spaceBefore=6, spaceAfter=3),
    "body": ParagraphStyle("body", fontName=BASE, fontSize=9.6, leading=13.6, textColor=INK, spaceAfter=5),
    "bullet": ParagraphStyle("bullet", fontName=BASE, fontSize=9.6, leading=13.4, textColor=INK, spaceAfter=2),
    "quote": ParagraphStyle("quote", fontName=BASE, fontSize=9.4, leading=13, textColor=INK, backColor=SOFT,
                            borderColor=ACCENT, borderWidth=0, borderPadding=6, leftIndent=8, spaceBefore=4, spaceAfter=8),
    "cell": ParagraphStyle("cell", fontName=BASE, fontSize=8, leading=10.4, textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName=BOLD, fontSize=8, leading=10.4, textColor=colors.white),
    "code": ParagraphStyle("code", fontName=MONO, fontSize=7.4, leading=9.4, textColor=INK, backColor=SOFT,
                           borderPadding=5, leftIndent=4, rightIndent=4, spaceBefore=3, spaceAfter=8),
    "caption": ParagraphStyle("caption", fontName=BASE, fontSize=8, leading=10, textColor=MUTED, spaceAfter=2),
    "toc1": ParagraphStyle("toc1", fontName=BOLD, fontSize=10.5, leading=15, leftIndent=0),
    "toc2": ParagraphStyle("toc2", fontName=BASE, fontSize=9, leading=12.5, leftIndent=14, textColor=MUTED),
}

EMOJI = {"✅": "[done]", "🟡": "[partial]", "⛔": "[blocked]", "⬜": "[todo]", "👍": "thumbs-up", "👎": "thumbs-down",
         "⚠️": "Warning:", "⚠": "Warning:", "🙂": "", "😊": "", "🎓": "", "🔑": "", "✓": "✓"}


def clean(text: str) -> str:
    for k, v in EMOJI.items():
        text = text.replace(k, v)
    text = text.replace("️", "")
    return "".join(ch for ch in text if ord(ch) <= 0xFFFF)  # drop remaining emoji (non-BMP)


def inline(text: str) -> str:
    """markdown inline -> reportlab mini-HTML."""
    text = clean(text)
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep, text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<link href="{m.group(2)}" color="#1D4ED8">{m.group(1)}</link>'
                  if m.group(2).startswith("http") else m.group(1), text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"(?<![\w/\"=])(https?://[^\s<)\]]+)", r'<link href="\1" color="#1D4ED8">\1</link>', text)
    for i, c in enumerate(codes):
        c = c.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00{i}\x00", f'<font name="{MONO}" size="8.2" color="#9A3412">{c}</font>')
    return text


def make_table(rows, width):
    rows = [[clean(c.strip()) for c in r.strip().strip("|").split("|")] for r in rows]
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c.strip()) for c in r if c.strip())]
    if not rows:
        return None
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    lens = [max(max(min(len(r[i]), 60) for r in rows), max((len(w) for w in r0.split()), default=0) + 1, 6) + 4 for i, r0 in ((i, rows[0][i]) for i in range(ncol))]
    widths = [width * l / sum(lens) for l in lens]
    data = [[Paragraph(inline(c), S["cellh"] if ri == 0 else S["cell"]) for c in r] for ri, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334E68")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def markdown_flowables(md: str, width: float, chapter_title: str | None = None):
    out, para, lines, i = [], [], md.splitlines(), 0

    def flush():
        if para:
            out.append(Paragraph(inline(" ".join(para)), S["body"]))
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("```"):
            flush()
            lang = s[3:].strip()
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(clean(lines[i]))
                i += 1
            if lang == "mermaid":
                out.append(Paragraph("Diagram (Mermaid source; renders as a flowchart on GitHub):", S["caption"]))
            wrapped = []
            for b in block:
                while len(b) > 118:
                    wrapped.append(b[:118])
                    b = "    " + b[118:]
                wrapped.append(b)
            out.append(Preformatted("\n".join(wrapped) or " ", S["code"]))
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            t = make_table(rows, width)
            if t:
                out += [t, Spacer(1, 7)]
            continue
        elif re.match(r"^#{1,4}\s", s):
            flush()
            level = len(s) - len(s.lstrip("#"))
            text = s[level:].strip()
            if level == 1:
                if chapter_title is None:
                    out.append(Paragraph(inline(text), S["h1"]))
            else:
                out.append(Paragraph(inline(text), S[f"h{min(level, 4)}"]))
        elif re.match(r"^\s*([-*]|\d+[.)])\s+", line):
            flush()
            indent = len(line) - len(line.lstrip())
            m = re.match(r"^\s*([-*]|\d+[.)])\s+(.*)", line)
            marker = "•" if m.group(1) in "-*" else m.group(1)
            text = m.group(2)
            while i + 1 < len(lines) and lines[i + 1].startswith(" " * (indent + 2)) and lines[i + 1].strip() \
                    and not re.match(r"^\s*([-*]|\d+[.)])\s+", lines[i + 1]) and not lines[i + 1].strip().startswith(("|", "```")):
                i += 1
                text += " " + lines[i].strip()
            out.append(Paragraph(inline(text), S["bullet"], bulletText=marker) if False else
                       Paragraph(f"{marker}&nbsp;&nbsp;{inline(text)}",
                                 ParagraphStyle("b", parent=S["bullet"], leftIndent=12 + indent * 5, firstLineIndent=-10)))
        elif s.startswith(">"):
            flush()
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip()[1:].strip())
                i += 1
            out.append(Paragraph(inline(" ".join(q)), S["quote"]))
            continue
        elif s == "---":
            flush()
            out.append(Spacer(1, 4))
        elif not s:
            flush()
        else:
            para.append(s)
        i += 1
    flush()
    return out


class Doc(BaseDocTemplate):
    def __init__(self, path, **kw):
        super().__init__(str(path), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=2 * cm,
                         bottomMargin=1.8 * cm, title="SkillPath AI - Implementation Report", author="SkillPath AI team", **kw)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate("cover", [frame], onPage=lambda c, d: None),
                               PageTemplate("main", [frame], onPage=self._decorate)])

    def _decorate(self, c, d):
        c.saveState()
        c.setFont(BASE, 7.5)
        c.setFillColor(MUTED)
        c.drawString(self.leftMargin, A4[1] - 1.25 * cm, "SkillPath AI · Implementation Report")
        c.drawRightString(A4[0] - self.rightMargin, A4[1] - 1.25 * cm, date.today().strftime("%d %B %Y"))
        c.drawRightString(A4[0] - self.rightMargin, 1.0 * cm, f"Page {d.page}")
        c.setStrokeColor(LINE)
        c.line(self.leftMargin, A4[1] - 1.4 * cm, A4[0] - self.rightMargin, A4[1] - 1.4 * cm)
        c.restoreState()

    def afterFlowable(self, f):
        if isinstance(f, Paragraph) and getattr(f, "_toc", None) is not None:
            level, text = f._toc
            key = f"k{id(f)}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(re.sub("<[^>]+>", "", text), key, level=level, closed=level > 0)
            self.notify("TOCEntry", (level, re.sub("<[^>]+>", "", text), self.page, key))


def heading(text, level):
    p = Paragraph(inline(text), S["h1"] if level == 0 else S["h2"])
    p._toc = (level, inline(text))
    return p


def summary_part(width):
    f = []
    T = lambda rows: make_table(["| " + " | ".join(r) + " |" for r in rows], width)  # noqa: E731
    f.append(heading("Part A · Implementation summary", 0))
    f.append(Paragraph("What SkillPath AI is, what was built, and the measured results. Every number below comes from "
                       "a saved report in <font name='%s'>reports/</font> and is traced in the experiment log (Part B)." % MONO, S["body"]))

    f.append(heading("1. Outcome in one page", 1))
    for b in [
        "<b>Product.</b> A career &amp; study advisor for students. Resume + job-description analysis (skills, exact skill gaps, ATS estimate, live LinkedIn/Naukri jobs, learning resources), a <b>career/study-only RAG chatbot</b>, and a <b>validated 30-day roadmap</b>.",
        "<b>Data.</b> Source of truth: the Emerging-Tech Career dataset (2,900 × 13). Audited, 1 junk title excluded, placeholder salaries flagged → <b>2,899 career vectors</b>, plus 37 curated guide sections and 153 jobs.",
        "<b>Embeddings &amp; RAG.</b> all-MiniLM-L6-v2 (chosen on a labelled benchmark) + <b>cross-encoder re-ranking</b>: career precision P@5 <b>0.767 → 0.858</b>, guide Hit@3 <b>0.90 → 0.967</b>.",
        "<b>Vector database.</b> <b>MongoDB Atlas Vector Search</b> (skillpath_ai: careers, knowledge+jobs, private profiles), with a least-privilege cloud user, a local fallback and a circuit breaker.",
        "<b>Chatbot.</b> Scope router (regex → kNN → LLM), question profiler, per-question answer contract, citations, self-check and revision (v6), a learning loop from thumbs-up/thumbs-down feedback, a question queue, bring-your-own-key.",
        "<b>Prompt training.</b> 6 prompt versions, each A/B-tested on fixed test sets (65 general + 30 profile/JD cases): pass rate 0.75 (v1) → 1.0 (v4–v6); precision cases 0.667 → 0.889 (v4 → v5).",
        "<b>Runs anywhere.</b> Hosted LLMs, a local Mistral via Ollama, or <b>fully keyless</b> (retrieval-only answers, rule-based analysis). Deployed on Streamlit Community Cloud. 40 automated tests.",
    ]:
        f.append(Paragraph("•&nbsp;&nbsp;" + b, ParagraphStyle("sb", parent=S["bullet"], leftIndent=12, firstLineIndent=-10)))

    f.append(heading("2. Key measured results", 1))
    f.append(T([["Area", "Metric", "Before", "After / final", "Test"],
                ["Career retrieval", "strict Precision@5 (24 labelled queries)", "0.708 (pilot text)", "0.858 (full text + re-rank)", "E11, E35"],
                ["Guide retrieval", "Hit@3 / MRR@5 (30 labelled questions)", "0.900 / 0.842", "0.967 / 0.884", "E35"],
                ["Profile retrieval", "Hit@3 (18 persona questions)", "-", "1.00", "E35"],
                ["Atlas vs exact search", "top-5 overlap", "-", "5/5 (359 ms median)", "E20"],
                ["Scope guardrail", "allow/refuse accuracy (65 cases)", "-", "1.00 (0 false refusals, 0 leaks)", "E34"],
                ["Chatbot answers", "pass rate", "0.75 (v1)", "1.00 (v4-v6)", "E9-E34"],
                ["Answer precision", "item count / length / first-sentence", "0.667 (v4)", "0.889 (v5)", "E32"],
                ["Profile / JD / both questions", "pass rate (30 persona questions)", "0.90 (v4)", "1.00 (v5)", "E33"],
                ["Feedback learning", "behaviour change after feedback", "-", "3/3 tests pass", "E32"],
                ["Keyless mode", "pass rate · tokens · latency", "-", "42/42 · 0 · 0.24 s", "E26"],
                ["Roadmap", "generation time · quality checks", "216 s (local LLM)", "0.7 s · 3/3 personas 7/7 checks", "E33, E35"],
                ["Code quality", "offline automated tests", "0", "40 passing", "tests/"]]))

    f.append(heading("3. Prompt script training: how the chatbot improved", 1))
    f.append(T([["Version", "What changed", "Why", "Result"],
                ["v1", "2-line baseline", "control", "pass 0.75; answered recipes/jokes; 6% citations"],
                ["v2", "role, scope rules, grounding + [S#] citations, few-shots as chat turns", "scope leaks, hallucinated facts", "pass 0.969 but copied few-shot content"],
                ["v3", "few-shots moved into the system prompt as 'fictional users'", "few-shot leakage", "judge relevance 5.0, groundedness 4.72 → activated"],
                ["v4", "project-doc rules: weak evidence → clarifying questions, related ≠ equivalent skills, salary placeholders, untrusted context", "guessing careers from little info", "1.00 vs v3 0.952 (42 paired)"],
                ["v5", "question profiler + per-type retrieval + answer contract + feedback-learned guidance", "answers not matching what was asked", "0.98 vs v4 0.922 (51 paired); precision 0.889 vs 0.667"],
                ["v6", "explicit study/career scope + generate → verify → revise self-check", "paraphrased fit/priority questions", "30/65 pairs: both 1.0, citations 1.0 vs 0.94; full paraphrase A/B in progress"]]))
    f.append(Paragraph("Live configuration: <b>advisor prompt v5</b> (v6 implemented, activation after its paired A/B), <b>router v2</b>, "
                       "MiniLM + re-ranker, MongoDB Atlas. All prompt versions are versioned files in "
                       "<font name='%s'>src/prompts/templates/</font>; nothing is fine-tuned (free-tier LLMs)." % MONO, S["body"]))

    f.append(heading("4. Architecture at a glance", 1))
    f.append(Preformatted(
        "Student (browser) ─► Streamlit UI  ── Career Advisor tab (always on) ──► chatbot.answer()\n"
        "        │                                   │  scope_router: regex → kNN anchors → LLM (career/study only)\n"
        "        │                                   │  question_profile → retrieval quotas + answer contract\n"
        "        │                                   │  retriever: MiniLM query → Atlas $vectorSearch (pool 20) → cross-encoder re-rank\n"
        "        │                                   │  prompt v5/v6 (+ feedback-learned guidance) → LLM → [verify → revise] → cited answer\n"
        "        │                                   └► engines: Groq/Gemini · visitor's own key · local Mistral · retrieval-only\n"
        "        └─ Analyze Profile ─► LangGraph pipeline: parse CV/JD → skills & gaps → LinkedIn/Naukri jobs\n"
        "                                 → web resources → summary → memory + private profile vectors (per visitor)\n"
        "MongoDB Atlas (skillpath_ai): careers_embeddings_v1 (2,899) · knowledge_chunks_v1 (37 guides + 153 jobs)\n"
        "                              · user_profile_chunks_v1 (private, per user) · feedback_v1 (learning)", S["code"]))

    f.append(heading("5. How to run and where everything is", 1))
    f.append(T([["What", "Where / command"],
                ["Run locally (Mistral + Atlas)", "./run_local.sh  →  http://localhost:8501"],
                ["Run like the deployed app (keyless)", "./run_local.sh --keyless  →  http://localhost:8502"],
                ["GitHub repository", "https://github.com/saanvi-sahoo/SkillPath"],
                ["Deployed app", "Streamlit Community Cloud (app URL from share.streamlit.io)"],
                ["Vector database", "MongoDB Atlas project 'SkillPath AI', cluster skillpath-cluster (M0, Mumbai)"],
                ["Tests", "python -m pytest -q tests  (40 offline tests)"],
                ["Benchmarks", "src.eval.rag_benchmark · evaluate_career_retrieval · run_prompt_eval · persona_eval · roadmap_eval · feedback_learning_test"],
                ["Rebuild this PDF", "python docs/build_pdf_report.py"]]))

    f.append(heading("6. Open items", 1))
    for b in ["Finish the v6 vs v5 paired A/B on paraphrased profile/JD questions, then activate v6 if it wins (free-tier quotas limited the run).",
              "LLM-judge pass on the latest answers once a judge model with quota is available.",
              "Grow the held-out test sets from real usage (chat log + feedback) to 100+ questions.",
              "Rotate the credentials that were shared in chat (Groq keys, HF token, account passwords); the Atlas cloud user can be rotated in Atlas → Database Access.",
              "OCR for scanned PDFs; roadmap progress tracking."]:
        f.append(Paragraph("•&nbsp;&nbsp;" + inline(b), ParagraphStyle("ob", parent=S["bullet"], leftIndent=12, firstLineIndent=-10)))
    return f


ORDER = [("README.md", "Documentation index"), ("status.md", "Progress ledger"), ("architecture.md", "Architecture"),
         ("runbook.md", "Runbook: every process"), ("embeddings.md", "Embeddings"), ("rag.md", "RAG design and precision"),
         ("mongodb_atlas_setup.md", "MongoDB Atlas setup"), ("chatbot.md", "Career Advisor chatbot"),
         ("prompt_scripting.md", "Prompt scripting and training"), ("evaluation.md", "Evaluation, prompt training v7-v8 and real-world reliability (E38)"), ("feedback_learning.md", "Feedback learning and precise answers"),
         ("keyless_mode.md", "Keyless mode"), ("byok.md", "Bring your own API key"), ("skills_and_roadmap.md", "Skill gaps and the 30-day roadmap"),
         ("scenarios.md", "Scenarios"), ("deployment.md", "Deployment"), ("roadmap.md", "Project roadmap"),
         ("experiment_log.md", "Experiment log (E0-E37)")]


def build():
    doc = Doc(OUT)
    w = doc.width
    story = [Spacer(1, 5 * cm), Paragraph("SkillPath AI", S["title"]), Spacer(1, 10),
             Paragraph("Implementation Report", ParagraphStyle("t2", parent=S["title"], fontSize=20, leading=26, textColor=ACCENT)),
             Spacer(1, 18),
             Paragraph("Career &amp; study advisor · Embeddings · RAG on MongoDB Atlas · Prompt training · 30-day roadmap", S["subtitle"]),
             Spacer(1, 2.2 * cm),
             Paragraph("Sabudh Foundation internship · Team: Saanvi Sahoo, Amrit Singh, Isa Ahmed Khan · Mentor: Ms. Suparna Dutta", S["subtitle"]),
             Spacer(1, 6), Paragraph(f"Generated {date.today().strftime('%d %B %Y')} from the repository documentation", S["subtitle"]),
             Spacer(1, 6), Paragraph('<link href="https://github.com/saanvi-sahoo/SkillPath" color="#1D4ED8">github.com/saanvi-sahoo/SkillPath</link>', S["subtitle"]),
             PageBreak()]
    from reportlab.platypus import NextPageTemplate
    story.insert(0, NextPageTemplate("main"))
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    story += [Paragraph("Contents", S["h1"]), toc, PageBreak()]
    story += summary_part(w)
    story += [PageBreak(), heading("Part B · Complete documentation", 0),
              Paragraph("Each chapter below is a document from the repository's <font name='%s'>docs/</font> folder, reproduced in full." % MONO, S["body"])]
    for fname, title in ORDER:
        path = DOCS / fname
        if not path.exists():
            continue
        story += [PageBreak(), heading(title, 1), Paragraph(f"Source: docs/{fname}", S["caption"])]
        story += markdown_flowables(path.read_text(encoding="utf-8"), w, chapter_title=title)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.multiBuild(story)
    return OUT


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size / 1024:.0f} KB)")
