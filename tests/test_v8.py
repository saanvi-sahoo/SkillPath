"""E37 (prompt v8): intent routing, claim-level checks, task contracts, feedback approval, retrieval changes. Offline."""
from src.backend.intent import classify, quotas_for
from src.backend.task_contract import check_v8, contract_v8, roadmap_evidence, sentence_count, url_issues


def c(q, hist=None, prof=False):
    return classify(q, hist or [], prof)


def test_intent_routing_review_examples():
    assert c("What is Docker?")["primary_intent"] == "concept_explanation"
    assert c("Should I learn Docker or Kubernetes first?")["primary_intent"] == "learning_plan"
    assert c("Suggest 3 careers for me.")["requested_count"] == 3
    assert c("Am I ready for a Data Engineer role?")["primary_intent"] == "profile_analysis"
    assert c("Make me a 30-day SQL plan.")["primary_intent"] == "learning_plan"
    assert c("Explain recursion for my exam.")["primary_intent"] == "study_help"
    assert c("What is my ATS score?")["primary_intent"] == "profile_progress"
    multi = c("Compare data science and data engineering, then make me a learning plan.")
    assert multi["primary_intent"] == "career_discovery" and "learning_plan" in multi["secondary_intents"]


def test_source_routing_concepts_never_use_career_records():
    q = quotas_for(c("What is gradient descent?"), has_profile=True)
    assert q.get("careers", 0) == 0 and q.get("profile", 0) == 0
    assert quotas_for(c("Which careers need machine learning?"), has_profile=False).get("careers", 0) >= 3
    assert quotas_for(c("What skills are in my resume?", prof=True), has_profile=True).get("profile", 0) >= 5


def test_constraints_and_conflicts():
    assert c("Explain recursion in Java in exactly three sentences.")["n_sentences"] == 3
    i = c("Explain supervised and unsupervised learning with two examples each.")
    assert i["examples_each"] == 2 and i["requested_count"] is None
    assert c("Explain polymorphism with a Java example")["example_language"] == "java"
    assert c("Give me a one-sentence answer containing 30 daily tasks")["conflict"]
    assert c("Can you guarantee I'll get a job?")["wants_guarantee"]


def test_follow_up_inherits_topic():
    h = [{"role": "user", "content": "Suggest three cybersecurity careers."}, {"role": "assistant", "content": "1. A 2. B 3. C"}]
    i = c("Explain the second one.", h)
    assert i["primary_intent"] == "career_discovery" and i["refers_to_history"]


def test_contract_lists_every_part():
    con = contract_v8(c("Compare data science and data engineering, then make me a learning plan."))
    assert "(1)" in con and "(2)" in con


def test_checks_sentences_guarantee_urls():
    i = c("Explain recursion in Java in exactly three sentences.")
    assert any("exactly 3 sentences" in x for x in check_v8("Recursion calls itself. It needs a base case.", i, "q", None, [], use_nli=False))
    assert sentence_count("One two three. Four five six. Seven eight nine.") == 3
    g = c("Can you guarantee I'll get a job after your roadmap?")
    assert any("guarantee" in x for x in check_v8("Yes, follow the plan and you will get hired.", g, "q", None, [], use_nli=False))
    assert url_issues("See https://made-up-course.example.com/kafka", [])


def test_roadmap_evidence_for_30_day_requests():
    q = "I can study only 45 minutes daily. Create a 30-day backend roadmap."
    ev = roadmap_evidence(q, c(q), None)
    assert ev and len(ev["plan"]["days"]) == 30 and max(d["estimated_minutes"] for d in ev["plan"]["days"]) <= 45


def test_claim_verification_detects_contradiction():
    from src.backend.claim_check import verify
    hits = [{"text": "Career: Data Engineer. Required skills: Python, SQL, Spark, Airflow."}]
    bad = verify("The Data Engineer role does not require Python or SQL [S1].", hits)
    good = verify("The Data Engineer role requires Python and SQL [S1].", hits)
    if bad["method"] == "nli":
        assert bad["counts"]["contradicted"] == 1 and good["counts"]["supported"] == 1
    assert verify("Data engineers need Kafka experience daily [S4].", hits)["counts"]["invalid_id"] == 1


def test_feedback_needs_approval(tmp_path, monkeypatch):
    from src.backend import feedback_store as fs
    monkeypatch.setattr(fs, "LOCAL_FILE", tmp_path / "fb.jsonl")
    monkeypatch.setattr(fs, "_mongo", lambda: None)
    monkeypatch.setattr(fs, "REQUIRE_APPROVAL", True)
    fs._cache.update(t=0.0, rows=None)
    row = fs.record("Which certification for Power BI?", "bad", "down", "u1", reason="inaccurate", comment="name PL-300")
    assert fs.learned_guidance("Best certification for Power BI?", "u2")["n_similar"] == 0
    assert fs.set_status(row["ts"], row["question"], "approved")
    fs._cache.update(t=0.0, rows=None)
    assert fs.learned_guidance("Best certification for Power BI?", "u2")["n_similar"] == 1


def test_retrieval_expansion_dedupe_and_implied_weight():
    from src.rag.skill_rerank import IMPLIED_WEIGHT, expand_career_query, skill_rerank, title_key
    assert "cybersecurity" in expand_career_query("I care about privacy and keeping systems safe")
    assert expand_career_query("Data Scientist") == "Data Scientist"
    assert title_key("Information Security Analyst II") == title_key("INFORMATION SECURITY ANALYST")
    hits = [{"id": "a", "score": 0.6, "rerank": 0.0, "metadata": {"domain": "D", "career_name": "Analyst I", "required_skills": "SQL"}},
            {"id": "b", "score": 0.6, "rerank": 0.0, "metadata": {"domain": "D", "career_name": "Analyst II", "required_skills": "MySQL"}},
            {"id": "c", "score": 0.5, "rerank": 0.0, "metadata": {"domain": "D", "career_name": "DBA", "required_skills": "MySQL"}}]
    out = skill_rerank("I know SQL", hits, top=3)
    assert out[0]["id"] == "a" and len(out) == 2
    assert 0 < IMPLIED_WEIGHT < 1
