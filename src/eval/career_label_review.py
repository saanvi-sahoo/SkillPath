"""
Career dataset label review (E38, review 3 §4D: "investigate mislabeled or ambiguous career records instead of repeatedly
changing reranker weights"). No LLM, no data is changed.

A record is flagged when its TITLE clearly names a role family (e.g. "Data Analyst", "QA Engineer", "Help Desk Technician")
but its `domain` label is outside that family's expected domains. Output is a review list for a person to accept or reject;
accepted relabels would go into a new dataset version, never edited in place.

  python -m src.eval.career_label_review
Writes reports/data_quality/career_label_review.csv + career_label_review.md
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict

from src.rag import config

FAMILIES = [  # (family, title pattern, acceptable domains)
    ("Data analysis / BI", r"\b(data analyst|business analyst|bi (analyst|developer)|business intelligence|power bi|tableau|reporting analyst)\b",
     {"Data Analysis and BI", "Data Science and Research"}),
    ("Data engineering", r"\b(data engineer|etl developer|big data engineer|data pipeline)\b", {"Data Engineering", "Data Architecture and Governance"}),
    ("Data science / ML", r"\b(data scientist|machine learning|ml engineer|deep learning|computer vision|nlp)\b",
     {"Machine Learning and AI", "Data Science and Research"}),
    ("Cybersecurity", r"\b(security analyst|soc analyst|penetration tester|cyber ?security|information security)\b", {"Cybersecurity and Networking"}),
    ("Cloud / DevOps", r"\b(devops|site reliability|sre|cloud engineer)\b", {"Cloud and DevOps"}),
    ("QA / testing", r"\b(qa|quality assurance|test engineer|tester|test automation)\b", {"Software and Web Development"}),
    ("IT support", r"\b(help ?desk|desktop support|it support|support technician)\b", {"IT Support and Systems"}),
    ("Software / web", r"\b(front ?end|back ?end|full ?stack|web developer|software (developer|engineer))\b", {"Software and Web Development"}),
    ("Project / agile", r"\b(scrum master|project manager|program manager|agile coach)\b", {"Project and Business Management"}),
    ("Finance", r"\b(financial analyst|risk analyst|credit analyst)\b", {"Finance and Risk"}),
    ("UX / design", r"\b(ux|ui designer|product designer|user experience)\b", {"Product, UX and Design"}),
]


def main():
    from src.rag.vector_store import get_vector_store
    docs = [d for d in get_vector_store("careers", backend="local").docs if d["source"] == "careers"]
    seen, flags, totals = set(), [], Counter()
    for d in docs:
        m = d.get("metadata") or {}
        cid, title, dom = m.get("career_id", d["id"]), str(m.get("career_name") or ""), m.get("domain")
        if cid in seen:
            continue
        seen.add(cid)
        for fam, pat, ok in FAMILIES:
            if re.search(pat, title.lower()):
                totals[fam] += 1
                if dom not in ok:
                    flags.append({"career_id": cid, "title": title, "current_domain": dom, "family": fam,
                                  "suggested_domain": sorted(ok)[0], "decision": ""})
                break
    out = config.PROJECT_ROOT / "reports" / "data_quality"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "career_label_review.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flags[0].keys()) if flags else ["career_id"])
        w.writeheader()
        w.writerows(flags)
    by = defaultdict(list)
    for f in flags:
        by[f["family"]].append(f)
    L = ["# Career dataset label review (E38)", "", f"{len(seen)} unique career records scanned; {sum(totals.values())} have a title that "
         f"clearly names a role family; **{len(flags)} ({len(flags) / max(1, sum(totals.values())):.0%}) carry a domain label outside that family**.",
         "", "Nothing was changed. `reports/data_quality/career_label_review.csv` has one row per record with a `decision` column for a reviewer.", "",
         "| Role family (from title) | Records | Flagged | Share | Most common wrong label |", "|---|---|---|---|---|"]
    for fam, _, _ in FAMILIES:
        fl = by.get(fam, [])
        common = Counter(f["current_domain"] for f in fl).most_common(1)
        L.append(f"| {fam} | {totals[fam]} | {len(fl)} | {len(fl) / max(1, totals[fam]):.0%} | {common[0][0] + f' ({common[0][1]})' if common else '-'} |")
    L += ["", "Examples:", ""] + [f"- {f['title']} - labelled *{f['current_domain']}* (expected {f['family']})" for f in flags[:15]]
    (out / "career_label_review.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:22]))


if __name__ == "__main__":
    main()


# ── Final validation (review 4 §4): first-pass classification of the flagged records, dataset untouched ─────────
FAMILY_SKILLS = {
    "Data analysis / BI": r"\b(sql|excel|tableau|power bi|dashboard|report|visuali[sz]|analytics|statistics)\b",
    "Data engineering": r"\b(spark|airflow|etl|pipeline|kafka|hadoop|data warehouse|snowflake|databricks|dbt)\b",
    "Data science / ML": r"\b(machine learning|tensorflow|pytorch|scikit|model|deep learning|nlp|statistics)\b",
    "Cybersecurity": r"\b(security|siem|firewall|incident|vulnerab|penetration|iam|soc)\b",
    "Cloud / DevOps": r"\b(aws|azure|gcp|kubernetes|docker|terraform|ci/cd|jenkins|devops)\b",
    "QA / testing": r"\b(selenium|test|qa|quality|automation|cypress|jira)\b",
    "IT support": r"\b(troubleshoot|help ?desk|windows|active directory|hardware|ticket|support)\b",
    "Software / web": r"\b(java|javascript|react|angular|node|python|c#|\.net|html|css|api|spring)\b",
    "Project / agile": r"\b(agile|scrum|project management|stakeholder|jira|planning|budget)\b",
    "Finance": r"\b(financ|accounting|risk|credit|forecast|excel)\b",
    "UX / design": r"\b(figma|ux|ui|wirefram|prototyp|user research|design)\b",
}
DOMAIN_FAMILY = {"Data Analysis and BI": "Data analysis / BI", "Data Engineering": "Data engineering", "Machine Learning and AI": "Data science / ML",
                 "Data Science and Research": "Data science / ML", "Cybersecurity and Networking": "Cybersecurity", "Cloud and DevOps": "Cloud / DevOps",
                 "IT Support and Systems": "IT support", "Software and Web Development": "Software / web",
                 "Project and Business Management": "Project / agile", "Finance and Risk": "Finance", "Product, UX and Design": "UX / design"}


def classify_flags() -> None:
    """Adds a first-pass `first_pass` column: likely_mislabeled (skills fit the title's family clearly better than the
    label's family) / ambiguous (skills fit both or neither). Writes a PROPOSED corrections file; nothing is applied."""
    import csv
    from collections import Counter

    from src.rag.vector_store import get_vector_store
    out = config.PROJECT_ROOT / "reports" / "data_quality"
    rows = list(csv.DictReader(open(out / "career_label_review.csv", encoding="utf-8")))
    skills = {(d.get("metadata") or {}).get("career_id", d["id"]): str((d.get("metadata") or {}).get("required_skills") or "").lower()
              for d in get_vector_store("careers", backend="local").docs if d["source"] == "careers"}
    for r in rows:
        sk = skills.get(r["career_id"], "")
        own = len(re.findall(FAMILY_SKILLS[r["family"]], sk))
        lab_fam = DOMAIN_FAMILY.get(r["current_domain"])
        lab = len(re.findall(FAMILY_SKILLS[lab_fam], sk)) if lab_fam else 0
        r["skills_fit_title_family"], r["skills_fit_label_family"] = own, lab
        r["first_pass"] = "likely_mislabeled" if own >= 2 and own >= 2 * max(lab, 1) else "ambiguous"
        r["decision"] = r.get("decision", "")
    fields = list(rows[0].keys())
    with open(out / "career_label_review.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    prop = [r for r in rows if r["first_pass"] == "likely_mislabeled"]
    with open(out / "career_domain_corrections_v1_PROPOSED.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["career_id", "title", "current_domain", "proposed_domain", "evidence", "verified_by", "apply"])
        for r in prop:
            w.writerow([r["career_id"], r["title"], r["current_domain"], r["suggested_domain"],
                        f"title family {r['family']}; {r['skills_fit_title_family']} family skills vs {r['skills_fit_label_family']} for the label", "", "no"])
    c = Counter(r["first_pass"] for r in rows)
    print(f"first pass over {len(rows)} flagged records: {dict(c)}; proposed corrections -> career_domain_corrections_v1_PROPOSED.csv (not applied)")
    md = out / "career_label_review.md"
    md.write_text(md.read_text().split("\n## First pass")[0] + f"\n## First pass (final validation)\n\n{dict(c)} of {len(rows)} flagged records. "
                  "*likely_mislabeled* = the record's required skills fit its title's role family at least twice as well as the family of "
                  "its label; *ambiguous* = they fit both or neither (e.g. a 'Business Analyst' whose skills are data pipelines). "
                  "Proposed relabels: `career_domain_corrections_v1_PROPOSED.csv` (`verified_by` and `apply` columns for a reviewer). "
                  "The dataset and the vector store are unchanged.\n")


if __name__ == "__main__" and len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "classify":
    classify_flags()
