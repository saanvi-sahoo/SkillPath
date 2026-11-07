"""
Document builders: turn every raw data source into embeddable `Chunk`s.

Sources (the `source` field on every chunk):
    careers    -> embedding_experiment/skillpath_careers_processed.csv (1 chunk / career)
    jobs       -> LinkedIn master_jobs_detailed.json + Naukri scraper/jobs.json
    profile    -> src/backend/memory.json (latest pipeline run for a user)
    knowledge  -> src/data/knowledge_base/*.md (curated career & study guides)

Chunk ids are deterministic (sha1 of source + natural key) so re-ingesting the
same data upserts instead of duplicating.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List

import pandas as pd

from src.rag import config


@dataclass
class Chunk:
    id: str
    text: str
    source: str  # careers | jobs | profile | knowledge
    doc_type: str  # finer-grained type, e.g. resume, skill_gap, job_listing
    user_id: str = "global"  # "global" for shared corpora, else the owner
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


def _hash_id(*parts: str) -> str:
    return hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()


def _clean(text) -> str:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def split_words(text: str, max_words: int = None, overlap: int = None) -> List[str]:
    """Sliding-window word chunker. Short texts come back as a single chunk."""
    max_words = max_words or config.CHUNK_MAX_WORDS
    overlap = config.CHUNK_OVERLAP_WORDS if overlap is None else overlap
    words = _clean(text).split()
    if len(words) <= max_words:
        return [" ".join(words)] if words else []
    step = max(1, max_words - overlap)
    out = []
    for start in range(0, len(words), step):
        out.append(" ".join(words[start : start + max_words]))
        if start + max_words >= len(words):
            break
    return out


# ── careers (source of truth: emerging_tech_career_dataset_cleaned.csv) ──────
# Embedding-text variants benchmarked in src/eval/evaluate_career_retrieval.py (docs/embeddings.md).
CAREER_TEXT_VARIANTS = {
    "pilot": lambda r: f"Career: {r['career_name']}. Required skills: {r['required_skills']}.",
    "domain": lambda r: f"Career: {r['career_name']}. Domain: {r['domain']}. Required skills: {r['required_skills']}.",
    "full": lambda r: (f"Career: {r['career_name']}. Domain: {r['domain']}. Required skills: {r['required_skills']}. "
                       f"Description: {r['description']}"),
}
CAREER_TEXT_VARIANT = "full"  # set from the benchmark, see docs/experiment_log.md


def load_career_frame(csv_path=config.CAREERS_CSV) -> pd.DataFrame:
    """Load + validate the career dataset. Keeps ALL rows: repeated titles are distinct profiles
    (193 of 194 repeated titles have different skill sets), so deduping by name loses information."""
    df = pd.read_csv(csv_path)
    required = {"career_id", "career_name", "required_skills", "education_required", "domain", "description"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path} is missing columns {missing}")
    if not df["career_id"].is_unique:
        raise ValueError("career_id must be unique (stable record id <-> vector alignment)")
    for c in ["career_name", "required_skills", "education_required", "domain", "description"]:
        df[c] = df[c].map(_clean)
    return df


def career_exclusions(df: pd.DataFrame) -> pd.Series:
    """Rows that cannot be a career record. Reason is logged in docs/embeddings.md."""
    return ~df["career_name"].str.contains(r"[A-Za-z]", regex=True)  # e.g. career_id 12 named "393360"


def build_career_chunks(csv_path=config.CAREERS_CSV, limit: int | None = None, variant: str = None) -> List[Chunk]:
    df = load_career_frame(csv_path)
    excl = career_exclusions(df)
    if excl.any():
        print(f"[careers] excluding {int(excl.sum())} rows with no alphabetic title: {df.loc[excl, 'career_id'].tolist()}")
    df = df[~excl]
    if limit:
        df = df.head(limit)
    to_text = CAREER_TEXT_VARIANTS[variant or CAREER_TEXT_VARIANT]
    chunks = []
    for _, row in df.iterrows():
        if not row["career_name"]:
            continue
        salary, growth = row.get("average_salary"), row.get("job_growth_rate")
        salary_ok = pd.notna(salary) and float(salary) != config.PLACEHOLDER_SALARY
        growth_ok = pd.notna(growth) and float(growth) != config.PLACEHOLDER_GROWTH
        cid = f"career_{int(row['career_id']):04d}"
        chunks.append(
            Chunk(
                id=cid,
                text=to_text(row),
                source="careers",
                doc_type="career_profile",
                metadata={
                    "career_id": cid,
                    "career_name": row["career_name"],
                    "domain": row["domain"],
                    "required_skills": row["required_skills"],
                    "education_required": row["education_required"],
                    "description": row["description"],
                    "average_salary": float(salary) if pd.notna(salary) else None,
                    "job_growth_rate": float(growth) if pd.notna(growth) else None,
                    "salary_is_placeholder": not salary_ok,
                    "growth_is_placeholder": not growth_ok,
                    "source_record_count": int(row.get("source_record_count") or 0),
                    "description_basis": _clean(row.get("description_basis")),
                    "education_basis": _clean(row.get("education_basis")),
                    "quality_note": _clean(row.get("salary_growth_quality_note")),
                    "text_variant": variant or CAREER_TEXT_VARIANT,
                },
            )
        )
    return chunks


# ── jobs ─────────────────────────────────────────────────────────────────────
def _job_chunks(job: Dict, origin: str, user_id: str = "global", source: str = "jobs") -> List[Chunk]:
    title = _clean(job.get("position") or job.get("Title") or job.get("title"))
    company = _clean(job.get("company") or job.get("Company"))
    location = _clean(job.get("location") or job.get("Location"))
    skills = _clean(job.get("Skills") or job.get("skills"))
    exp = _clean(job.get("Experience") or job.get("experience"))
    salary = _clean(job.get("salary") or job.get("Salary"))
    url = _clean(job.get("jobUrl") or job.get("Link") or job.get("link") or job.get("url"))
    desc = _clean(job.get("description") or job.get("Description"))
    if not title:
        return []
    header = f"Job: {title} at {company or 'unknown company'} ({location or 'location n/a'})."
    if skills:
        header += f" Skills: {skills}."
    if exp:
        header += f" Experience: {exp}."
    if salary:
        header += f" Salary: {salary}."
    meta = {"title": title, "company": company, "location": location, "url": url, "origin": origin}
    key = url or f"{title}|{company}|{location}"
    pieces = split_words(desc) or [""]
    out = []
    for i, piece in enumerate(pieces):
        text = header if not piece else f"{header} Description: {piece}"
        out.append(
            Chunk(
                id=_hash_id(source, user_id, key, str(i)),
                text=text,
                source=source,
                doc_type="job_listing",
                user_id=user_id,
                metadata={**meta, "chunk_index": i},
            )
        )
    return out


def build_job_chunks() -> List[Chunk]:
    chunks: List[Chunk] = []
    for path, origin in [(config.LINKEDIN_JOBS_JSON, "linkedin"), (config.NAUKRI_JOBS_JSON, "naukri")]:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for job in data if isinstance(data, list) else []:
            chunks.extend(_job_chunks(job, origin))
    return chunks


# ── profile (memory.json) ────────────────────────────────────────────────────
def build_profile_chunks(memory_path=config.MEMORY_JSON, user_id: str = config.DEFAULT_USER_ID) -> List[Chunk]:
    if not memory_path.exists():
        return []
    with open(memory_path, encoding="utf-8") as f:
        mem = json.load(f)

    def mk(doc_type: str, key: str, text: str, **meta) -> Chunk:
        return Chunk(
            id=_hash_id("profile", user_id, doc_type, key),
            text=text,
            source="profile",
            doc_type=doc_type,
            user_id=user_id,
            metadata=meta,
        )

    chunks: List[Chunk] = []
    overview = (
        f"Candidate profile overview. Target role: {mem.get('target_role') or 'not specified'}. "
        f"ATS match score: {mem.get('ats_score', 'n/a')}/100. "
        f"Candidate skills: {', '.join(mem.get('candidate_skills') or [])}. "
        f"Skills required by the job description: {', '.join(mem.get('required_skills') or [])}. "
        f"Skill gaps (missing skills): {', '.join(mem.get('skill_gaps') or []) or 'none'}."
    )
    chunks.append(mk("profile_overview", "overview", overview, ats_score=mem.get("ats_score")))

    for i, piece in enumerate(split_words(mem.get("resume_text", ""))):
        chunks.append(mk("resume", str(i), f"Candidate resume (part {i + 1}): {piece}", chunk_index=i))
    for i, piece in enumerate(split_words(mem.get("job_description", ""))):
        chunks.append(mk("job_description", str(i), f"Target job description (part {i + 1}): {piece}", chunk_index=i))

    # skill_resources is a formatted string: blocks "skill: X\nresource: type: title : url ..."
    res_blocks: Dict[str, List[str]] = {}
    res_text = mem.get("skill_resources") or ""
    if isinstance(res_text, str) and res_text.strip():
        for b in re.split(r"(?=^skill:)", res_text, flags=re.M):
            lines = [l.strip() for l in b.strip().splitlines() if l.strip()]
            if lines:
                res_blocks[_clean(lines[0].replace("skill:", ""))] = [l.replace("resource:", "").strip() for l in lines[1:]]

    def _match(skill: str):
        s = skill.lower()
        for k in res_blocks:
            if s in k.lower() or k.lower() in s:
                return k
        return None

    # One chunk per skill gap = plan (search queries) + curated resources with links.
    # (E6: separate plan/resource chunks meant retrieval surfaced plans but never the links.)
    used = set()
    for step in mem.get("learning_path") or []:
        skill = _clean(step.get("skill"))
        queries = "; ".join(step.get("search_queries") or [])
        key = _match(skill)
        res = res_blocks.get(key, []) if key else []
        if key:
            used.add(key)
        text = f"Skill gap '{skill}': learning path and free/curated resources. Suggested searches: {queries}."
        if res:
            text += " Recommended resources: " + " | ".join(res)
        for j, piece in enumerate(split_words(text, max_words=180, overlap=0)):
            chunks.append(mk("learning_path", f"{skill}|{j}", piece, skill=skill))
    for key, res in res_blocks.items():
        if key in used or not res:
            continue
        for j, piece in enumerate(split_words(f"Recommended resources for '{key}': " + " | ".join(res), max_words=180, overlap=0)):
            chunks.append(mk("learning_resource", f"{key}|{j}", piece, skill=key))

    static = mem.get("static_resources") or []
    if static:
        lines = [f"{_clean(r.get('title'))}: {_clean(r.get('link'))}" for r in static if isinstance(r, dict)]
        for j, piece in enumerate(split_words(" | ".join(lines), max_words=180, overlap=0)):
            chunks.append(mk("static_resource", str(j), f"Course search links: {piece}"))

    for job in mem.get("job_listings") or []:
        for c in _job_chunks(job, origin=_clean(job.get("Source")) or "scraped", user_id=user_id, source="profile"):
            c.doc_type = "matched_job"
            chunks.append(c)

    if mem.get("career_summary"):
        chunks.append(mk("career_summary", "summary", f"Career summary for the candidate: {_clean(mem['career_summary'])}"))
    return chunks


# ── knowledge base (markdown guides) ─────────────────────────────────────────
def build_knowledge_chunks(kb_dir=config.KNOWLEDGE_DIR) -> List[Chunk]:
    chunks: List[Chunk] = []
    if not kb_dir.exists():
        return chunks
    for md in sorted(kb_dir.glob("*.md")):
        raw = md.read_text(encoding="utf-8")
        title = md.stem.replace("_", " ").title()
        # split by level-2 headings so each chunk is one self-contained topic
        sections = re.split(r"(?=^## )", raw, flags=re.M)
        for s_idx, section in enumerate(sections):
            heading_match = re.match(r"^##\s+(.*)", section)
            heading = heading_match.group(1).strip() if heading_match else title
            body = re.sub(r"^#+\s.*$", "", section, flags=re.M)
            for p_idx, piece in enumerate(split_words(body)):
                chunks.append(
                    Chunk(
                        id=_hash_id("knowledge", md.name, str(s_idx), str(p_idx)),
                        text=f"{title} - {heading}: {piece}",
                        source="knowledge",
                        doc_type="guide",
                        metadata={"file": md.name, "section": heading},
                    )
                )
    return chunks


BUILDERS = {
    "careers": build_career_chunks,
    "jobs": build_job_chunks,
    "profile": build_profile_chunks,
    "knowledge": build_knowledge_chunks,
}


def build_all(sources: Iterable[str]) -> List[Chunk]:
    out: List[Chunk] = []
    for s in sources:
        out.extend(BUILDERS[s]())
    return out
