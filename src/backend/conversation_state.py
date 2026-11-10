"""
Structured conversation state (E38, docs/evaluation.md Part 3; review 3 §3).

Real students don't restate context: "I prefer the second one", "make it easier", "No. Make me a 30-day plan. I can
study one hour daily." This module rebuilds a small state from the chat history on every turn:

    {"selected_career": "Data Engineer", "last_recommendations": ["Data Analyst", "Data Engineer", "Backend Developer"],
     "reference": {"phrase": "the second one", "resolved": "Data Engineer"}, "known_skills": ["Python", "SQL"],
     "missing_skills": ["Spark", "Airflow"], "daily_minutes": 60, "background": "b.tech cse", "level": None,
     "previous_goals": [], "corrections": [], "conflicts": [], "provenance": {...}}

Rules (from the review):
  * Every field records where it came from: "stated" (the student said it) or "suggested" (the advisor proposed it).
    Advisor suggestions are never treated as confirmed facts about the student.
  * The latest statement wins, and the student can correct anything ("I meant Java, not JavaScript"). A change of goal
    moves the old goal to previous_goals; nothing is deleted from the history.
  * Deterministic (regex + the skills extractor): identical locally, on the deployed app and in keyless mode, no extra
    model call, nothing stored server-side (the chat history is the store).

The state is used three ways: (1) a CONVERSATION STATE block in the prompt, (2) a resolved search query
("the second one" -> "Data Engineer"), (3) the roadmap generator's inputs (career, daily minutes, known/missing skills).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

_ORD = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4, "fifth": 5, "5th": 5, "last": -1}
_ORD_PAT = re.compile(
    r"\b(?:the\s+)?(first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)\s+(?:one|option|choice|career|role|path|item|gap|skill|suggestion|resource|certification)\b"
    r"|\bthe\s+(first|second|third|fourth|fifth|last)\b(?!\s+(?:week|day|time|step|month|thing|year|round|sentence|line))"
    r"|\b(?:number|no\.|option|#|item|point)\s*(\d)\b", re.I)
_LIST_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•]|#{1,4}\s*\d+[.)]?)\s+(.+)$")
_INLINE_LIST = re.compile(r"(?:explore|consider|options? (?:are|include)|such as|could be|try|roles? like)\s+(?:roles? (?:like|such as)\s+)?"
                          r"((?:[A-Z][\w/+.#-]*(?:\s+[A-Z(][\w/+.#()-]*){0,3})(?:,\s*(?:[A-Z][\w/+.#-]*(?:\s+[A-Z(][\w/+.#()-]*){0,3}))+,?\s+(?:or|and)\s+"
                          r"[A-Z][\w/+.#-]*(?:\s+[A-Z(][\w/+.#()-]*){0,3})")
_GOAL = re.compile(r"\b(?:i (?:want|wanna|would like|'d like|plan|hope|aim) to (?:become|be|move into|switch to|get into|work as|transition to|do)|"
                   r"i(?:'d| would) rather (?:do|be|become|go for)|i (?:prefer|choose|pick|'ll go with|will go with|think)|"
                   r"(?:switch|move|transition)(?:ing)? (?:in)?to|i(?:'m| am) (?:aiming|targeting) for)\s+(?:an?\s+|the\s+)?"
                   r"([a-z][a-z/+&. -]{2,40}?)(?=[.,!?;]| now| instead| but| because| suits| sounds| what| where| how| and |$)", re.I)
_CAREERY = re.compile(r"\b(analyst|analytics|engineer|engineering|developer|development|scientist|science|designer|design|manager|"
                      r"management|architect|administrator|tester|testing|security|cybersecurity|devops|cloud|consultant|"
                      r"specialist|researcher|writer|marketing|product|data|ux|ui|web|game|ml|ai|machine learning|backend|frontend)\b", re.I)
_KNOW = re.compile(r"\bi (?:already )?(?:know|have (?:experience|worked) (?:in|with)|am good at|'m good at|have learned|learned|can use|use)\s+"
                   r"([^.;!?]+?)(?=\s+but\b|\s+and (?:want|i|would|need)\b|[.;!?]|$)", re.I)
_DONT = re.compile(r"\b(?:i )?(?:don'?t|do not|never) (?:know|used?|learned|studied|have (?:experience|worked) (?:in|with))\s+"
                   r"([^.;!?]+?)(?=\s+but\b|\s+yet\b|[.;!?]|$)|\bno experience (?:in|with)\s+([^.;!?]+)", re.I)
_CORRECT = re.compile(r"\b(?:i )?meant\s+([\w+#. ]+?),?\s+not\s+([\w+#. ]+?)(?=[.,!?]|$)|\bnot\s+([\w+#. ]+?),?\s+(?:but|i meant)\s+([\w+#. ]+?)(?=[.,!?]|$)", re.I)
_NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "half an": 0.5, "half a": 0.5, "an": 1, "a": 1}
_TIME = re.compile(r"\b(\d+(?:\.\d+)?|one|two|three|four|five|half an?|an|a)\s*[- ]?(hours?|hrs?|hr|h|minutes?|mins?|min)\b", re.I)
_DAILY = re.compile(r"\b(daily|a day|per day|every day|each day|/day|a night|weekdays?|everyday)\b|\bi (?:have|can (?:study|spend|give))\b", re.I)
_BACKGROUND = re.compile(
    r"\b((?:b\.?\s?tech|b\.?e\.?|bsc|b\.?sc|bcom|b\.com|bba|bca|mca|mba|m\.?tech|12th)(?:\s+(?:in\s+)?(?:cse|cs|it|ece|eee|mechanical|civil|"
    r"electrical|electronics|arts|commerce|science|biology))?|(?:mechanical|civil|electrical|electronics|chemical|computer science|"
    r"commerce|arts|biology|nursing) (?:engineering|engineer|student|graduate|background|degree)|(?:teacher|accountant|nurse|"
    r"sales executive|customer support|manual tester|network administrator|graphic designer|civil engineer|mechanical engineer))\b", re.I)
_BEGINNER = re.compile(r"\b(complete |total |absolute )?beginner\b|\bnew to (coding|programming|tech)\b|\bzero knowledge\b|\bfrom scratch\b|\bno (coding|programming) (experience|background)\b", re.I)
_EXPERIENCED = re.compile(r"\b(\d+|one|two|three|four|five)\+?\s*(?:years?|yrs?) (?:of )?(?:experience|exp)\b|\bexperienced\b", re.I)
_YES = re.compile(r"^\s*(yes|yeah|yep|yup|sure|ok(ay)?|y)\b", re.I)
_NO = re.compile(r"^\s*(no|nope|nah|not really|never|none)\b", re.I)
_ASKS_SKILLS = re.compile(r"(?:do you have|have you (?:used|worked with|studied|learned)|are you familiar with)\s+(?:any\s+)?(?:experience\s+(?:with|in)\s+)?([^?]+)\?", re.I)


def _body(text: str) -> str:
    return (text or "").split("\n\n---\n**Sources**")[0]


def _clean_item(t: str) -> str:
    t = re.sub(r"\*\*|__|`", "", t)
    t = re.sub(r"\[S\d+[^\]]*\]", "", t)
    t = re.split(r"\s+[-–—:]\s+|:\s|\s\(|\.\s|\s[-–—]$", t)[0]
    return t.strip(" .*:-–—")


def list_items(text: str) -> List[str]:
    """Items of the last numbered/bulleted list in an assistant turn (career names, gaps, options), else an inline 'X, Y, or Z'."""
    body = _body(text)
    blocks: List[List[str]] = [[]]
    for line in body.splitlines():
        m = _LIST_LINE.match(line)
        if m and "[S" not in line[:6]:
            item = _clean_item(m.group(1))
            if 1 <= len(item.split()) <= 8:
                blocks[-1].append(item)
        elif line.strip() and blocks[-1] and not line.startswith((" ", "\t")):
            blocks.append([])
    found = [b for b in blocks if len(b) >= 2]
    if found:
        return found[0]  # the first list in a reply is the answer's options; later lists are usually details/next steps
    m = _INLINE_LIST.search(body)
    if m:
        return [x.strip(" .") for x in re.split(r",\s*(?:or\s+|and\s+)?|\s+(?:or|and)\s+", m.group(1)) if x.strip(" .")]
    return []


def _skills(text: str) -> List[str]:
    from src.rag.skill_rerank import query_skills
    from src.skills.normalizer import normalize_all
    found = normalize_all(sorted(query_skills(text)))
    return [s.upper() if s.lower() in ("sql", "aws", "gcp", "html", "css", "dsa") else s for s in found]


def _minutes(text: str) -> Optional[int]:
    best = None
    for sent in re.split(r"(?<=[.!?;])\s+|,\s*", text):
        if not _DAILY.search(sent) and not re.fullmatch(r"\s*(i have\s+)?" + _TIME.pattern + r".*", sent.strip(), re.I):
            continue
        for num, unit in _TIME.findall(sent):
            n = float(num) if num[0].isdigit() else _NUMW.get(num.lower(), 1)
            mins = int(round(n * 60)) if unit.lower().startswith("h") else int(n)
            if 10 <= mins <= 600:
                if re.search(r"weekdays?", sent, re.I) or best is None:
                    best = mins
    return best


def _ordinal(msg: str, items: List[str]) -> Optional[Dict]:
    m = _ORD_PAT.search(msg)
    if not m or not items:
        return None
    tok = (m.group(1) or m.group(2) or m.group(3) or "").lower()
    n = int(tok) if tok.isdigit() else _ORD.get(tok)
    if n is None:
        return None
    idx = len(items) - 1 if n == -1 else n - 1
    if not 0 <= idx < len(items):
        return None
    return {"phrase": m.group(0).strip(), "index": idx + 1, "resolved": items[idx]}


def build_state(history: List[Dict], message: str) -> Dict:
    """State after the student's latest `message`, from the earlier turns in `history` (oldest first)."""
    st: Dict = {"selected_career": None, "last_recommendations": [], "reference": None, "known_skills": [], "missing_skills": [],
                "daily_minutes": None, "background": None, "level": None, "previous_goals": [], "corrections": [], "conflicts": [],
                "provenance": {}}
    turns = [m for m in history if m.get("role") in ("user", "assistant") and m.get("content")] + [{"role": "user", "content": message}]
    known: Dict[str, str] = {}
    last_items: List[str] = []
    last_assistant = ""
    beginner_said = experienced_said = None
    for t in turns:
        text = t["content"]
        if t["role"] == "assistant":
            items = list_items(text)
            if items:
                last_items = items
            last_assistant = _body(text)
            continue
        low = text.lower()
        # corrections first ("I meant Java, not JavaScript")
        for a, b, c, d in _CORRECT.findall(text):
            new, old = (a, b) if a else (d, c)
            if new and old:
                st["corrections"].append(f"'{old.strip()}' -> '{new.strip()}'")
                for s in _skills(old):
                    known.pop(s.lower(), None)
                for s in _skills(new):
                    known[s.lower()] = s
                if st["selected_career"] and old.strip().lower() in st["selected_career"].lower():
                    st["selected_career"] = new.strip()
        for clause in _KNOW.findall(text):
            if re.search(r"\b(don'?t|do not|never)\b", clause):
                continue
            for s in _skills(clause):
                known[s.lower()] = s
                st["missing_skills"] = [x for x in st["missing_skills"] if x.lower() != s.lower()]
        for a, b in _DONT.findall(text):
            for s in _skills(a or b):
                known.pop(s.lower(), None)
                if s.lower() not in {x.lower() for x in st["missing_skills"]}:
                    st["missing_skills"].append(s)
        # a bare "No"/"Yes" answering "Do you have experience with X, Y or Z?"
        q = _ASKS_SKILLS.search(last_assistant or "")
        if q and (_NO.match(text) or _YES.match(text)):
            for s in _skills(q.group(1)):
                if _NO.match(text):
                    known.pop(s.lower(), None)
                    if s.lower() not in {x.lower() for x in st["missing_skills"]}:
                        st["missing_skills"].append(s)
                elif not re.search(r"\b(but|except|only)\b", low):
                    known[s.lower()] = s
        mins = _minutes(text)
        if mins:
            if st["daily_minutes"] and st["daily_minutes"] != mins:
                st["corrections"].append(f"daily study time {st['daily_minutes']} -> {mins} minutes")
            st["daily_minutes"] = mins
            st["provenance"]["daily_minutes"] = "stated"
            st["time_note"] = re.sub(r"\s+", " ", text.strip())[:120] if re.search(r"weekend|weekday", low) else None
        bg = _BACKGROUND.search(text)
        if bg:
            st["background"] = bg.group(1).strip()
            st["provenance"]["background"] = "stated"
        if _BEGINNER.search(text):
            beginner_said, st["level"] = text.strip()[:80], "beginner"
        if _EXPERIENCED.search(text):
            experienced_said, st["level"] = text.strip()[:80], "experienced"
        # references to the advisor's last list, and explicit goals
        ref = _ordinal(text, last_items)
        goal = None
        if ref:
            goal = ref["resolved"]
            st["reference"] = ref
        for g in _GOAL.findall(text):
            g = g.strip(" .")
            if _CAREERY.search(g) and not _ORD_PAT.search(g) and not re.match(r"(it|that|this|one|them|those|so)\b", g):
                goal = g
        if goal:
            if st["selected_career"] and goal.lower() != st["selected_career"].lower():
                st["previous_goals"].append(st["selected_career"])
            st["selected_career"] = goal
            st["provenance"]["selected_career"] = "stated (picked from your list)" if ref and goal == ref["resolved"] else "stated"
    if last_items:
        st["last_recommendations"] = last_items
    st["known_skills"] = [v for k, v in known.items() if k not in {x.lower() for x in st["missing_skills"]}]
    if beginner_said and experienced_said:
        st["conflicts"].append(f"the student said \"{beginner_said}\" and also \"{experienced_said}\"")
    # the reference only matters if it is in the CURRENT message
    if st["reference"] and not _ORD_PAT.search(message):
        st["reference"] = None
    return st


def resolved_message(message: str, st: Dict) -> str:
    """The message with references made explicit, for intent detection and retrieval ("the second one" -> "Data Engineer")."""
    out = message
    if st.get("reference"):
        out = out.replace(st["reference"]["phrase"], st["reference"]["resolved"], 1)
    words = re.findall(r"[a-z]+", out.lower())
    has_topic = bool(_CAREERY.search(out)) or bool(_skills(out))
    if st.get("selected_career") and st["selected_career"].lower() not in out.lower() and (len(words) <= 12 and not has_topic):
        out = f"{out} ({st['selected_career']})"
    return out


def state_block(st: Dict, intent: Optional[Dict] = None) -> str:
    """CONVERSATION STATE lines for the prompt; empty when nothing useful is known."""
    L = []
    if st.get("reference"):
        r = st["reference"]
        L.append(f"- \"{r['phrase']}\" = **{r['resolved']}** (item {r['index']} of your last list: {'; '.join(st['last_recommendations'])}). "
                 f"Name it explicitly in your first sentence.")
    if st.get("selected_career"):
        L.append(f"- Current goal / selected career: {st['selected_career']} ({st['provenance'].get('selected_career', 'stated')}).")
    if st.get("previous_goals"):
        L.append(f"- The student changed goal: earlier {', '.join(st['previous_goals'])}; answer for the CURRENT goal only.")
    if st.get("known_skills"):
        L.append(f"- Skills the student said they have: {', '.join(st['known_skills'])} (stated in chat; don't re-teach them).")
    if st.get("missing_skills"):
        L.append(f"- Skills the student said they do NOT have yet: {', '.join(st['missing_skills'])}.")
    if st.get("daily_minutes"):
        note = f" Schedule as stated: \"{st['time_note']}\"." if st.get("time_note") else ""
        L.append(f"- Daily study time: {st['daily_minutes']} minutes (stated).{note} Every plan must fit it and say so.")
    if st.get("background"):
        L.append(f"- Background: {st['background']} (stated).")
    if st.get("level"):
        L.append(f"- Level: {st['level']} (stated)."
                 + (" Simpler means SHORTER: plain words, one everyday example, about 150 words unless they ask for more." if st["level"] == "beginner" else ""))
    for c in st.get("corrections", []):
        L.append(f"- Correction by the student: {c}. Use the corrected fact.")
    for c in st.get("conflicts", []):
        L.append(f"- Conflicting statements: {c}. Point this out briefly and follow the most recent one (or ask).")
    if intent and intent.get("primary_intent") == "learning_plan" and not st.get("daily_minutes") and \
            not re.search(r"\b\d+\s*(min|minutes|h|hrs?|hours?)\b", " ".join(intent.get("parts", []))):
        L.append("- The student has not said how much time they have per day: build the plan for 60 minutes/day, say that assumption "
                 "in the first line, and end by asking how many minutes a day they can really study.")
    if not L:
        return ""
    return ("CONVERSATION STATE (rebuilt from this chat; 'stated' = the student said it; your own earlier suggestions are not "
            "facts about the student; the student can correct anything):\n" + "\n".join(L))
