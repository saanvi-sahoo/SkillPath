import streamlit as st
import requests
import tempfile
import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path so we can import from src (must come BEFORE any `from src...` import:
# `streamlit run` and Streamlit Cloud only put the script's own folder on sys.path)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# E31: Streamlit Cloud pulls new code on every push but keeps the same Python process. Modules imported by
# an earlier version stay cached in sys.modules, so new code importing new names from them fails with
# ImportError (seen live: byok_ui -> llm_provider). Fingerprint src/ and drop stale `src.*` modules when it changes.
def _src_fingerprint() -> str:
    import hashlib
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    h = hashlib.sha1()
    for dirpath, _, files in os.walk(root):
        for f in sorted(files):
            if f.endswith(".py"):
                p = os.path.join(dirpath, f)
                st_ = os.stat(p)
                h.update(f"{p}:{st_.st_mtime_ns}:{st_.st_size}".encode())
    return h.hexdigest()


_fp = _src_fingerprint()
# At this point of a run no `src.*` module has been imported by THIS run yet, so any already in sys.modules
# come from an earlier run; if the code changed (or the earlier version predates this guard) drop them all.
if getattr(sys, "_skillpath_src_fp", None) != _fp:
    for _name in [m for m in list(sys.modules) if m == "src" or m.startswith("src.")]:
        del sys.modules[_name]
sys._skillpath_src_fp = _fp

# Load environment variables
from src.utilities.env import load_env; load_env()

# --- MONKEY PATCH FOR LANGCHAIN VERSION BUG ---
import langchain_core.exceptions
if not hasattr(langchain_core.exceptions, "ContextOverflowError"):
    class ContextOverflowError(Exception): pass
    langchain_core.exceptions.ContextOverflowError = ContextOverflowError
# ----------------------------------------------

from src.frontend.advisor_ui import render_career_advisor
from src.frontend.byok_ui import apply_session_llm, render_byok_sidebar
st.set_page_config(page_title="SkillPath AI", page_icon=":material/school:", layout="wide")

st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>SkillPath AI</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1rem;'>Your AI career & study advisor: chat about careers anytime, "
            "or upload your CV and a job description for skill gaps, job matches and a 30-day roadmap.</p>", unsafe_allow_html=True)

# ---- PERSISTENT STATE
@st.cache_resource
def get_persistent_state():
    return {}

# E26: one id per visitor (kept in the URL so a refresh keeps your own data). Every profile file,
# private vector chunk and cached result is keyed by it, so visitors never see each other's analysis.
import uuid as _uuid
if "uid" not in st.session_state:
    st.session_state["uid"] = st.query_params.get("u") or _uuid.uuid4().hex[:16]
if st.query_params.get("u") != st.session_state["uid"]:
    st.query_params["u"] = st.session_state["uid"]
UID = st.session_state["uid"]
apply_session_llm()  # E29: this visitor's own API key (if any) for this run only
persistent_state = get_persistent_state().setdefault(UID, {})

# Sync persistent state to session state so results survive page refresh
if "pipeline_data" not in st.session_state and "pipeline_data" in persistent_state:
    st.session_state["pipeline_data"] = persistent_state["pipeline_data"]
    st.session_state["analyzed_fp"] = persistent_state.get("analyzed_fp")
    st.session_state["analyzed_meta"] = persistent_state.get("analyzed_meta")

# ---- SIDEBAR (INPUT)
with st.sidebar:
    st.header("Profile Analysis")
    st.caption("Optional. The Career Advisor works without it, but with your CV and a target job it can give "
               "personal advice (ATS estimate, skill gaps, matched jobs, 30-day roadmap).")
    
    uploaded_files = st.file_uploader(
        "Upload CV",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=False,
        help="Supported formats: PDF, DOCX, TXT."
    )

    with st.expander("Or paste CV text directly"):
        user_text = st.text_area("Paste CV text here...", height=150)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    uploaded_jd_file = st.file_uploader(
        "Upload Job Description",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=False,
        help="Supported formats: PDF, DOCX, TXT."
    )
    
    with st.expander("Or paste JD text/URL directly"):
        jd_input = st.text_area("Job Description (Paste Text or URL)", placeholder="e.g., https://linkedin.com/... or paste text", height=150)
    
    job_pref = st.text_input("Target Role", placeholder="e.g., Senior Software Engineer")
    
    analyze_btn = st.button("Analyze Profile", type="primary", use_container_width=True)
render_byok_sidebar()

# ---- PROFILE LIFECYCLE (E33): fingerprint inputs, detect stale / removed inputs, clear on request ----
from src.backend.pipeline_service import clear_profile as _clear_profile, input_fingerprint as _fingerprint
_cv_part = uploaded_files.getvalue() if uploaded_files else (user_text or "")
_jd_part = uploaded_jd_file.getvalue() if uploaded_jd_file else (jd_input or "")
INPUT_FP = _fingerprint(_cv_part, _jd_part, job_pref)
_has_inputs = bool(_cv_part) or bool(_jd_part)


def _forget_profile(reason: str):
    for k in ("pipeline_data", "roadmap", "analyzed_fp", "analyzed_meta"):
        st.session_state.pop(k, None)
    for k in ("pipeline_data", "job_pref", "analyzed_fp", "analyzed_meta"):
        persistent_state.pop(k, None)
    _clear_profile(UID)
    st.session_state["_profile_notice"] = reason


with st.sidebar:
    if uploaded_files and user_text:
        st.caption(":material/info: Using the **uploaded CV file**; remove it to analyse the pasted text instead.")
    if uploaded_jd_file and jd_input:
        st.caption(":material/info: Using the **uploaded JD file**; remove it to analyse the pasted text instead.")
    if "pipeline_data" in st.session_state and st.button(":material/delete: Clear profile", use_container_width=True,
                                                          help="Forget this analysis (also removes it from the chatbot's memory)"):
        _forget_profile("Profile cleared.")
        st.rerun()

if _has_inputs:
    st.session_state["_had_inputs"] = True
elif st.session_state.get("_had_inputs") and "pipeline_data" in st.session_state:
    # the visitor removed both CV and JD in this session (not just a page refresh) -> drop the old profile
    st.session_state["_had_inputs"] = False
    _forget_profile("The CV and job description were removed, so the previous profile was cleared.")
if st.session_state.get("_profile_notice"):
    st.info(st.session_state.pop("_profile_notice"))

# ---- MAIN AREA
if analyze_btn or st.session_state.pop("_reanalyze", False):
    if not (uploaded_files or user_text):
        st.warning("Please upload a CV or paste CV text.")
    elif not (uploaded_jd_file or jd_input):
        st.warning("Please upload a Job Description or paste JD text/URL.")
    else:
        resume_input = ""
        temp_dir = tempfile.gettempdir()
        if uploaded_files:
            temp_path = os.path.join(temp_dir, f"skillpath_{UID}_{INPUT_FP}_cv_{os.path.basename(uploaded_files.name)}")  # E33: no cross-visitor collisions
            with open(temp_path, "wb") as f:
                f.write(uploaded_files.getvalue())
            resume_input = temp_path
        else:
            resume_input = user_text
            
        jd_input_final = ""
        if uploaded_jd_file:
            temp_path_jd = os.path.join(temp_dir, f"skillpath_{UID}_{INPUT_FP}_jd_{os.path.basename(uploaded_jd_file.name)}")
            with open(temp_path_jd, "wb") as f:
                f.write(uploaded_jd_file.getvalue())
            jd_input_final = temp_path_jd
        else:
            jd_input_final = jd_input
            
        loading_placeholder = st.empty()
        
        loading_html = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0');
        
        .loader-overlay {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 40px;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            border-radius: 16px;
            border: 1px solid #cbd5e1;
            margin: 20px 0;
        }
        
        .loader-title {
            font-size: 24px;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .loader-spinner {
            animation: spin 1s linear infinite;
            color: #3b82f6;
        }
        
        @keyframes spin {
            100% { transform: rotate(360deg); }
        }
        
        .process-steps {
            display: flex;
            flex-direction: column;
            gap: 8px;
            width: 100%;
            max-width: 450px;
            align-items: center;
        }
        
        .step-item {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 16px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            opacity: 0.4;
            width: 100%;
            border: 1px solid transparent;
            animation: highlight-item 0.5s forwards;
        }
        
        .step-arrow {
            color: #94a3b8;
            font-size: 24px;
            display: flex;
            justify-content: center;
            opacity: 0.4;
            animation: highlight-arrow 0.5s forwards;
        }

        .process-steps > div:nth-child(1) { animation-delay: 0s; }
        .process-steps > div:nth-child(2) { animation-delay: 2s; }
        .process-steps > div:nth-child(3) { animation-delay: 2.5s; }
        .process-steps > div:nth-child(4) { animation-delay: 4.5s; }
        .process-steps > div:nth-child(5) { animation-delay: 5s; }
        .process-steps > div:nth-child(6) { animation-delay: 7s; }
        .process-steps > div:nth-child(7) { animation-delay: 7.5s; }
        
        @keyframes highlight-item {
            to { 
                opacity: 1; 
                transform: scale(1.02); 
                border-color: #bfdbfe; 
                box-shadow: 0 10px 15px -3px rgb(59 130 246 / 0.2); 
            }
        }

        @keyframes highlight-arrow {
            to { 
                opacity: 1; 
                color: #3b82f6; 
                transform: translateY(4px); 
            }
        }
        
        .step-icon {
            font-size: 24px;
            color: #3b82f6;
        }
        
        .step-text {
            font-weight: 500;
            color: #334155;
            font-size: 16px;
        }
        </style>
        
        <div class="loader-overlay">
            <div class="loader-title">
                <span class="material-symbols-rounded loader-spinner">progress_activity</span>
                Processing Your Profile...
            </div>
            <div class="process-steps">
                <div class="step-item">
                    <span class="material-symbols-rounded step-icon">description</span>
                    <span class="step-text">Parsing Resume & Job Description</span>
                </div>
                <div class="step-arrow"><span class="material-symbols-rounded">arrow_downward</span></div>
                <div class="step-item">
                    <span class="material-symbols-rounded step-icon">psychology</span>
                    <span class="step-text">AI Skill Gap Analysis</span>
                </div>
                <div class="step-arrow"><span class="material-symbols-rounded">arrow_downward</span></div>
                <div class="step-item">
                    <span class="material-symbols-rounded step-icon">travel_explore</span>
                    <span class="step-text">Scraping Web for Jobs & Resources</span>
                </div>
                <div class="step-arrow"><span class="material-symbols-rounded">arrow_downward</span></div>
                <div class="step-item">
                    <span class="material-symbols-rounded step-icon">auto_awesome</span>
                    <span class="step-text">Synthesizing Career Summary</span>
                </div>
            </div>
        </div>
        """
        
        loading_placeholder.markdown(loading_html, unsafe_allow_html=True)
        
        from src.backend.pipeline_service import API_URL, PIPELINE_MODE, run_and_persist_sync

        def _store(data):
            import datetime as _dt
            meta = {"at": _dt.datetime.now().strftime("%d %b %H:%M"),
                    "cv": f"file '{uploaded_files.name}'" if uploaded_files else "pasted text",
                    "jd": f"file '{uploaded_jd_file.name}'" if uploaded_jd_file else ("URL" if str(jd_input).strip().startswith("http") else "pasted text")}
            st.session_state["pipeline_data"] = data
            st.session_state["analyzed_fp"] = INPUT_FP
            st.session_state["analyzed_meta"] = meta
            st.session_state.pop("roadmap", None)  # E33: an old roadmap must not survive a new analysis
            persistent_state.update(pipeline_data=data, job_pref=job_pref, analyzed_fp=INPUT_FP, analyzed_meta=meta)

        payload = {"resume_input": resume_input, "jd_input": jd_input_final, "target_role": job_pref, "location": "",
                   "user_id": UID}
        try:
            data, api_unreachable = None, False
            from src.utilities.llm_provider import session_llm as _sess
            mode = "inprocess" if _sess() else PIPELINE_MODE  # E29: the API server can't see this visitor's key
            if mode in ("api", "auto"):
                try:
                    response = requests.post(f"{API_URL}/pipeline/run", json=payload, timeout=600)
                    if response.status_code == 200:
                        data = response.json()
                    else:
                        st.error(f"Error from backend: {response.text}")
                except requests.exceptions.ConnectionError:
                    if mode == "api":
                        raise
                    api_unreachable = True
            if mode == "inprocess" or (mode == "auto" and api_unreachable):
                data = run_and_persist_sync(**payload)  # no API server reachable: run the pipeline here
            if data is not None:
                _store(data)
        except Exception as e:
            from src.utilities.llm_provider import redact as _redact, session_llm as _sess2
            st.error(f"Pipeline failed: {_redact(str(e), (_sess2() or {}).get('api_key', ''))}")
        finally:
            loading_placeholder.empty()

if "pipeline_data" in st.session_state:
    data = st.session_state["pipeline_data"]
    
    extracted_skills = data.get("candidate_skills", [])
    required_skills = data.get("required_skills", [])
    skill_gaps = data.get("skill_gaps", [])
    ats_score = data.get("ats_score", 0)
    job_listings = data.get("job_listings", [])
    static_resources = data.get("static_resources", [])
    career_summary = data.get("career_summary", "")
    
    st.markdown("---")
    
    st.subheader("Profile Overview")
    _meta = st.session_state.get("analyzed_meta") or {}
    if _meta:
        st.caption(f":material/history: Analysed {_meta.get('at')} from CV ({_meta.get('cv')}) and JD ({_meta.get('jd')}).")
    if _has_inputs and st.session_state.get("analyzed_fp") and st.session_state["analyzed_fp"] != INPUT_FP:
        _c1, _c2 = st.columns([4, 1], vertical_alignment="center")
        _c1.warning("Your CV, job description or target role changed since this analysis. "
                    "The profile below still shows the **previous** inputs.")
        if _c2.button(":material/refresh: Re-analyse now", type="primary", use_container_width=True):
            st.session_state["_reanalyze"] = True
            st.rerun()
    
    # Career Summary
    if career_summary:
        st.info(career_summary)
        
    m1, m2, m3, m4 = st.columns(4)
    saved_job_pref = persistent_state.get("job_pref", job_pref)
    with m1:
        st.metric(label="Target Role", value=saved_job_pref if saved_job_pref else "Not specified")
    with m2:
        st.metric(label="Skills Found", value=str(len(extracted_skills)))
    with m3:
        st.metric(label="ATS Match Score", value=f"{ats_score}%")
    with m4:
        st.metric(label="Job Matches", value=str(len(job_listings)) if job_listings else "0")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ---- TABS ----
    TABS = st.tabs([
        ":material/forum: Career Advisor",
        ":material/query_stats: Skills Analysis",
        ":material/work: Job Matches",
        ":material/school: Learning Paths & 30-Day Roadmap",
    ])
    tab1, tab2, tab3 = TABS[1], TABS[2], TABS[3]
    
    with tab1:
        st.markdown("#### Skill Match Breakdown")
        # Helper to group "Category: Skill" lists
        def group_skills(skills_list):
            groups = {}
            for item in skills_list:
                if ":" in item:
                    cat, skill = item.split(":", 1)
                    groups.setdefault(cat.strip(), []).append(skill.strip())
                else:
                    groups.setdefault("Other", []).append(item.strip())
            return groups

        c1, c2 = st.columns(2)
        with c1:
            st.success("**Verified Skills (You possess these)**")
            if extracted_skills:
                grouped = group_skills(extracted_skills)
                for cat, skills in grouped.items():
                    st.markdown(f"**{cat}**")
                    st.markdown(" ".join([f"`{skill}`" for skill in skills]))
            else:
                st.write("No technical skills detected.")
        with c2:
            st.warning("**Skill Gaps (Recommended to learn)**")
            if skill_gaps:
                grouped = group_skills(skill_gaps)
                for cat, skills in grouped.items():
                    st.markdown(f"**{cat}**")
                    st.markdown(" ".join([f"`{skill}`" for skill in skills]))
            else:
                st.write("No major skill gaps detected!")
                
        with st.expander("View Extracted Raw Text"):
            st.text("RESUME TEXT:\n" + data.get("resume_text", ""))
            st.text("\n\nJD TEXT:\n" + data.get("job_description", ""))
            
    with tab2:
        st.markdown("#### Recommended Opportunities")
        if not job_listings:
            st.info("No jobs found for this role/location right now.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                time_filter = st.selectbox("Time Updated", ["Any time", "Past 24 hours", "Past week", "Past month"])
            with col2:
                exp_filter = st.selectbox("Experience Required", ["Any", "Entry level", "Mid level", "Senior"])
                
            filtered_jobs = []
            for job in job_listings:
                keep = True
                t_str = str(job.get("Experience", "")).lower() + " " + str(job.get("Description", "")).lower()
                e_str = str(job.get("Experience", "")).lower() + " " + str(job.get("Title", "")).lower()
                
                if time_filter != "Any time":
                    if time_filter == "Past 24 hours" and not any(w in t_str for w in ["hour", "day", "just now", "today", "recent"]):
                        keep = False
                    elif time_filter == "Past week" and not any(w in t_str for w in ["hour", "day", "week", "just now", "today", "recent"]):
                        keep = False
                    elif time_filter == "Past month" and not any(w in t_str for w in ["hour", "day", "week", "month", "just now", "today", "recent"]):
                        keep = False
                        
                if keep and exp_filter != "Any":
                    if exp_filter == "Entry level" and any(w in e_str for w in ["senior", "lead", "manager", "principal", "3 yr", "4 yr", "5 yr"]):
                        keep = False
                    elif exp_filter == "Mid level" and any(w in e_str for w in ["intern", "fresher", "student"]):
                        keep = False
                    elif exp_filter == "Senior" and not any(w in e_str for w in ["senior", "lead", "manager", "principal", "architect", "5 yr", "6 yr", "10 yr"]):
                        keep = False
                        
                if keep:
                    filtered_jobs.append(job)

            if not filtered_jobs:
                st.info("No jobs match the selected filters.")
            else:
                if "job_limit" not in st.session_state:
                    st.session_state["job_limit"] = 5
                    
                displayed_jobs = filtered_jobs[:st.session_state["job_limit"]]
                
                for i, job in enumerate(displayed_jobs):
                    with st.container(border=True):
                        colA, colB = st.columns([3, 1])
                        with colA:
                            st.markdown(f"### {job.get('Title', 'Unknown Title')}")
                            source_bg = "#E0F2FE" if job.get("Source") == "LinkedIn" else "#FFEDD5"
                            source_fg = "#0369A1" if job.get("Source") == "LinkedIn" else "#C2410C"
                            source_icon = "link" if job.get("Source") == "LinkedIn" else "work"
    
                            st.markdown(
                                f"""
                                <style>
                                @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20,400,0,0');
                                </style>
                                <div style='margin-top: 8px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap;'>
                                    <span style='background-color: #DBEAFE; color: #1E3A8A; padding: 4px 10px; border-radius: 16px; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 4px;'>
                                        <span class="material-symbols-rounded" style="font-size: 16px;">business</span> {job.get('Company', 'Unknown Company')}
                                    </span>
                                    <span style='background-color: #FEF3C7; color: #92400E; padding: 4px 10px; border-radius: 16px; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 4px;'>
                                        <span class="material-symbols-rounded" style="font-size: 16px;">location_on</span> {job.get('Location', 'Unknown Location')}
                                    </span>
                                    <span style='background-color: #E2E8F0; color: #475569; padding: 4px 10px; border-radius: 16px; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 4px;'>
                                        <span class="material-symbols-rounded" style="font-size: 16px;">schedule</span> {job.get('Experience', 'Not specified')}
                                    </span>
                                    <span style='background-color: {source_bg}; color: {source_fg}; padding: 4px 10px; border-radius: 16px; font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 4px;'>
                                        <span class="material-symbols-rounded" style="font-size: 16px;">{source_icon}</span> {job.get('Source', 'Unknown Source')}
                                    </span>
                                </div>
                                """, 
                                unsafe_allow_html=True
                            )
                            st.caption(job.get('Description', ''))
                        with colB:
                            st.markdown(f"<h4 style='color: #059669; margin-bottom: 0;'>{job.get('Salary', 'Not Disclosed')}</h4>", unsafe_allow_html=True)
                            st.markdown("<br>", unsafe_allow_html=True)
                            if job.get('Link') and job.get('Link') != 'N/A':
                                st.link_button("Apply Now", job['Link'], type="primary", use_container_width=True)
                            else:
                                st.button("No Link", disabled=True, key=f"job_no_link_{i}")
                                
                if st.session_state["job_limit"] < len(filtered_jobs):
                    if st.button("Load More Jobs", use_container_width=True):
                        st.session_state["job_limit"] += 5
                        st.rerun()

    with tab3:
        st.markdown("#### Recommended Learning Paths")
        
        dynamic_res = []
        raw_res = data.get("skill_resources", "")
        for line in raw_res.split("\n"):
            line = line.strip()
            if line.startswith("resource:"):
                parts = line.replace("resource:", "", 1).split(" : ", 1)
                if len(parts) == 2:
                    dynamic_res.append({"title": parts[0].strip(), "link": parts[1].strip(), "Source": "Web Search"})
        
        # Assign source to static resources
        for sr in static_resources:
            if "udemy.com" in sr.get("link", ""):
                sr["Source"] = "Udemy"
            elif "youtube.com" in sr.get("link", ""):
                sr["Source"] = "YouTube"
            elif "coursera.org" in sr.get("link", ""):
                sr["Source"] = "Coursera"
            else:
                sr["Source"] = "Resource"
                
        combined_resources = static_resources + dynamic_res
        unique_resources = {res["link"]: res for res in combined_resources}.values()
        top_10 = list(unique_resources)[:10]
        
        if not top_10:
            st.info("No resources found.")
        else:
            cols = st.columns(3)
            for i, res in enumerate(top_10):
                col = cols[i % 3]
                with col:
                    with st.container(border=True):
                        st.markdown(f"**{res.get('title', 'Course')}**")
                        
                        source = res.get("Source", "Resource")
                        if source == "Udemy":
                            s_bg, s_fg, s_icon = "#FCE7F3", "#9D174D", "menu_book"
                        elif source == "Coursera":
                            s_bg, s_fg, s_icon = "#DBEAFE", "#1E3A8A", "school"
                        elif source == "YouTube":
                            s_bg, s_fg, s_icon = "#FEE2E2", "#991B1B", "play_circle"
                        else:
                            s_bg, s_fg, s_icon = "#F3F4F6", "#374151", "travel_explore"
                            
                        st.markdown(
                            f"""
                            <style>
                            @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20,400,0,0');
                            </style>
                            <div style='margin-bottom: 12px;'>
                                <span style='background-color: {s_bg}; color: {s_fg}; padding: 4px 10px; border-radius: 16px; font-size: 13px; font-weight: 500; display: inline-flex; align-items: center; gap: 4px;'>
                                    <span class="material-symbols-rounded" style="font-size: 16px;">{s_icon}</span> {source}
                                </span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        st.link_button("View Resource", res.get("link", "#"), use_container_width=True)

        # ---- 30-day roadmap (src/roadmap/generator.py, project doc section 11) ----
        st.divider()
        st.markdown("#### 30-Day Personalised Roadmap")
        st.caption("Prioritised by prerequisites and by how often each gap skill appears in career records for your target role. "
                   "30 days builds working familiarity, not mastery.")
        rc1, rc2 = st.columns(2)
        rm_minutes = rc1.slider("Daily study time (minutes)", 30, 240, 90, step=15, key="rm_minutes")
        rm_level = rc2.selectbox("Your current level", ["beginner", "intermediate", "advanced"], key="rm_level")
        if st.button("Generate 30-day roadmap", type="primary", key="rm_btn"):
            from src.roadmap.generator import generate_roadmap
            from src.utilities.llm_provider import llm_provider as _lp
            _eta = "up to ~75 s (AI-written plan)" if _lp() in ("api", "byok") else "a few seconds"
            with st.spinner(f"Planning your 30 days ({_eta})..."):
                st.session_state["roadmap"] = generate_roadmap(
                    data.get("target_role") or "", data.get("candidate_skills") or [],
                    required_skills=data.get("required_skills") or [], gaps=None if data.get("required_skills") else data.get("skill_gaps"),
                    daily_minutes=rm_minutes, level=rm_level, user_id=UID)
        rm = st.session_state.get("roadmap")
        if rm:
            v = rm["validation"]
            # E32: a plain statement, not a bare `a if c else b` expression. Streamlit "magic" tried to display
            # the returned element and crashed under Python 3.14 on Streamlit Cloud (SyntaxError via ast.parse).
            if v["valid"]:
                _how = "written by the AI model" if rm.get("generation") == "llm" else "built from our skill curricula"
                st.success(f"Valid plan: {v['checks']['n_days']} days, all gaps covered, max {v['checks']['max_minutes']} min/day ({_how})")
            else:
                st.warning("Plan repaired: " + "; ".join(v["issues"][:3]))
            if rm.get("deferred_gaps"):
                st.info("Deferred to a second month: " + ", ".join(rm["deferred_gaps"]))
            import pandas as _pd
            st.dataframe(_pd.DataFrame(rm["days"])[["day", "kind", "skill", "topic", "learning_task", "practice_task",
                                                   "estimated_minutes", "completion_criteria"]],
                         hide_index=True, use_container_width=True)

else:
    TABS = st.tabs([
        ":material/forum: Career Advisor",
        ":material/query_stats: Skills Analysis",
        ":material/work: Job Matches",
        ":material/school: Learning Paths & 30-Day Roadmap",
    ])
    for _t, _what in ((TABS[2], "matched LinkedIn/Naukri jobs"), (TABS[3], "learning paths and your 30-day roadmap")):
        with _t:
            st.info(f"Upload your CV and a job description in the sidebar, then click **Analyze Profile** to see {_what}.")
    with TABS[1]:
        st.info("Upload your CV and JD in the sidebar, then click **Analyze Profile**. Meanwhile, the **Career Advisor** tab is ready for questions.")
    
        graph_svg = """
        <div style='display: flex; justify-content: center; padding: 40px; background-color: #F8FAFC; border-radius: 12px; border: 1px solid #E2E8F0; margin-top: 20px; margin-bottom: 30px;'>
            <svg width="600" height="400" viewBox="0 0 600 400" fill="none" xmlns="http://www.w3.org/2000/svg">
                <!-- Paths / Edges -->
                <path d="M 300 50 L 200 120" stroke="#CBD5E1" stroke-width="2" />
                <path d="M 300 50 L 400 120" stroke="#CBD5E1" stroke-width="2" />
                <path d="M 200 160 L 300 230" stroke="#CBD5E1" stroke-width="2" />
                <path d="M 400 160 L 300 230" stroke="#CBD5E1" stroke-width="2" />
                <path d="M 300 270 L 150 340" stroke="#CBD5E1" stroke-width="2" />
                <path d="M 300 270 L 300 340" stroke="#CBD5E1" stroke-width="2" />
                <path d="M 300 270 L 450 340" stroke="#CBD5E1" stroke-width="2" />
                <!-- Animated Data Flow -->
                <path d="M 300 50 L 200 120" stroke="#3B82F6" stroke-width="3" stroke-dasharray="10 10">
                    <animate attributeName="stroke-dashoffset" from="100" to="0" dur="2s" repeatCount="indefinite" />
                </path>
                <path d="M 300 50 L 400 120" stroke="#3B82F6" stroke-width="3" stroke-dasharray="10 10">
                    <animate attributeName="stroke-dashoffset" from="100" to="0" dur="2s" repeatCount="indefinite" />
                </path>
                <path d="M 200 160 L 300 230" stroke="#10B981" stroke-width="3" stroke-dasharray="10 10">
                    <animate attributeName="stroke-dashoffset" from="100" to="0" dur="2s" repeatCount="indefinite" />
                </path>
                <path d="M 400 160 L 300 230" stroke="#10B981" stroke-width="3" stroke-dasharray="10 10">
                    <animate attributeName="stroke-dashoffset" from="100" to="0" dur="2s" repeatCount="indefinite" />
                </path>
                <path d="M 300 270 L 150 340" stroke="#8B5CF6" stroke-width="3" stroke-dasharray="10 10">
                    <animate attributeName="stroke-dashoffset" from="100" to="0" dur="2s" repeatCount="indefinite" />
                </path>
                <path d="M 300 270 L 300 340" stroke="#8B5CF6" stroke-width="3" stroke-dasharray="10 10">
                    <animate attributeName="stroke-dashoffset" from="100" to="0" dur="2s" repeatCount="indefinite" />
                </path>
                <path d="M 300 270 L 450 340" stroke="#8B5CF6" stroke-width="3" stroke-dasharray="10 10">
                    <animate attributeName="stroke-dashoffset" from="100" to="0" dur="2s" repeatCount="indefinite" />
                </path>
                <!-- Nodes -->
                <!-- START -->
                <rect x="240" y="10" width="120" height="40" rx="8" fill="#F1F5F9" stroke="#94A3B8" stroke-width="2"/>
                <text x="300" y="35" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="14" fill="#334155">START</text>
                <!-- Load Docs -->
                <rect x="140" y="120" width="120" height="40" rx="8" fill="#EFF6FF" stroke="#3B82F6" stroke-width="2"/>
                <text x="200" y="145" text-anchor="middle" font-family="sans-serif" font-weight="600" font-size="12" fill="#1E3A8A">Load Resume</text>
                <rect x="340" y="120" width="120" height="40" rx="8" fill="#EFF6FF" stroke="#3B82F6" stroke-width="2"/>
                <text x="400" y="145" text-anchor="middle" font-family="sans-serif" font-weight="600" font-size="12" fill="#1E3A8A">Load JD</text>
                <!-- Analyze -->
                <rect x="220" y="230" width="160" height="40" rx="8" fill="#ECFDF5" stroke="#10B981" stroke-width="2"/>
                <text x="300" y="255" text-anchor="middle" font-family="sans-serif" font-weight="bold" font-size="14" fill="#064E3B">AI Brain Analysis</text>
                <!-- Fetching -->
                <rect x="90" y="340" width="120" height="40" rx="8" fill="#F5F3FF" stroke="#8B5CF6" stroke-width="2"/>
                <text x="150" y="365" text-anchor="middle" font-family="sans-serif" font-weight="600" font-size="12" fill="#4C1D95">Scrape Jobs</text>
                <rect x="240" y="340" width="120" height="40" rx="8" fill="#F5F3FF" stroke="#8B5CF6" stroke-width="2"/>
                <text x="300" y="365" text-anchor="middle" font-family="sans-serif" font-weight="600" font-size="12" fill="#4C1D95">Web Search</text>
                <rect x="390" y="340" width="120" height="40" rx="8" fill="#F5F3FF" stroke="#8B5CF6" stroke-width="2"/>
                <text x="450" y="365" text-anchor="middle" font-family="sans-serif" font-weight="600" font-size="12" fill="#4C1D95">Static Resources</text>
            </svg>
        </div>
        """
        st.markdown(graph_svg.replace('\n', ''), unsafe_allow_html=True)
    
        st.markdown("### :material/help: Frequently Asked Questions")
    
        with st.expander(":material/bar_chart: How is the ATS Score calculated?"):
            st.markdown("""
            The **ATS (Applicant Tracking System) Score** is an AI-generated metric (0-100) reflecting how well your resume matches the target job description. It evaluates three key areas:
        
            1. **Keyword Match**: The overlap between the technical/soft skills extracted from your resume and the explicit/implicit requirements in the Job Description.
            2. **Contextual Relevance**: How well your past experience aligns with the requested domain.
            3. **Formatting**: Checks for unreadable data blocks or missing standard sections (like Education or Experience).
        
            *A score above 75% typically indicates a strong match.*
            """)
        
        with st.expander(":material/psychology: How does the AI Skill Gap Analysis work?"):
            st.markdown("""
            We use Google's **Gemini AI** to act as an expert career coach. The AI reads your formatted resume alongside the target job description. It extracts the skills you possess and compares them to the skills implicitly and explicitly demanded by the role, outputting a highly accurate "Gap List" of what you need to learn.
            """)
        
        with st.expander(":material/travel_explore: How do you scrape jobs in real-time?"):
            st.markdown("""
            When you submit your target role, our backend spins up a **Selenium-powered web scraper**. It actively navigates to top job boards (like Naukri) and extracts live, current job postings that match your desired title and location. This ensures you aren't looking at stale, cached job data.
            """)
        
        with st.expander(":material/school: How are Learning Resources found?"):
            st.markdown("""
            For every skill gap identified by the AI, our graph uses **Tavily Web Search** to dynamically find the best, most up-to-date tutorials, articles, and courses on the internet. We also cross-reference these with a curated list of static high-quality learning platforms.
            """)

# ---- CAREER ADVISOR (always available, first tab) ----
with TABS[0]:
    render_career_advisor(st.session_state.get("pipeline_data"), UID)
