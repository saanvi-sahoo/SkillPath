"""E36 (prompt v7): parsed intent, grounding checks, skill-aware career re-ranking, capstones. Offline, no LLM."""
from src.backend.answer_check import check_answer_v7, citation_report, fact_issues
from src.backend.question_profile import parsed_intent, profile_question
from src.roadmap.syllabus import capstone_for
from src.rag.skill_rerank import explain, query_skills, skill_rerank, _record_skills

MEM = {"ats_score": 43, "skill_gaps": ["Tableau", "Statistics"], "candidate_skills": ["Python", "SQL", "Power BI"],
       "required_skills": ["Python", "SQL", "Power BI", "Tableau", "Statistics"]}
HITS = [{"source": "careers", "text": "Career: Data Analyst. Required skills: SQL, Excel, Power BI, dashboards.", "metadata": {}},
        {"source": "knowledge", "text": "Interview prep: practise SQL joins and explain one project with the STAR method.", "metadata": {}}]


def pi(q, has_profile=False, hist=0):
    return parsed_intent(profile_question(q), q, has_profile, hist)


def test_missing_information_rules():
    assert pi("Suggest a career for me")["missing"]
    assert pi("Which one is better?")["missing"]
    assert pi("What is my ATS score?")["missing"]                     # profile question, no profile
    assert pi("What is my ATS score?", has_profile=True)["missing"] is None
    assert pi("Which career fits me if I like statistics?")["missing"] is None   # interests given
    assert pi("What is SQL?")["missing"] is None
    assert pi("Which one is better?", hist=2)["missing"] is None      # follow-up has a referent


def test_intent_fields():
    p = pi("Give me 3 certifications for cloud, briefly")
    assert p["n_items"] == 3 and p["max_words"] == 120 and p["primary_source"] and p["task"]


def test_citation_report_invalid_and_unsupported():
    good = "Data analysts use SQL and Power BI dashboards [S1]. Practise SQL joins for interviews [S2]."
    assert citation_report(good, HITS)["correct_rate"] == 1.0
    bad = "Graphic designers create logos with Photoshop [S1]. See also [S5]."
    r = citation_report(bad, HITS)
    assert r["invalid"] == [5] and r["unsupported"]


def test_fact_issues():
    assert fact_issues("Your ATS estimate is 61/100.", MEM)
    assert not fact_issues("Your ATS estimate is 43/100 (an AI estimate).", MEM)
    assert fact_issues("You already have Tableau experience, so apply.", MEM)
    assert not fact_issues("You don't have Tableau yet; it is a gap.", MEM)


def test_check_answer_v7_requires_clarification():
    p = pi("Suggest a career for me")
    issues = check_answer_v7("Become a data scientist. It pays well.", p, "Suggest a career for me", None, [])
    assert any("clarifying question" in i for i in issues)


def test_skill_rerank_exact_and_related():
    assert {"docker"} <= query_skills("I know Docker")
    rs = _record_skills("Kubernetes, AWS, MySQL")
    assert "sql" in rs                                                # MySQL proves SQL
    e = explain({"docker", "sql"}, rs)
    assert e["exact"] == ["sql"] and e["related_only"] == ["docker"]  # related is not exact
    hits = [{"id": "a", "score": 0.5, "rerank": 0.0, "metadata": {"domain": "Cloud and DevOps", "required_skills": "Kubernetes"}},
            {"id": "b", "score": 0.6, "rerank": 0.0, "metadata": {"domain": "Cloud and DevOps", "required_skills": "Docker, AWS"}}]
    assert skill_rerank("I know Docker", hits, top=2)[0]["id"] == "b"  # exact beats related


def test_capstones_role_specific():
    assert "vulnerability" in capstone_for("Cybersecurity Analyst", ["SIEM"])
    assert "pipeline" in capstone_for("Data Engineer", ["Spark"])
    assert "dashboard" in capstone_for("Data Analyst", ["Tableau"])
