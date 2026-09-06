"""Core logic for AI Code Reviewer:
- GitHub raw content URL resolution and fetching
- Language detection from file extensions
- Google Gemini API (official google-genai SDK) prompt construction and execution
- Strict JSON parsing, schema validation, and fallback handling
- Unified diff generation between original and fixed code
"""

import difflib
import json
import os
import re
from typing import Dict, Any, Optional, Tuple
import requests

try:
    from google import genai
    from google.genai import types
    from google.genai import errors as genai_errors
except ImportError:
    genai = None
    types = None
    genai_errors = None

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".swift": "swift",
    ".kt": "kotlin",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
}


def detect_language_from_filename(filename: str) -> str:
    """Infers programming language name from a file extension."""
    _, ext = os.path.splitext(filename.lower())
    return EXTENSION_TO_LANGUAGE.get(ext, "auto")


def convert_github_url_to_raw(url: str) -> str:
    """Converts a standard GitHub file view URL into its raw content URL.

    Supported patterns:
    - https://github.com/owner/repo/blob/branch/path/to/file.ext
    - https://github.com/owner/repo/raw/branch/path/to/file.ext
    - https://raw.githubusercontent.com/owner/repo/branch/path/to/file.ext
    """
    clean_url = url.strip()

    if clean_url.startswith("https://raw.githubusercontent.com/"):
        return clean_url

    # Match github.com/owner/repo/(blob|raw)/branch/filepath...
    github_blob_pattern = r"^https?://github\.com/([^/]+)/([^/]+)/(?:blob|raw)/(.+)$"
    match = re.match(github_blob_pattern, clean_url)
    if match:
        owner, repo, rest = match.groups()
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{rest}"

    return clean_url


def fetch_github_file(url: str, timeout: int = 10) -> Tuple[str, str, str]:
    """Fetches code content from a public GitHub file URL.

    Returns:
        Tuple of (code_content, detected_language, filename)
    """
    if not url or not url.strip():
        raise ValueError("Please provide a valid GitHub URL.")

    raw_url = convert_github_url_to_raw(url)
    filename = raw_url.split("/")[-1].split("?")[0]
    detected_lang = detect_language_from_filename(filename)

    headers = {
        "User-Agent": "AICodeReviewer/1.0"
    }

    try:
        response = requests.get(raw_url, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout:
        raise RuntimeError("Request timed out while trying to fetch the GitHub file.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Network error while fetching GitHub file: {str(e)}")

    if response.status_code == 404:
        raise FileNotFoundError(
            f"File not found (404). Ensure the repository is public and the URL points to a specific file: {raw_url}"
        )
    elif response.status_code == 403:
        raise PermissionError(
            "Access denied (403). GitHub rate limits may have been reached, or the repository may be private."
        )
    elif not response.ok:
        raise RuntimeError(f"Failed to fetch file. HTTP status code: {response.status_code}")

    content = response.text
    if not content.strip():
        raise ValueError("The fetched file is empty.")

    return content, detected_lang, filename


def generate_unified_diff(original: str, fixed: str, filename: str = "code") -> str:
    """Generates a unified diff between original and fixed code."""
    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        original_lines,
        fixed_lines,
        fromfile=f"original/{filename}",
        tofile=f"suggested_fix/{filename}",
        lineterm=""
    ))

    return "\n".join(diff_lines) if diff_lines else "No modifications made."


def parse_llm_json(raw_text: str) -> Dict[str, Any]:
    """Extracts and parses JSON from the LLM's response, handling code fences and formatting issues."""
    text = raw_text.strip()

    # Strip markdown code blocks like ```json ... ``` or ``` ... ```
    if text.startswith("```"):
        pattern = r"^```(?:json)?\s*\n?([\s\S]*?)\n?```$"
        match = re.match(pattern, text)
        if match:
            text = match.group(1).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Fallback regex search for JSON object
        json_match = re.search(r"(\{[\s\S]*\})", text)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
            except json.JSONDecodeError as err:
                return {
                    "findings": [
                        {
                            "line": 1,
                            "severity": "medium",
                            "issue": "Raw Model Output (JSON Parsing Error)",
                            "explanation": f"The model response could not be parsed as strict JSON ({str(err)}). Full raw output:\n\n{raw_text}"
                        }
                    ],
                    "fixed_code": raw_text,
                    "summary": "Completed review, but LLM response was not structured JSON."
                }
        else:
            return {
                "findings": [
                    {
                        "line": 1,
                        "severity": "medium",
                        "issue": "Raw Model Output",
                        "explanation": raw_text
                    }
                ],
                "fixed_code": raw_text,
                "summary": "Review generated unstructured output."
            }

    # Normalize findings format
    findings = parsed.get("findings", [])
    if not isinstance(findings, list):
        findings = []

    normalized_findings = []
    for f in findings:
        if isinstance(f, dict):
            severity = str(f.get("severity", "low")).lower()
            if severity not in ["high", "medium", "low"]:
                severity = "medium"
            normalized_findings.append({
                "line": f.get("line", 1),
                "severity": severity,
                "issue": str(f.get("issue", "Unspecified issue")),
                "explanation": str(f.get("explanation", ""))
            })

    fixed_code = str(parsed.get("fixed_code", ""))
    summary = str(parsed.get("summary", "Analysis complete."))

    return {
        "findings": normalized_findings,
        "fixed_code": fixed_code,
        "summary": summary
    }


def review_code(
    code: str,
    language: str = "auto",
    api_key: Optional[str] = None,
    model: str = "gemini-2.5-flash"
) -> Dict[str, Any]:
    """Sends code to Google Gemini API using google-genai SDK for bug detection, smell analysis, and automated fixing.

    Returns:
        dict with keys: 'findings', 'fixed_code', 'summary'
    """
    if not code or not code.strip():
        raise ValueError("Code snippet cannot be empty.")

    resolved_api_key = (
        api_key
        or os.environ.get("GEMINI_API_KEY")
    )

    if not resolved_api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Get a free API key at https://aistudio.google.com/apikey and provide it in the sidebar or set GEMINI_API_KEY in your .env or Streamlit Secrets."
        )

    if genai is None:
        raise RuntimeError("The 'google-genai' package is not installed. Please run: pip install google-genai")

    client = genai.Client(api_key=resolved_api_key)

    system_instruction = (
        "You are an elite principal software engineer, security researcher, and code auditor.\n"
        "Your task is to analyze user-provided code for:\n"
        "1. Critical bugs, runtime errors, unhandled exceptions, and logic flaws\n"
        "2. Security vulnerabilities (OWASP Top 10, injection, insecure memory/data access, leaked secrets)\n"
        "3. Concurrency issues, resource leaks, and performance bottlenecks\n"
        "4. Anti-patterns, code smells, and major style/maintainability problems\n\n"
        "Return your analysis as STRICT, VALID JSON ONLY. Do not prefix or suffix your response with explanations or markdown formatting outside the JSON.\n\n"
        "JSON SCHEMA:\n"
        "{\n"
        '  "findings": [\n'
        "    {\n"
        '      "line": <integer line number where issue originates (1-indexed)>,\n'
        '      "severity": "high" | "medium" | "low",\n'
        '      "issue": "<concise description of the problem>",\n'
        '      "explanation": "<clear explanation of why this is dangerous/problematic and how it causes harm>"\n'
        "    }\n"
        "  ],\n"
        '  "fixed_code": "<full corrected version of the code resolving all findings while preserving original intent>",\n'
        '  "summary": "<one or two sentence summary of the review results>"\n'
        "}\n\n"
        "RULES:\n"
        "- If the code is clean with no issues, return empty `findings: []`, set `fixed_code` equal to the input code, and provide an encouraging summary.\n"
        "- High severity: security vulnerabilities, data loss, crashes, unhandled null/None pointer, infinite loops, logic breaking primary functionality.\n"
        "- Medium severity: performance bottlenecks, unhandled edge cases, resource leaks, deprecations.\n"
        "- Low severity: code smells, maintainability issues, convention violations, minor refactoring opportunities.\n"
        "- Always ensure `fixed_code` is complete and immediately runnable."
    )

    lang_instruction = f"Language: {language}" if language != "auto" else "Language: Auto-detect from snippet"
    user_prompt = f"""Please review the following code snippet ({lang_instruction}):

```
{code}
```

Output valid JSON only, conforming strictly to the requested schema."""

    config = None
    if types is not None:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            temperature=0.1,
        )

    # Candidate models for fallback if selected model is not available in free tier
    fallback_models = [model]
    for m in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        if m not in fallback_models:
            fallback_models.append(m)

    last_err = None
    response = None

    for candidate_model in fallback_models:
        try:
            response = client.models.generate_content(
                model=candidate_model,
                contents=user_prompt,
                config=config
            )
            break
        except Exception as e:
            err_msg = str(e)
            last_err = e
            if "API_KEY" in err_msg.upper() or "PERMISSION_DENIED" in err_msg or "UNAUTHENTICATED" in err_msg:
                raise PermissionError(
                    f"Gemini API authentication error: Please verify your GEMINI_API_KEY from https://aistudio.google.com/apikey ({err_msg})"
                )
            elif "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                raise RuntimeError(f"Gemini API rate limit exceeded: {err_msg}")
            elif "NOT_FOUND" in err_msg or "404" in err_msg:
                # Try next fallback model
                continue
            else:
                raise RuntimeError(f"Gemini API Error: {err_msg}")

    if response is None:
        raise ValueError(
            f"Could not connect to model '{model}' or fallbacks ({', '.join(fallback_models)}): {str(last_err)}"
        )

    result_text = getattr(response, "text", "") or ""
    parsed_output = parse_llm_json(result_text)

    # If code had no findings and fixed_code is blank, restore original code
    if not parsed_output["fixed_code"]:
        parsed_output["fixed_code"] = code

    return parsed_output
