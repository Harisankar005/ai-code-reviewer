"""AI Code Reviewer & Bug Fixing Agent
Streamlit Web Application powered by Google Gemini (google-genai SDK)
"""

import os
import difflib
from typing import Optional
import streamlit as st
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

from reviewer import (
    review_code,
    fetch_github_file,
    generate_unified_diff,
    detect_language_from_filename
)

# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="AI Code Reviewer & Bug Fixer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Styling ---
st.markdown("""
<style>
    .metric-card {
        background-color: #1E293B;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        border: 1px solid #334155;
    }
    .metric-num {
        font-size: 28px;
        font-weight: 700;
    }
    .metric-label {
        font-size: 13px;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .severity-high {
        color: #EF4444;
        font-weight: bold;
    }
    .severity-medium {
        color: #F59E0B;
        font-weight: bold;
    }
    .severity-low {
        color: #3B82F6;
        font-weight: bold;
    }
    .stCodeBlock {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# --- Preset Test Snippets ---
BUGGY_PYTHON_SNIPPET = '''import sqlite3

def get_user_data(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # CRITICAL: SQL Injection vulnerability via string formatting
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)
    results = cursor.fetchall()
    
    # CRITICAL: Off-by-one error (IndexError if results is not empty)
    for i in range(len(results) + 1):
        print("User row:", results[i])
        
    # SMELL: Connection is never closed (Resource leak)
    return results
'''

CLEAN_PYTHON_SNIPPET = '''import sqlite3
from typing import List, Tuple, Any

def get_user_data(user_id: int, db_path: str = "users.db") -> List[Tuple[Any, ...]]:
    """Safely retrieves user records by ID using parameterized queries."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM users WHERE id = ?"
        cursor.execute(query, (user_id,))
        return cursor.fetchall()
'''

BUGGY_JS_SNIPPET = '''function processItems(items) {
    var results = [];
    for (var i = 0; i < items.length; i++) {
        // Closure bug with var in asynchronous callback
        setTimeout(function() {
            console.log("Processing item " + items[i].name);
        }, 1000);
    }
    // Potential null reference without guard
    return results.concat(items.extra.data);
}
'''

SAMPLE_GITHUB_URL = "https://github.com/psf/requests/blob/main/src/requests/api.py"


# --- Session State Initialization ---
if "code_input" not in st.session_state:
    st.session_state.code_input = BUGGY_PYTHON_SNIPPET
if "github_url_input" not in st.session_state:
    st.session_state.github_url_input = ""
if "selected_language" not in st.session_state:
    st.session_state.selected_language = "python"
if "review_results" not in st.session_state:
    st.session_state.review_results = None
if "reviewed_code" not in st.session_state:
    st.session_state.reviewed_code = ""


# --- Helper to resolve API Key ---
def get_resolved_api_key(sidebar_key: Optional[str]) -> Optional[str]:
    if sidebar_key and sidebar_key.strip():
        return sidebar_key.strip()
    
    # Check Streamlit Cloud secrets
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    # Check environment variable
    return os.environ.get("GEMINI_API_KEY")


# --- Sidebar Navigation & Settings ---
with st.sidebar:
    st.header("⚙️ Settings & Key")

    # Determine if API key already exists in env/secrets
    env_api_key = os.environ.get("GEMINI_API_KEY")
    secrets_key = None
    try:
        if "GEMINI_API_KEY" in st.secrets:
            secrets_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    has_preconfigured_key = bool(env_api_key or secrets_key)

    if has_preconfigured_key:
        st.success("✅ `GEMINI_API_KEY` detected from environment/secrets")
        user_api_key = st.text_input(
            "Override API Key (Optional)",
            type="password",
            help="Leave blank to use the preconfigured environment key."
        )
    else:
        st.warning("⚠️ No API Key found in environment or secrets.")
        user_api_key = st.text_input(
            "Enter Gemini API Key",
            type="password",
            help="Get your free key from Google AI Studio: https://aistudio.google.com/apikey"
        )
        st.caption("👉 [Get a free API key at Google AI Studio](https://aistudio.google.com/apikey)")

    model_choice = st.selectbox(
        "Gemini Model",
        options=[
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-2.5-pro",
        ],
        index=0,
        help="gemini-2.5-flash and flash models are free-tier friendly with 15 RPM / 1500 RPD."
    )
    st.caption("⚡ *Free tier in Google AI Studio includes up to 15 Requests/Min & 1,500 Requests/Day for Flash models.*")

    st.markdown("---")
    st.subheader("🧪 Quick Test Presets")
    st.caption("Click any preset to load sample code into the reviewer:")

    if st.button("🐛 Buggy Python (SQLi + Off-by-one)", use_container_width=True):
        st.session_state.code_input = BUGGY_PYTHON_SNIPPET
        st.session_state.selected_language = "python"
        st.session_state.review_results = None
        st.rerun()

    if st.button("✅ Clean Python (Safe DB Query)", use_container_width=True):
        st.session_state.code_input = CLEAN_PYTHON_SNIPPET
        st.session_state.selected_language = "python"
        st.session_state.review_results = None
        st.rerun()

    if st.button("⚠️ Buggy JavaScript (Closure & Null)", use_container_width=True):
        st.session_state.code_input = BUGGY_JS_SNIPPET
        st.session_state.selected_language = "javascript"
        st.session_state.review_results = None
        st.rerun()

    if st.button("🌐 Pre-fill Public GitHub File URL", use_container_width=True):
        st.session_state.github_url_input = SAMPLE_GITHUB_URL
        st.session_state.review_results = None
        st.rerun()

    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.caption(
        "**AI Code Reviewer & Bug Fixing Agent**\n"
        "- **LLM Engine**: Google Gemini API (`google-genai`)\n"
        "- **Default Model**: `gemini-2.5-flash`\n"
        "- **Framework**: Streamlit & Python\n"
        "- **Deployment**: Streamlit Community Cloud\n"
        "- **Features**: Bug scan, vulnerability audit, structured JSON output, unified diff & full-code fix."
    )


# --- Main Application Header ---
st.title("🛡️ AI Code Reviewer & Bug Fixing Agent")
st.markdown(
    "Automated code review, security vulnerability detection, and production-ready bug fixing powered by **Google Gemini** (`google-genai` SDK)."
)

st.markdown("---")

# --- Input Mode Selection ---
input_mode = st.radio(
    "Choose Input Method:",
    options=["📝 Paste Code Snippet", "🔗 Public GitHub File URL"],
    horizontal=True
)

code_to_review = ""
language = "auto"

languages_list = [
    "auto", "python", "javascript", "typescript", "go", "rust",
    "java", "c", "cpp", "csharp", "php", "ruby", "sql", "bash", "html", "css"
]

if input_mode == "📝 Paste Code Snippet":
    col_lang, _ = st.columns([1, 2])
    with col_lang:
        current_idx = languages_list.index(st.session_state.selected_language) if st.session_state.selected_language in languages_list else 0
        language = st.selectbox(
            "Select Programming Language",
            options=languages_list,
            index=current_idx
        )
        st.session_state.selected_language = language

    code_to_review = st.text_area(
        "Paste your code here:",
        value=st.session_state.code_input,
        height=260,
        placeholder="Paste code snippet here..."
    )
    st.session_state.code_input = code_to_review

else:
    st.markdown("Enter a link to a file in a public GitHub repository (supports both `blob` and `raw` URLs):")
    col_url, col_fetch = st.columns([4, 1])
    with col_url:
        github_url = st.text_input(
            "GitHub File URL:",
            value=st.session_state.github_url_input,
            placeholder="https://github.com/owner/repo/blob/main/path/to/file.py"
        )
        st.session_state.github_url_input = github_url

    with col_fetch:
        st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
        fetch_btn = st.button("📥 Fetch File", use_container_width=True)

    if fetch_btn and github_url:
        with st.spinner("Fetching file from GitHub..."):
            try:
                fetched_code, detected_lang, filename = fetch_github_file(github_url)
                st.session_state.code_input = fetched_code
                st.session_state.selected_language = detected_lang
                st.success(f"Successfully fetched `{filename}` (Detected: **{detected_lang}**)")
            except Exception as e:
                st.error(f"Error fetching file: {str(e)}")

    code_to_review = st.text_area(
        "Fetched Code Content:",
        value=st.session_state.code_input,
        height=260
    )
    language = st.session_state.selected_language
    st.session_state.code_input = code_to_review


# --- Review Execution Trigger ---
st.markdown("<br>", unsafe_allow_html=True)
col_action1, col_action2 = st.columns([1, 4])

with col_action1:
    review_button = st.button("🚀 Review Code", type="primary", use_container_width=True)

with col_action2:
    if st.button("🧹 Clear", use_container_width=True):
        st.session_state.code_input = ""
        st.session_state.github_url_input = ""
        st.session_state.review_results = None
        st.session_state.reviewed_code = ""
        st.rerun()

resolved_api_key = get_resolved_api_key(user_api_key)

if review_button:
    if not code_to_review or not code_to_review.strip():
        st.error("Please provide code to review.")
    elif not resolved_api_key:
        st.error(
            "API Key missing! Please enter your Gemini API Key in the sidebar or set GEMINI_API_KEY in your environment/secrets. "
            "You can obtain a free key at https://aistudio.google.com/apikey"
        )
    else:
        with st.spinner("🤖 Gemini is analyzing code, inspecting security risks, and preparing fixes..."):
            try:
                results = review_code(
                    code=code_to_review,
                    language=language,
                    api_key=resolved_api_key,
                    model=model_choice
                )
                st.session_state.review_results = results
                st.session_state.reviewed_code = code_to_review
                st.success("Review complete!")
            except Exception as err:
                st.error(f"Review failed: {str(err)}")


# --- Display Review Results ---
results = st.session_state.review_results
reviewed_code = st.session_state.reviewed_code

if results:
    st.markdown("---")
    st.header("📊 Review Results & Suggested Fix")

    # High-level Summary Callout
    summary_text = results.get("summary", "Analysis completed.")
    findings = results.get("findings", [])
    fixed_code = results.get("fixed_code", "")

    st.info(f"**Summary**: {summary_text}")

    # Metrics Summary Cards
    high_count = sum(1 for f in findings if f.get("severity") == "high")
    med_count = sum(1 for f in findings if f.get("severity") == "medium")
    low_count = sum(1 for f in findings if f.get("severity") == "low")
    total_count = len(findings)

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-num">{total_count}</div><div class="metric-label">Total Findings</div></div>',
            unsafe_allow_html=True
        )
    with col_m2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-num severity-high">{high_count}</div><div class="metric-label">High Severity</div></div>',
            unsafe_allow_html=True
        )
    with col_m3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-num severity-medium">{med_count}</div><div class="metric-label">Medium Severity</div></div>',
            unsafe_allow_html=True
        )
    with col_m4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-num severity-low">{low_count}</div><div class="metric-label">Low / Style</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Tabs for Outputs
    tab_findings, tab_fix, tab_diff = st.tabs([
        f"🔍 Findings ({total_count})",
        "✨ Suggested Fix (Full Code)",
        "🔄 Unified Diff"
    ])

    with tab_findings:
        if not findings:
            st.success("🎉 **No bugs, vulnerabilities, or smells found! The code appears clean and follows best practices.**")
        else:
            # Severity Filter
            severity_filter = st.radio(
                "Filter by Severity:",
                options=["All", "High", "Medium", "Low"],
                horizontal=True
            )

            filtered_findings = findings
            if severity_filter != "All":
                filtered_findings = [f for f in findings if f.get("severity") == severity_filter.lower()]

            if not filtered_findings:
                st.write(f"No {severity_filter.lower()} severity findings.")

            for idx, finding in enumerate(filtered_findings, 1):
                severity = finding.get("severity", "low").upper()
                line = finding.get("line", "N/A")
                issue = finding.get("issue", "Issue")
                explanation = finding.get("explanation", "")

                sev_color = {
                    "HIGH": "🔴",
                    "MEDIUM": "🟡",
                    "LOW": "🔵"
                }.get(severity, "⚪")

                with st.expander(f"{sev_color} **[{severity}] Line {line}:** {issue}", expanded=True):
                    st.markdown(f"**Explanation:**\n\n{explanation}")

    with tab_fix:
        st.markdown("### Suggested Fixed Version")
        st.caption("Complete corrected code with all fixes applied. Use the copy button in the top right of the code block:")
        detected_lang = language if language != "auto" else "python"
        st.code(fixed_code, language=detected_lang)

    with tab_diff:
        st.markdown("### Side-by-Side Unified Diff")
        st.caption("Lines starting with `-` are removed/buggy; lines with `+` are fixes:")
        diff_text = generate_unified_diff(
            original=reviewed_code,
            fixed=fixed_code,
            filename=f"code.{language if language != 'auto' else 'txt'}"
        )
        st.code(diff_text, language="diff")
