# Career dataset quality report (2026-11-07 19:57 UTC)

Source: `docs/emerging_tech_career_dataset_cleaned.csv`

| Check | Result |
|---|---|
| Rows x columns | 2900 x 13 |
| career_id unique | True |
| Missing values (any column) | 0 |
| Exact duplicate rows (excluding id) | 0 |
| Unique career titles | 2399 |
| Repeated titles / with differing skill sets | 194 / 193 |
| Rows excluded from embedding (no alphabetic title) | 1 -> ids [12] |
| Salary == placeholder 140,100 | 2848 rows |
| Growth == placeholder 0.05 | 2897 rows |
| Description generated (not from source) | 1379 rows |
| Education inferred (not from source) | 1485 rows |
| Description words mean / max | 47.3 / 85 |

## Domains

| Domain | Rows |
|---|---|
| Project and Business Management | 607 |
| Data Analysis and BI | 450 |
| Machine Learning and AI | 331 |
| Data Engineering | 328 |
| Cloud and DevOps | 201 |
| Cybersecurity and Networking | 182 |
| Software and Web Development | 176 |
| Technology and Business Operations | 174 |
| Design, Engineering and Other Technical | 104 |
| Operations and Administration | 89 |
| Data Science and Research | 79 |
| Finance and Risk | 47 |
| IT Support and Systems | 47 |
| Marketing, Sales and Customer Operations | 43 |
| Data Architecture and Governance | 30 |
| Product, UX and Design | 12 |

## Implications

- Repeated titles are distinct profiles, so records are keyed by `career_id` and never deduplicated by name.
- Salary and growth are placeholders for most rows. The chatbot only shows non-placeholder values, labelled as unverified dataset values.
- Domains are classifier-assigned ('review borderline roles'), so they are used as weak labels in the retrieval benchmark.
- Generated descriptions repeat the title and skills. They help retrieval (E11) but are not independent evidence.
