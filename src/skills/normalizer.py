"""
Skill normalisation, categorisation and exact gap comparison (project doc section 10).

    extraction (LLM, brain.py)  ->  normalise (aliases -> canonical)  ->  categorise (rule map)
                                ->  compare (EXACT canonical match; related != equivalent)

Design rules from the project doc:
  * related technology is NOT equivalent: Docker never satisfies Kubernetes. We record it as
    "related background" while the requirement stays a gap.
  * rule-based category map first; unknown skills fall into "Other" (LLM fallback is a TODO,
    see docs/roadmap.md), so nothing is silently mis-categorised.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List

# alias (lowercase, punctuation-normalised) -> canonical name
ALIASES: Dict[str, str] = {
    "py": "Python", "python3": "Python", "python": "Python",
    "js": "JavaScript", "javascript": "JavaScript", "ts": "TypeScript", "typescript": "TypeScript",
    "node": "Node.js", "nodejs": "Node.js", "node js": "Node.js", "node.js": "Node.js",
    "react": "React", "reactjs": "React", "react js": "React", "react.js": "React",
    "java": "Java", "spring": "Spring Boot", "spring boot": "Spring Boot", "springboot": "Spring Boot",
    "c++": "C++", "cpp": "C++", "c#": "C#", "csharp": "C#", "golang": "Go", "go": "Go",
    "sql": "SQL", "mysql": "MySQL", "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "mongo": "MongoDB", "mongodb": "MongoDB", "nosql": "NoSQL",
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "dl": "Deep Learning", "deep learning": "Deep Learning",
    "nlp": "Natural Language Processing", "natural language processing": "Natural Language Processing",
    "cv": "Computer Vision", "computer vision": "Computer Vision",
    "llm": "Large Language Models", "llms": "Large Language Models", "large language models": "Large Language Models",
    "genai": "Generative AI", "generative ai": "Generative AI",
    "tf": "TensorFlow", "tensorflow": "TensorFlow", "pytorch": "PyTorch", "torch": "PyTorch",
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn", "scikit-learn": "scikit-learn",
    "pandas": "Pandas", "numpy": "NumPy",
    "stats": "Statistics", "statistics": "Statistics", "statistical analysis": "Statistics",
    "excel": "Excel", "ms excel": "Excel", "microsoft excel": "Excel", "advanced excel": "Excel",
    "power bi": "Power BI", "powerbi": "Power BI", "tableau": "Tableau", "looker": "Looker",
    "data visualization": "Data Visualization", "data visualisation": "Data Visualization",
    "aws": "AWS", "amazon web services": "AWS", "azure": "Azure", "microsoft azure": "Azure",
    "gcp": "GCP", "google cloud": "GCP", "google cloud platform": "GCP",
    "docker": "Docker", "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "ci/cd": "CI/CD", "cicd": "CI/CD", "ci cd": "CI/CD", "jenkins": "Jenkins", "terraform": "Terraform",
    "autocad": "AutoCAD", "matlab": "MATLAB", "git": "Git", "github": "GitHub", "linux": "Linux", "bash": "Bash", "shell scripting": "Bash",
    "spark": "Apache Spark", "apache spark": "Apache Spark", "pyspark": "Apache Spark",
    "airflow": "Apache Airflow", "apache airflow": "Apache Airflow", "kafka": "Apache Kafka", "apache kafka": "Apache Kafka",
    "hadoop": "Hadoop", "etl": "ETL", "data warehousing": "Data Warehousing", "snowflake": "Snowflake",
    "rest": "REST APIs", "rest api": "REST APIs", "rest apis": "REST APIs", "restful apis": "REST APIs", "restful api": "REST APIs", "restful api design": "REST APIs", "apis": "REST APIs",
    "microservices": "Microservices", "microservices concepts": "Microservices",
    "html": "HTML", "css": "CSS", "flask": "Flask", "django": "Django", "fastapi": "FastAPI",
    "communication": "Communication", "communication skills": "Communication",
    "teamwork": "Teamwork", "problem solving": "Problem Solving", "leadership": "Leadership",
    "agile": "Agile", "scrum": "Scrum", "project management": "Project Management",
}

CATEGORIES: Dict[str, List[str]] = {
    "Programming": ["Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Bash"],
    "Databases": ["SQL", "MySQL", "PostgreSQL", "MongoDB", "NoSQL", "Snowflake"],
    "AI/ML": ["Machine Learning", "Deep Learning", "Natural Language Processing", "Computer Vision",
              "Large Language Models", "Generative AI", "TensorFlow", "PyTorch", "scikit-learn"],
    "Data Analysis & BI": ["Statistics", "Excel", "Power BI", "Tableau", "Looker", "Data Visualization", "Pandas", "NumPy"],
    "Data Engineering": ["Apache Spark", "Apache Airflow", "Apache Kafka", "Hadoop", "ETL", "Data Warehousing"],
    "Cloud/DevOps": ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Jenkins", "Terraform", "Linux"],
    "Web & Backend": ["React", "Node.js", "HTML", "CSS", "Flask", "Django", "FastAPI", "Spring Boot", "REST APIs", "Microservices"],
    "Tools": ["Git", "GitHub"],
    "Soft Skills": ["Communication", "Teamwork", "Problem Solving", "Leadership"],
    "Project Management": ["Agile", "Scrum", "Project Management"],
}
_CATEGORY_OF = {skill: cat for cat, skills in CATEGORIES.items() for skill in skills}

# Related-but-not-equivalent groups: used ONLY for "related background" notes, never for matching.
RELATED: List[set] = [
    {"Docker", "Kubernetes"}, {"AWS", "Azure", "GCP"}, {"Power BI", "Tableau", "Looker"},
    {"MySQL", "PostgreSQL", "SQL"}, {"TensorFlow", "PyTorch"}, {"Flask", "Django", "FastAPI"},
    {"Machine Learning", "Deep Learning"}, {"Apache Spark", "Hadoop"}, {"Jenkins", "CI/CD"},
    {"JavaScript", "TypeScript"}, {"Pandas", "NumPy"},
]

# Specific skill -> general skill it PROVES (using MySQL means writing SQL). One direction only:
# knowing SQL does not prove MySQL. Kept deliberately small and auditable.
IMPLIES: Dict[str, List[str]] = {
    "MySQL": ["SQL"], "PostgreSQL": ["SQL"], "Snowflake": ["SQL"],
    "Spring Boot": ["Java"], "Django": ["Python"], "Flask": ["Python"], "FastAPI": ["Python"],
    "Pandas": ["Python"], "scikit-learn": ["Python", "Machine Learning"], "PyTorch": ["Python", "Deep Learning"],
    "TensorFlow": ["Python", "Deep Learning"], "React": ["JavaScript"], "Node.js": ["JavaScript"],
    "TypeScript": ["JavaScript"], "Apache Spark": ["ETL"],
}

_PREFIX = re.compile(r"^\s*(tools?|soft skills?|programming|languages?|frameworks?|technical|skills?|databases?)\s*:\s*", re.I)


def _key(s: str) -> str:
    s = _PREFIX.sub("", s or "")
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", re.sub(r"[()\[\]]", " ", s)).strip(" .,-")
    return s


def normalize(skill: str) -> str:
    """'Tools: power-bi ' -> 'Power BI'. Unknown skills are title-cased but otherwise kept."""
    k = _key(skill)
    k2 = k.replace("-", " ")
    if k in ALIASES:
        return ALIASES[k]
    if k2 in ALIASES:
        return ALIASES[k2]
    return " ".join(w if w.isupper() else w.capitalize() for w in k.split()) if k else ""


def categorize(skill: str) -> str:
    return _CATEGORY_OF.get(normalize(skill), "Other")


def normalize_all(skills: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for s in skills or []:
        n = normalize(s)
        if n and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def compare(candidate_skills: Iterable[str], required_skills: Iterable[str]) -> Dict:
    """Exact canonical comparison. Returns matched, gaps, related_background, categories."""
    cand = normalize_all(candidate_skills)
    req = normalize_all(required_skills)
    cand_l = {c.lower() for c in cand}
    implied = {i.lower(): c for c in cand for i in IMPLIES.get(c, [])}
    matched = [r for r in req if r.lower() in cand_l]
    matched_by_implication = {r: implied[r.lower()] for r in req if r.lower() not in cand_l and r.lower() in implied}
    gaps = [r for r in req if r.lower() not in cand_l and r not in matched_by_implication]
    related = {}
    for g in gaps:
        rel = sorted(c for grp in RELATED if g in grp for c in grp if c != g and c.lower() in cand_l)
        if rel:
            related[g] = rel
    return {
        "candidate": cand, "required": req, "matched": matched + list(matched_by_implication), "gaps": gaps,
        "matched_by_implication": matched_by_implication,  # e.g. {"SQL": "MySQL"}
        "related_background": related,  # e.g. {"Kubernetes": ["Docker"]}: still a gap
        "match_ratio": round((len(matched) + len(matched_by_implication)) / len(req), 3) if req else None,
        "gap_categories": {g: categorize(g) for g in gaps},
    }
