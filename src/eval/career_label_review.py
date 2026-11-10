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
