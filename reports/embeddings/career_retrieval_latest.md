# Career retrieval benchmark (20261107T195455Z)

Corpus: 2900 careers, 24 labelled queries, k=5.

| Model | Text variant | Domain-P@5 | Keyword-P@5 | Strict-P@5 | Top-1 score |
|---|---|---|---|---|---|
| sentence-transformers/all-MiniLM-L6-v2 | pilot | 0.725 | 0.942 | 0.708 | 0.576 |
| sentence-transformers/all-MiniLM-L6-v2 | domain | 0.775 | 0.917 | 0.75 | 0.571 |
| sentence-transformers/all-MiniLM-L6-v2 | full | 0.8 | 0.908 | 0.767 | 0.577 |
| BAAI/bge-small-en-v1.5 | pilot | 0.667 | 0.942 | 0.658 | 0.733 |
| BAAI/bge-small-en-v1.5 | domain | 0.742 | 0.95 | 0.725 | 0.725 |
| BAAI/bge-small-en-v1.5 | full | 0.775 | 0.925 | 0.733 | 0.731 |

## Error analysis - best config (sentence-transformers/all-MiniLM-L6-v2, full)
- **I want to work on recommendation systems for e-commerce** (domain 0.2, keyword 0.2): Expert Data Scientist [Machine Learning and AI]; Product Advisor - The Domain [Marketing, Sales and Customer Operations]; Principal Consultant, eCommerce IT [Project and Business Management]; Web Developer [Software and Web Development]; VP of Technology, eCommerce [Software and Web Development]
- **How do I become a sports analyst?** (domain 0.0, keyword 1.0): Analyst, Baseball Operations [Project and Business Management]; Basketball Data Analyst [Machine Learning and AI]; Global Strategy Competitive Analysis Analyst [Project and Business Management]; Game Security Analyst [Cybersecurity and Networking]; Financial Analyst [Project and Business Management]
- **I'm good at planning, coordinating teams and tracking project timelines** (domain 0.6, keyword 0.6): Project Coordinator [Project and Business Management]; Project Manager, Development [Project and Business Management]; Entry-Level Project Manager [Data Analysis and BI]; Project Manager -Reporting & Analytics [Data Analysis and BI]; Project Management Coordinator, Brand Operations [Project and Business Management]
- **Which career fits Python, SQL and dashboards?** (domain 0.6, keyword 1.0): Python Developer - Data Analysis [Software and Web Development]; Python Integration Engineer [Data Engineering]; Software Engineer, Data [Data Engineering]; Python Engineer for Data Analytics [Machine Learning and AI]; Data Engineer (Python) [Data Engineering]

## Sample results - best config
- **I enjoy building predictive models in Python and want to work with neural networks** -> Software Developer - Machine Learning (0.549); Data Scientist (0.541); Data Science Generalist (0.534); Machine Learning Research Scientist (0.525); Deep Learning Computer Architect (0.523)
- **Which career fits Python, SQL and dashboards?** -> Python Developer - Data Analysis (0.722); Python Integration Engineer (0.712); Software Engineer, Data (0.701); Python Engineer for Data Analytics (0.691); Data Engineer (Python) (0.671)
- **I like making reports and charts for business teams using Excel and Power BI** -> Business Analytics Specialist (0.599); Associate – Workplace Analytics Customer Solutions (0.597); REPORTING ANALYST - REDMOND, WA (0.589); Consultant - Analytics (Microsoft Power BI and Data Science) (0.577); Associate, Analytics (0.575)
- **I want to build data pipelines with Spark and Airflow** -> Spark Data Engineer (0.573); Software and Data Pipeline Architect (0.544); Data Engineer (0.525); Data Engineer (Spark, Docker, AWS) (0.522); Data Engineer (0.52)
- **career working with AWS, Docker, Kubernetes and CI/CD automation** -> Automation Architect (0.712); AWS Cloud Infrastructure Architect (0.673); AWS IaaS Developer (0.665); AWS IaaS Developer (0.661); AWS Cloud Engineer (0.651)
- **I want to protect companies from hackers and do penetration testing** -> Security Analyst (0.492); Security Analyst (0.487); Security Architect (0.475); Security Analyst (0.473); Security Engineer - Data Protection (0.472)
