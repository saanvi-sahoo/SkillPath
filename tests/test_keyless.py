"""Offline tests for keyless mode + per-user isolation (no LLM / network). Run: python -m pytest -q tests"""
import pytest

from src.rag import config


def test_provider_resolution(monkeypatch):
    from src.utilities import llm_provider as lp
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert lp.llm_provider() == "none" and "Retrieval-only" in lp.provider_label()
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert lp.llm_provider() == "api"
    monkeypatch.delenv("GROQ_API_KEY"); monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(lp, "ollama_available", lambda ttl_s=60: False)
    assert lp.llm_provider() == "none"


def test_robust_llm_raises_when_no_generator(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    from src.utilities.brain import get_robust_llm
    from src.utilities.llm_provider import LLMUnavailable
    with pytest.raises(LLMUnavailable):
        get_robust_llm()


def test_rule_based_analysis_matches_expected_gaps():
    from src.skills.extractor import rule_based_analysis
    r = rule_based_analysis("Skills: Python, Excel, SQL, Pandas. Built a Power BI dashboard.",
                            "Data Analyst: Python, SQL, Power BI, Tableau, statistics, data visualization, communication")
    assert {"Tableau", "Statistics", "Data Visualization", "Communication"} <= set(r["skill_gaps"])
    assert "Python" not in r["skill_gaps"] and 0 <= r["ats_score"] <= 100 and r["analysis_method"] == "rule_based"
    assert len(r["learning_path"]) == len(r["skill_gaps"])


def test_extractor_avoids_ambiguous_words():
    from src.skills.extractor import extract_skills
    found = extract_skills("I go to the gym and excel at teamwork. Strong REST APIs and Kubernetes.")
    assert "Go" not in found and "REST APIs" in found and "Kubernetes" in found


def _hit(i, source, doc_type, text, **meta):
    return {"id": f"h{i}", "source": source, "doc_type": doc_type, "text": text, "score": 0.6, "metadata": meta}


def test_extractive_answer_clarifies_vague_request():
    from src.backend.extractive_answer import compose_answer
    hits = [_hit(1, "careers", "career_profile", "Career: X", career_name="X", domain="D", required_skills="A, B")]
    out = compose_answer("Recommend a career for me", {"label": "career_study"}, hits, None)
    assert out.count("?") >= 2 and "Career: X" not in out


def test_extractive_answer_cites_and_compares_skills():
    from src.backend.extractive_answer import compose_answer
    hits = [_hit(1, "careers", "career_profile", "Career: Data Analyst", career_name="Data Analyst",
                 domain="Data Analysis and BI", required_skills="SQL, Python, Tableau")]
    out = compose_answer("Which career fits me?", {"label": "career_study"}, hits, {"candidate_skills": ["Python", "SQL"]})
    assert "[S1]" in out and "You already have: SQL, Python" in out and "To learn: Tableau" in out


def test_extractive_equivalence_rules():
    from src.backend.extractive_answer import compose_answer
    out = compose_answer("Does Docker cover the Kubernetes requirement?", {"label": "career_study"}, [], None)
    assert "related but not the same" in out
    out2 = compose_answer("Does MySQL cover SQL?", {"label": "career_study"}, [], None)
    assert out2.startswith("**Yes:**")


def test_memory_path_is_per_user_and_sanitised():
    assert config.memory_path(None) == config.MEMORY_JSON
    p = config.memory_path("../../etc/passwd")
    assert p.parent == config.USER_MEMORY_DIR and ".." not in p.name and "/" not in p.name
    assert config.memory_path("alice") != config.memory_path("bob")
