"""E38 (real-world reliability): conversation state, career-query rewrite, adaptive roadmap, failure handling. Offline.
Phrasings here are deliberately different from the frozen evaluation sets (heldout_v3, journeys_v1, careers_v3)."""
import json

from src.backend.conversation_state import build_state, list_items, resolved_message, state_block


def U(t):
    return {"role": "user", "content": t}


def A(t):
    return {"role": "assistant", "content": t}


def test_ordinal_reference_resolves_to_last_list():
    h = [U("which jobs suit someone who likes networks?"), A("Options:\n1. **Network Engineer** - routers\n2. Cloud Engineer: AWS\n3. SOC Analyst")]
    st = build_state(h, "the third option sounds good, what do I study?")
    assert st["reference"]["resolved"] == "SOC Analyst" and st["selected_career"] == "SOC Analyst"
    assert "SOC Analyst" in resolved_message("the third option sounds good, what do I study?", st)
    assert "SOC Analyst" in state_block(st)


def test_inline_list_and_last():
    assert list_items("You might consider Product Manager, Business Analyst, or Scrum Master roles.") == ["Product Manager", "Business Analyst", "Scrum Master"]
    st = build_state([U("x"), A("1. Alpha Analyst\n2. Beta Engineer")], "tell me about the last one")
    assert st["reference"]["resolved"] == "Beta Engineer"


def test_time_budget_skills_and_answers_to_questions():
    h = [U("I know Excel and Tableau but never used Python."), A("Do you have experience with SQL or Power BI?")]
    st = build_state(h, "nope. I can give it 40 minutes a day")
    assert st["daily_minutes"] == 40
    assert {"Excel", "Tableau"} <= set(st["known_skills"])
    assert {"Python", "SQL", "Power BI"} <= set(st["missing_skills"])
    assert build_state([], "I have two hours every day")["daily_minutes"] == 120


def test_corrections_conflicts_and_goal_changes():
    st = build_state([U("I know C# and want backend jobs"), A("ok")], "sorry, I meant C++, not C#")
    assert "C++" in st["known_skills"] and "C#" not in st["known_skills"] and st["corrections"]
    st = build_state([U("I'm new to programming"), A("ok")], "I've got 4 years of experience in PHP")
    assert st["conflicts"]
    st = build_state([U("I want to become a data analyst"), A("ok")], "actually I'd rather become a UX designer")
    assert st["selected_career"].lower().startswith("ux designer") and st["previous_goals"] == ["data analyst"]


def test_plan_without_time_asks():
    from src.backend.intent import classify
    st = build_state([], "build me a 30 day roadmap for react")
    assert "60 minutes/day" in state_block(st, classify("build me a 30 day roadmap for react", [], False))


def test_offer_answer_is_a_plan_request():
    from src.backend.intent import classify
    h = [U("I want to learn Kafka"), A("Kafka is a streaming platform. Would you like a week-by-week plan?")]
    assert classify("sure", h, False)["primary_intent"] == "learning_plan"
    assert classify("make it simpler please", [U("what is a hash map"), A("A hash map ...")], False)["response_style"] == "beginner"


def test_roadmap_evidence_uses_state():
    from src.backend.intent import classify
    from src.backend.task_contract import roadmap_evidence
    h = [U("I'm into cloud. I already know Linux."), A("1. Cloud Engineer\n2. DevOps Engineer"), U("the first one")]
    st = build_state(h, "ok, give me a 30-day roadmap. I have 45 minutes daily")
    ev = roadmap_evidence("ok, give me a 30-day roadmap. I have 45 minutes daily", classify("give me a 30-day roadmap", h, False), None, state=st)
    assert ev and ev["plan"]["daily_minutes"] == 45 and "Linux" not in ev["plan"]["gaps_prioritised"]
    st2 = build_state(h, "ok, give me a 30-day roadmap")
    ev2 = roadmap_evidence("ok, give me a 30-day roadmap", classify("give me a 30-day roadmap", h, False), None, state=st2)
    assert ev2["plan"]["daily_minutes"] == 60 and "ASSUMED" in ev2["text"]


def test_career_query_rewrite():
    from src.rag.skill_rerank import rewrite_career_query, title_bonus
    r = rewrite_career_query("I did a chemistry degree and hope to move into data science")
    assert r["type"] == "transition" and r["role"] == "data scientist" and "chemistry" not in r["search_query"].lower()
    assert rewrite_career_query("Cloud Architect")["type"] == "plain"
    hits = [{"id": "a", "rerank": 1.0, "metadata": {"career_name": "Marketing Lead"}},
            {"id": "b", "rerank": 0.5, "metadata": {"career_name": "Senior Data Scientist"}}]
    assert title_bonus(hits, "data scientist")[0]["id"] == "b"


def test_adaptive_roadmap():
    from src.roadmap.adapt import adapt_roadmap
    from src.roadmap.generator import generate_roadmap
    r = generate_roadmap("Backend Developer", ["Python"], gaps=["SQL", "Docker", "REST APIs"], daily_minutes=45, use_llm=False)
    a = adapt_roadmap(r, {1: "completed", 2: "needs_revision", 3: "skipped"}, today=4)
    assert a["days"][1]["day"] == 4 and a["days"][1]["kind"] == "revision"
    assert max(d["day"] for d in a["days"]) <= 30 and all(d["estimated_minutes"] <= 45 for d in a["days"])
    assert a["progress"]["rate"] == round(1 / 3, 3) and any("missed" in c for c in a["changes"])
    assert adapt_roadmap(r, {}, today=1)["changes"] == ["You're on track: no changes needed."]


def test_unreadable_pdf(tmp_path):
    import fitz
    from src.utilities.doc_check import unreadable_reason
    p = tmp_path / "scan.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(p))
    assert "scanned" in unreadable_reason(str(p), "CV")


def test_privacy_guard_blocks_other_users(tmp_path, monkeypatch):
    from src.rag import retriever
    monkeypatch.setattr(retriever, "SECURITY_LOG", tmp_path / "sec.jsonl")
    hits = [{"id": "g", "user_id": "global"}, {"id": "mine", "user_id": "u1"}, {"id": "theirs", "user_id": "u2"}]
    assert [h["id"] for h in retriever._privacy_guard(hits, "u1")] == ["g", "mine"]
    assert json.loads((tmp_path / "sec.jsonl").read_text())["record_ids"] == ["theirs"]


def test_salary_and_progress_rules():
    from src.backend.task_contract import e38_rules
    assert "do not establish" in e38_rules("what's the starting package for SDE in bangalore", None, None).replace("does not establish", "do not establish")
    assert "Adapt" in e38_rules("I fell behind by a week, what do I do", None, None)


def test_empty_model_reply_is_retried_then_falls_back(monkeypatch):
    """Final validation (journey j03): gpt-oss once returned no text; the student saw 'I couldn't generate an answer'."""
    import src.utilities.brain as brain
    from src.backend import chatbot

    class Resp:
        def __init__(self, t):
            self.text, self.response_metadata, self.usage_metadata = t, {"model_name": "fake"}, None

    for replies, expect_fallback in ((["", "Docker packages apps into containers."], False), (["", ""], True)):
        it = iter(replies + ["unused"] * 3)

        class Fake:
            def invoke(self, msgs):
                return Resp(next(it))
        monkeypatch.setattr(brain, "get_robust_llm", lambda *a, **k: Fake())
        monkeypatch.setenv("LLM_PROVIDER", "api")
        out = chatbot.answer([{"role": "user", "content": "What is Docker?"}], user_id="test_no_profile",
                             route_override={"label": "career_study"})
        assert out.get("empty_retry")
        if expect_fallback:
            assert out["generation"] == "retrieval-only (empty model reply)" and "unavailable right now" in out["text"]
        else:
            assert out["text"].startswith("Docker packages apps")
