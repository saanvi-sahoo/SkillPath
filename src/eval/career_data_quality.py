"""
Reproducible data-quality audit of the career source of truth (project doc sections 6.3-6.4, 14.3).
    python -m src.eval.career_data_quality
Writes reports/data_quality/career_dataset_report.md
"""
from datetime import datetime, timezone

import pandas as pd

from src.rag import config
from src.rag.documents import career_exclusions, load_career_frame


def main():
    raw = pd.read_csv(config.CAREERS_CSV)
    df = load_career_frame()
    rep = config.PROJECT_ROOT / "reports" / "data_quality"
    rep.mkdir(parents=True, exist_ok=True)
    rep_titles = df[df.career_name.duplicated(keep=False)].groupby("career_name")
    L = [f"# Career dataset quality report ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
         f"Source: `{config.CAREERS_CSV.relative_to(config.PROJECT_ROOT)}`", "",
         "| Check | Result |", "|---|---|",
         f"| Rows x columns | {raw.shape[0]} x {raw.shape[1]} |",
         f"| career_id unique | {raw.career_id.is_unique} |",
         f"| Missing values (any column) | {int(raw.isna().sum().sum())} |",
         f"| Exact duplicate rows (excluding id) | {int(raw.drop(columns='career_id').duplicated().sum())} |",
         f"| Unique career titles | {df.career_name.nunique()} |",
         f"| Repeated titles / with differing skill sets | {rep_titles.ngroups} / {int((rep_titles.required_skills.nunique() > 1).sum())} |",
         f"| Rows excluded from embedding (no alphabetic title) | {int(career_exclusions(df).sum())} -> ids {df.loc[career_exclusions(df), 'career_id'].tolist()} |",
         f"| Salary == placeholder {config.PLACEHOLDER_SALARY:,.0f} | {int((raw.average_salary == config.PLACEHOLDER_SALARY).sum())} rows |",
         f"| Growth == placeholder {config.PLACEHOLDER_GROWTH} | {int((raw.job_growth_rate == config.PLACEHOLDER_GROWTH).sum())} rows |",
         f"| Description generated (not from source) | {int((raw.description_basis != 'Retained from source dataset').sum())} rows |",
         f"| Education inferred (not from source) | {int(raw.education_basis.str.startswith('Inferred').sum())} rows |",
         f"| Description words mean / max | {raw.description.str.split().str.len().mean():.1f} / {raw.description.str.split().str.len().max()} |",
         "", "## Domains", "", "| Domain | Rows |", "|---|---|"]
    L += [f"| {d} | {n} |" for d, n in df.domain.value_counts().items()]
    L += ["", "## Implications", "",
          "- Repeated titles are distinct profiles, so records are keyed by `career_id` and never deduplicated by name.",
          "- Salary and growth are placeholders for most rows. The chatbot only shows non-placeholder values, labelled as unverified dataset values.",
          "- Domains are classifier-assigned ('review borderline roles'), so they are used as weak labels in the retrieval benchmark.",
          "- Generated descriptions repeat the title and skills. They help retrieval (E11) but are not independent evidence."]
    (rep / "career_dataset_report.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
