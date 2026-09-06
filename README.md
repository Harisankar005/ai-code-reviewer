# 🛡️ AI Code Reviewer & Bug Fixing Agent

> An autonomous, real-time code analysis and bug-fixing tool powered by **Google Gemini** (`google-genai` SDK) and **Streamlit**. Paste any code snippet or public GitHub file URL to instantly detect bugs, security vulnerabilities, and code smells with severity tags, an interactive diff, and a production-ready fix.

---

## 🚀 Live Demo & Deployment

- **🌐 Live App**: **[https://ai-code-reviewer-hari.streamlit.app/](https://ai-code-reviewer-hari.streamlit.app/)**
- **💻 GitHub Repo**: **[https://github.com/Harisankar005/ai-code-reviewer](https://github.com/Harisankar005/ai-code-reviewer)**
- **Deployment Platform**: [Streamlit Community Cloud](https://streamlit.io/cloud)
- **Status**: 🟢 **Live & Operational**

---

## ✨ Features

- **Multi-Vector Code Inspection**: Scans for runtime bugs, unhandled exceptions, logical errors, off-by-one loops, and resource leaks.
- **Security Vulnerability Auditing**: Flags critical flaws such as SQL injection, unescaped inputs, insecure direct object references, and credential exposure.
- **Severity-Ranked Findings**: Classifies issues into **High** (critical runtime/security), **Medium** (edge cases, performance leaks), and **Low** (code smells, style).
- **Line-by-Line Pinpointing**: Identifies the precise line numbers where each issue originates.
- **Automated Fix Generation**: Produces a clean, runnable, corrected version of the code that resolves every finding while preserving the original design.
- **Interactive Unified Diff**: Side-by-side before/after comparison highlighting deleted buggy lines (`-`) and inserted fixes (`+`).
- **GitHub URL Fetcher**: Accepts public GitHub file URLs (`blob` or `raw`), auto-converts them, and downloads the raw source code on the fly.
- **Clean Code Verification**: Correctly recognizes clean, well-architected code without hallucinating false positives.
- **Zero-Setup Presets**: Preloaded test cases (Buggy Python with SQLi/Off-by-one, Clean Python, Buggy JavaScript) for quick evaluation.

---

## 🏗️ Architecture

```text
[User Input: Code Snippet or GitHub URL]
                       │
                       ▼
             [Streamlit Frontend (app.py)]
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
[URL Converter & Fetcher]     [Prompt & Schema Builder]
(raw.githubusercontent.com)             │
                                       ▼
                          [Google Gemini API]
                         (gemini-2.5-flash via
                           google-genai SDK)
                                       │
                                       ▼
                         [Strict JSON Parser]
                         (findings + fixed_code)
                                       │
                                       ▼
                       ┌───────────────┴───────────────┐
                       ▼                               ▼
             [Metric Badges & Cards]         [Unified Diff Engine]
             (High / Med / Low Findings)      (difflib comparison)
```

---

## 📁 File Structure

```text
ai-code-reviewer/
├── README.md              # Project documentation, deployment guide, & approach write-up
├── requirements.txt      # Production dependencies (streamlit, google-genai, requests, python-dotenv)
├── app.py                 # Streamlit web application & UI dashboard
├── reviewer.py            # Core review agent, GitHub raw content fetcher, diff engine
├── test_reviewer.py       # Automated unit tests for URL parser, JSON extractor, and diffing
├── .env.example           # Template for environment variables (GEMINI_API_KEY)
├── .gitignore             # Excludes .env, secrets, cache, and virtual environments
└── .streamlit/
    └── config.toml        # Professional dark theme & server configuration
```

---

## ⚡ Quickstart (Local Development)

### 1. Clone the repository
```bash
git clone https://github.com/Harisankar005/ai-code-reviewer.git
cd ai-code-reviewer
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your Google Gemini API Key
Get your free API key at [Google AI Studio](https://aistudio.google.com/apikey).

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env`:
```env
GEMINI_API_KEY=AIzaSy...
```
*(Alternatively, you can launch the app and paste your API key directly into the sidebar).*

### 4. Run automated unit tests
```bash
python test_reviewer.py
```

### 5. Launch the Streamlit application
```bash
streamlit run app.py
```
Your browser will open automatically at `http://localhost:8501`.

---

## ☁️ Deployment Guide (Streamlit Community Cloud)

Deploying takes under 3 minutes:

1. **Push your repository to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of AI Code Reviewer & Bug Fixing Agent"
   git branch -M main
   git remote add origin https://github.com/<your-username>/ai-code-reviewer.git
   git push -u origin main
   ```
2. **Open Streamlit Community Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with your GitHub account.
   - Click **New app**.
3. **Configure App**:
   - **Repository**: `<your-username>/ai-code-reviewer`
   - **Branch**: `main`
   - **Main file path**: `app.py` (or `ai-code-reviewer/app.py` if kept in a subfolder).
4. **Set Secrets (API Key)**:
   - Click **Advanced settings...** before deploying (or go to **App settings > Secrets**).
   - Add your Gemini API key in TOML format:
     ```toml
     GEMINI_API_KEY = "AIzaSy..."
     ```
5. **Deploy & Verify**:
   - Click **Deploy!**.
   - Once deployed, test the live URL in a fresh incognito browser window to verify public accessibility.

---

## 🧪 Testing Checklist

- [x] **Buggy Code with Vulnerability**: Tested with Python SQL injection and off-by-one loop; flagged severity as High and generated parameterized query fix.
- [x] **Clean Code Evaluation**: Confirmed clean snippet returns 0 findings and reports no false positives.
- [x] **GitHub URL Ingestion**: Tested conversion from standard `github.com/.../blob/...` URLs to `raw.githubusercontent.com/...` with language auto-detection.
- [x] **Diff Generation**: Unified diff cleanly highlights line deletions and insertions.
- [x] **Resilience**: Handled empty inputs, unauthenticated calls, and malformed responses gracefully.

---

## 📝 Approach Write-Up

### Problem
Developers frequently introduce subtle runtime bugs, security vulnerabilities (such as SQL injection or resource leaks), and code smells during rapid development cycles. Manually reviewing code or waiting for peer reviews creates bottlenecks, and traditional static analysis tools (linters) often lack the contextual intelligence to provide comprehensive, runnable fixes.

### Approach
We designed a streamlined, single-tier architecture combining a **Streamlit** reactive web interface with Google's **Gemini 2.5 Flash** model via the official `google-genai` Python SDK. The reviewer requests strict JSON output adhering to a designated schema containing categorized findings (line number, severity, description, explanation) alongside a fully corrected code replacement. A built-in diff engine (`difflib`) generates immediate unified visual diffs, and an integrated HTTP fetcher converts public GitHub URLs into raw source streams for instant multi-language review.

### Tech Used
- **Frontend & App Server**: Streamlit 1.62+
- **LLM Reasoning Engine**: Google Gemini API (`gemini-2.5-flash` via the official `google-genai` Python SDK)
- **Source Ingestion & HTTP**: Requests, regex URL normalizer
- **Diff & Analysis**: Python `difflib` for unified diffs, JSON schema sanitization
- **Configuration & Security**: `python-dotenv` and Streamlit Secrets management

### Limitations & Future Enhancements
- **Single-File Scope**: Currently reviews one file or snippet at a time; future iterations could support repository-level context through AST indexing or vector retrieval.
- **Stateless Sessions**: Reviews are performed per request without persistent database storage; adding user accounts and review histories would benefit enterprise team workflows.
- **LLM Context Boundaries**: Code files exceeding the token budget must be segmented or summarized prior to review.
