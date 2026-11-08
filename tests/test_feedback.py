"""Prompt v5 precision + feedback learning + UI regression tests (offline). Run: python -m pytest -q tests"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_question_profile_types_and_constraints():
    from src.backend.question_profile import profile_question as p
    assert p("What is my ATS score?")["type"] == "profile_fact"
    assert p("How can I make my resume ATS friendly?")["type"] == "how_to"
    assert p("Difference between data analyst and data scientist?")["type"] == "comparison"
    q = p("Give me 3 certifications for cloud")
    assert q["type"] == "list" and q["n_items"] == 3
    assert p("In one sentence, what does a business analyst do?")["max_words"] == 40
    assert p("List five free courses for Power BI in a table")["format"] == "table"
    assert p("What salary does a Big Data Engineer get?")["type"] == "salary"


def test_answer_contract_mentions_constraints():
    from src.backend.question_profile import answer_contract, profile_question
    c = answer_contract(profile_question("Give me 3 certifications for cloud"))
    assert "exactly 3" in c and "FIRST sentence" in c


def test_relevance_filter_drops_far_below_best():
    from src.backend.chatbot import _relevance_filter
    hits = [{"source": "careers", "score": 0.70}, {"source": "careers", "score": 0.50},
            {"source": "knowledge", "score": 0.40}]
    kept = _relevance_filter(hits)
    assert {"source": "careers", "score": 0.50} not in kept and {"source": "knowledge", "score": 0.40} in kept


def _isolated_store(tmp_path, monkeypatch):
    from src.backend import feedback_store as fs
    monkeypatch.setattr(fs, "LOCAL_FILE", tmp_path / "fb.jsonl")
    monkeypatch.setattr(fs, "_mongo", lambda: None)
    fs._cache.update(t=0.0, rows=None)
    return fs


def test_feedback_guidance_from_similar_questions(tmp_path, monkeypatch):
    fs = _isolated_store(tmp_path, monkeypatch)
    fs.record("Which certification should I do for Power BI?", "bad answer", "down", "u1",
              reason="not_answered", comment="name the PL-300 exam")
    fs.record("Which certification should I do for Power BI?", "great answer", "up", "u2")
    g = fs.learned_guidance("What is the best certification for Power BI?", "u3")
    assert g["n_bad"] == 1 and g["n_good"] == 1 and "PL-300" in g["avoid"] and "great answer" in g["examples"]
    assert fs.learned_guidance("How do I cook pasta?", "u3")["n_similar"] == 0  # unrelated -> nothing


def test_profile_specific_feedback_not_shared_across_users(tmp_path, monkeypatch):
    fs = _isolated_store(tmp_path, monkeypatch)
    fs.record("What is my ATS score?", "Your ATS is 70", "up", "alice")
    assert fs.learned_guidance("What is my ATS score?", "bob")["n_similar"] == 0
    assert fs.learned_guidance("What is my ATS score?", "alice")["n_similar"] == 1


def test_wrong_refusal_needs_two_distinct_users(tmp_path, monkeypatch):
    fs = _isolated_store(tmp_path, monkeypatch)
    q = "How do I make friends in a new college?"
    fs.record(q, "refused", "down", "u1", reason="wrong_refusal")
    fs.record(q, "refused", "down", "u1", reason="wrong_refusal")  # same user twice: not enough
    assert fs.learned_scope_anchors() == []
    fs.record(q, "refused", "down", "u2", reason="wrong_refusal")
    assert fs.learned_scope_anchors() == [q]


def test_frontend_has_no_bare_non_call_expressions_and_no_resume_builder():
    """E32: a bare `a if c else b` expression was 'magic'-displayed and crashed on Python 3.14."""
    for f in ("src/frontend/frontend.py", "src/frontend/advisor_ui.py", "src/frontend/byok_ui.py"):
        tree = ast.parse((ROOT / f).read_text())
        bad = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Expr)
               and not isinstance(n.value, ast.Call)
               and not (isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        assert bad == [], f"{f}: bare expressions at lines {bad}"
    assert "Resume Builder" not in (ROOT / "src/frontend/frontend.py").read_text()
    assert "magicEnabled = false" in (ROOT / ".streamlit/config.toml").read_text()
