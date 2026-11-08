"""E35: retrieval upgrades + roadmap specificity (offline). Run: python -m pytest -q tests"""


def test_bm25_ranks_exact_term_match_first():
    from src.rag.hybrid import BM25, tokens
    docs = [tokens(t) for t in ["Power BI PL-300 certification exam", "Tableau dashboards for analysts", "Docker containers"]]
    s = BM25(docs).scores(tokens("PL-300 exam"))
    assert s.argmax() == 0 and s[2] == 0


def test_rrf_rewards_agreement_between_rankings():
    from src.rag.hybrid import rrf
    a = [{"id": "x"}, {"id": "y"}, {"id": "z"}]
    b = [{"id": "y"}, {"id": "x"}, {"id": "w"}]
    order = [h["id"] for h in rrf([a, b])]
    assert set(order[:2]) == {"x", "y"} and order[-1] in {"z", "w"}


def test_capstone_is_role_specific():
    from src.roadmap.syllabus import capstone_for
    assert "dashboard" in capstone_for("Data Analyst", ["Tableau"])
    assert "REST service" in capstone_for("Backend Developer", ["Docker"])
    assert "model" in capstone_for("Machine Learning Engineer", ["TensorFlow"])
    assert capstone_for("Chef", []).startswith("Portfolio project for Chef")


def test_template_roadmap_has_resources_and_real_topics(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    from src.roadmap import generator
    monkeypatch.setattr(generator, "market_importance", lambda gaps, role, k=25: {g: 0.5 for g in gaps})
    r = generator.generate_roadmap("Data Analyst", ["Python"], gaps=["SQL", "Tableau"], daily_minutes=60)
    learn = [d for d in r["days"] if d["kind"] == "learn"]
    assert r["validation"]["valid"] and all(d["resources"] for d in learn)
    assert not any(" - part " in d["topic"] for d in learn) and "dashboard" in r["capstone"]
    assert [d["topic"] for d in r["days"] if d["kind"] == "project"] == ["Capstone: plan & build", "Capstone: polish & present"]


def test_rerank_cutoff_configured():
    from src.rag import config
    assert config.RAG_RERANK and config.RERANK_MIN == -6.0 and "careers" in config.RERANK_SOURCES
