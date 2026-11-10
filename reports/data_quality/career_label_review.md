# Career dataset label review (E38)

2899 unique career records scanned; 907 have a title that clearly names a role family; **240 (26%) carry a domain label outside that family**.

Nothing was changed. `reports/data_quality/career_label_review.csv` has one row per record with a `decision` column for a reviewer.

| Role family (from title) | Records | Flagged | Share | Most common wrong label |
|---|---|---|---|---|
| Data analysis / BI | 292 | 76 | 26% | Data Engineering (64) |
| Data engineering | 97 | 18 | 19% | Machine Learning and AI (13) |
| Data science / ML | 177 | 0 | 0% | - |
| Cybersecurity | 75 | 11 | 15% | Cloud and DevOps (6) |
| Cloud / DevOps | 10 | 0 | 0% | - |
| QA / testing | 26 | 22 | 85% | Data Engineering (6) |
| IT support | 15 | 4 | 27% | Project and Business Management (2) |
| Software / web | 168 | 82 | 49% | Cloud and DevOps (42) |
| Project / agile | 31 | 16 | 52% | Data Analysis and BI (8) |
| Finance | 7 | 3 | 43% | Project and Business Management (2) |
| UX / design | 9 | 8 | 89% | Software and Web Development (4) |

Examples:

- .NET Full-Stack Web Developer - labelled *Cloud and DevOps* (expected Software / web)
- Analytics Project Manager (SSS III) - Information Services - labelled *Data Analysis and BI* (expected Project / agile)
- Architect (fullstack) - labelled *Data Engineering* (expected Software / web)
- Architect (fullstack) - labelled *Data Engineering* (expected Software / web)
- Associate Data Engineer - labelled *Machine Learning and AI* (expected Data engineering)
- Associate, Big Data Software Engineer - labelled *Machine Learning and AI* (expected Software / web)
- Associate, Big Data Software Engineer - labelled *Data Science and Research* (expected Software / web)
- Associate, Big Data Software Engineer - labelled *Data Science and Research* (expected Software / web)
- BI Developer - labelled *Data Engineering* (expected Data analysis / BI)
- Backend Architect - labelled *Cloud and DevOps* (expected Software / web)
- Backend Programmer - labelled *Cloud and DevOps* (expected Software / web)
- Basketball Data Analyst - labelled *Machine Learning and AI* (expected Data analysis / BI)
- Big Data Analyst - Developer - labelled *Machine Learning and AI* (expected Data analysis / BI)
- Big Data Engineer - labelled *Machine Learning and AI* (expected Data engineering)
- Big Data Engineer - labelled *Machine Learning and AI* (expected Data engineering)
