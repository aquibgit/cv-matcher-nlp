# cvmatch/app/utils.py

import re
import string
from collections import Counter

from .models import JobRequirement


# ---------------- STOPWORDS (generic + HR boilerplate) ---------------- #

BASE_STOPWORDS = {
    "and", "or", "the", "a", "an", "to", "for", "of", "in", "on", "at",
    "is", "are", "was", "were", "am", "be", "been", "being",
    "with", "as", "by", "from", "this", "that", "these", "those",
    "it", "its", "into", "over", "under", "up", "down",
    "have", "has", "had", "will", "shall", "can", "could",
    "would", "should",
    "i", "you", "we", "they", "he", "she",
    "your", "our", "their", "his", "her",
}

# HR / JD boilerplate – NOT useful for any domain
HR_STOPWORDS = {
    "looking", "must", "should", "required", "requirement", "requirements",
    "candidate", "responsible", "responsibilities", "including", "include",
    "advantage", "plus", "preferred", "ability", "strong", "excellent", "good",
    "knowledge", "skills", "skill", "experience", "experiences",
    "working", "work", "team", "teams", "environment", "role", "position",
    "benefits", "opportunity", "apply",
    "added", "both", "encouraged", "freshers", "like", "also",
}

STOPWORDS = BASE_STOPWORDS | HR_STOPWORDS

SECTION_PATTERNS = {
    "skills": re.compile(r"\bskills\b", re.IGNORECASE),
    "experience": re.compile(r"\b(experience|work history|employment)\b", re.IGNORECASE),
    "education": re.compile(r"\b(education|academics|qualification)\b", re.IGNORECASE),
}

PUNCT_STRIP = string.punctuation


# ---------------- BASIC TEXT HELPERS ---------------- #

def tokenize(text: str):
    """
    Lowercase, split on non-alphanumeric, strip punctuation,
    drop short tokens & stopwords.
    Generic for ALL job domains.
    """
    if not text:
        return []

    text = text.lower()
    # quick split on non alphanumeric (keeps + . # for things like C++, .NET, etc.)
    raw_tokens = re.split(r"[^a-z0-9+.#]+", text)

    cleaned = []
    for t in raw_tokens:
        if not t:
            continue

        # strip surrounding punctuation
        t = t.strip(PUNCT_STRIP)
        if not t:
            continue

        if len(t) < 3:  # ignore tiny tokens like 'at', 'in'
            continue

        if t in STOPWORDS:
            continue

        cleaned.append(t)

    return cleaned


def split_skills_field(skills_text: str):
    """
    Split the 'skills' field into:
    - skill phrases (exact phrases: 'customer service', 'python')
    - skill tokens (tokenized form of those phrases)
    Works for ANY job type.
    """
    if not skills_text:
        return set(), set()

    raw_parts = re.split(r"[,\n;]+", skills_text)
    phrases = set()
    tokens = set()

    for part in raw_parts:
        part = part.strip()
        if not part:
            continue
        lower = part.lower()
        phrases.add(lower)
        for t in tokenize(lower):
            tokens.add(t)

    return phrases, tokens


# ---------------- EXPERIENCE PARSING (JD & CV) ---------------- #

EXPERIENCE_PATTERN = re.compile(
    r"(\d+)\s*\+?\s*(?:year|years|yr|yrs)", re.IGNORECASE
)


def parse_experience_range(text: str):
    """
    Try to extract an experience range (min, max) in years from JD text.
    Examples JD strings:
      '0–2 years', '1-3 years', '2+ years', '3 years minimum'
    Returns (min_years, max_years or None)
    """
    if not text:
        return None, None

    text = text.lower()

    # pattern for ranges like '0-2 years', '1–3 years'
    range_pattern = re.compile(
        r"(\d+)\s*[-–]\s*(\d+)\s*(?:year|years|yr|yrs)", re.IGNORECASE
    )
    m_range = range_pattern.search(text)
    if m_range:
        min_y = int(m_range.group(1))
        max_y = int(m_range.group(2))
        if min_y > max_y:
            min_y, max_y = max_y, min_y
        return min_y, max_y

    # single number with plus sign, e.g., '2+ years'
    plus_pattern = re.compile(
        r"(\d+)\s*\+\s*(?:year|years|yr|yrs)", re.IGNORECASE
    )
    m_plus = plus_pattern.search(text)
    if m_plus:
        min_y = int(m_plus.group(1))
        return min_y, None  # no explicit upper bound

    # any "X years" mention; take smallest as min
    numbers = [int(n) for n in re.findall(r"(\d+)\s*(?:year|years|yr|yrs)", text)]
    if numbers:
        min_y = min(numbers)
        max_y = max(numbers) if len(numbers) > 1 else None
        return min_y, max_y

    return None, None


def parse_experience_from_cv(cv_text: str):
    """
    Try to estimate candidate's years of experience from CV text.
    Very rough heuristic: take the largest 'X years' mention in CV.
    """
    if not cv_text:
        return None

    nums = [int(n) for n in EXPERIENCE_PATTERN.findall(cv_text)]
    if not nums:
        return None

    return max(nums)


def experience_match_score(jd_min, jd_max, cv_years):
    """
    Return a score 0–100 based on how well CV's experience matches JD requirement.
    Heuristic:
      - If JD has no experience requirement or CV has no years -> 50 (neutral)
      - If CV meets/exceeds minimum -> high score
      - If CV is slightly below min -> medium
      - If far below -> low
    """
    if jd_min is None and jd_max is None:
        return 50.0  # JD didn't specify years clearly

    if cv_years is None:
        return 50.0  # cannot detect from CV; neutral

    # If candidate meets/exceeds minimum: good
    if jd_min is not None and cv_years >= jd_min:
        # bonus if also within upper bound (if any)
        if jd_max is not None and cv_years > jd_max + 3:
            # far above upper bound, but that's usually okay
            return 80.0
        return 95.0

    # candidate below min:
    diff = jd_min - cv_years if jd_min is not None else 0
    if diff <= 1:
        return 70.0  # slightly under
    elif diff <= 2:
        return 50.0  # under
    else:
        return 25.0  # way below


# ---------------- REQUIREMENT KEYWORDS (generic, multi-domain) ---------------- #

def extract_keywords_from_requirement(requirement: JobRequirement, top_n: int = 60):
    """
    Build keyword sets from a JobRequirement:
    - use title + skills + description
    - emphasize 'skills' + title tokens
    - ignore HR fluff
    Works for ALL kinds of jobs.
    Returns:
      jd_keywords (set of tokens)
      jd_skill_phrases (set of skill phrases from skills field)
    """
    jd_parts = [
        requirement.title or "",
        requirement.skills or "",
        requirement.job_description or "",
    ]
    full_jd_text = "\n".join(jd_parts)

    # 1) Tokens & frequency from JD
    jd_tokens = tokenize(full_jd_text)
    freq = Counter(jd_tokens)

    # 2) skills + title tokens
    skill_phrases, skill_tokens = split_skills_field(requirement.skills or "")
    title_tokens = set(tokenize(requirement.title or ""))

    # 3) base keywords = top frequent JD tokens
    base_keywords = {w for w, _ in freq.most_common(top_n)}

    # 4) ALWAYS include skills + title tokens
    base_keywords |= skill_tokens
    base_keywords |= title_tokens

    return base_keywords, skill_phrases


# ---------------- CV PARSING ---------------- #

def parse_cv_sections(cv_text: str):
    """
    Very simple CV parser: split into sections:
    Skills / Experience / Education / Other
    based on headings in the CV.
    """
    lines = cv_text.splitlines()
    current = "other"
    sections = {"skills": [], "experience": [], "education": [], "other": []}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        lowered = stripped.lower()
        matched = False
        for sec_name, pattern in SECTION_PATTERNS.items():
            if pattern.search(lowered):
                current = sec_name
                matched = True
                break

        if not matched:
            sections[current].append(stripped)

    for key in sections:
        sections[key] = "\n".join(sections[key]).strip()

    return sections


# ---------------- FILE PARSING: PDF / DOCX / TXT ---------------- #

def extract_text_from_uploaded_file(cv_file):
    """
    Convert uploaded CV file (PDF / DOCX / TXT) into plain text.
    - PDF: uses PyPDF2
    - DOCX/DOC: uses python-docx
    Install:
        pip install PyPDF2 python-docx
    """
    if not cv_file:
        return ""

    filename = (cv_file.name or "").lower()

    # --- PDF ---
    if filename.endswith(".pdf"):
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            return ""
        try:
            reader = PdfReader(cv_file)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
            return "\n".join(text_parts)
        except Exception:
            return ""

    # --- DOCX / DOC ---
    if filename.endswith(".docx") or filename.endswith(".doc"):
        try:
            import docx  # python-docx
        except ImportError:
            return ""
        try:
            doc = docx.Document(cv_file)
            paragraphs = [p.text for p in doc.paragraphs if p.text]
            return "\n".join(paragraphs)
        except Exception:
            return ""

    # --- Fallback: treat as plain text ---
    try:
        raw = cv_file.read()
        if isinstance(raw, bytes):
            return raw.decode(errors="ignore")
        return str(raw)
    except Exception:
        return ""


# ---------------- MAIN SCORING FUNCTION ---------------- #

def score_cv_for_requirement(cv_text: str, requirement: JobRequirement):
    """
    Rate a CV against ANY JobRequirement (tech, sales, HR, teaching, etc.) by:
    - extracting JD keywords (title + skills + description)
    - checking coverage in full CV
    - checking coverage in 'Skills' section
    - checking phrase-level coverage of JD 'skills' field
    - checking experience (years) match between JD and CV
    Returns a dict of scores + debug info.
    """
    if not cv_text or not requirement:
        return {
            "overall_score": 0,
            "skills_score": 0,
            "keyword_coverage": 0,
            "phrase_coverage": 0,
            "experience_score": 0,
            "matched_keywords": [],
            "missing_keywords": [],
            "matched_skill_phrases": [],
            "missing_skill_phrases": [],
            "parsed_cv": {},
            "jd_keywords": [],
            "jd_skill_phrases": [],
        }

    # 1) Parse CV into sections
    parsed_cv = parse_cv_sections(cv_text)

    # 2) JD keywords & skill phrases
    jd_keywords, jd_skill_phrases = extract_keywords_from_requirement(requirement)

    # 3) CV tokens (full) + skills section tokens
    full_cv_tokens = set(tokenize(cv_text))
    skills_tokens = set(tokenize(parsed_cv.get("skills", "")))

    # 4) Keyword match
    matched_keywords = sorted(jd_keywords & full_cv_tokens)
    missing_keywords = sorted(jd_keywords - full_cv_tokens)

    if jd_keywords:
        keyword_coverage = (len(matched_keywords) / len(jd_keywords)) * 100
    else:
        keyword_coverage = 0.0

    # 5) Skills section match
    skills_matches = jd_keywords & skills_tokens
    if jd_keywords:
        skills_score = (len(skills_matches) / len(jd_keywords)) * 100
    else:
        skills_score = 0.0

    # 6) Skill phrase-level match (matches JD "skills" field as phrases)
    cv_lower = cv_text.lower()
    matched_skill_phrases = []
    missing_skill_phrases = []

    for phrase in jd_skill_phrases:
        if phrase in cv_lower:
            matched_skill_phrases.append(phrase)
        else:
            missing_skill_phrases.append(phrase)

    if jd_skill_phrases:
        phrase_coverage = (len(matched_skill_phrases) / len(jd_skill_phrases)) * 100
    else:
        # if no explicit skills provided, fall back to keyword coverage
        phrase_coverage = keyword_coverage

    # 7) Experience match
    jd_exp_min, jd_exp_max = parse_experience_range(
        (requirement.experience or "") + " " + (requirement.job_description or "")
    )
    cv_years = parse_experience_from_cv(cv_text)
    experience_score = experience_match_score(jd_exp_min, jd_exp_max, cv_years)

    # 8) Combine into overall score
    # Tuned weights:
    #   35% keyword coverage + 25% skills section + 20% phrase coverage + 20% experience
    overall_score = (
        0.35 * keyword_coverage
        + 0.25 * skills_score
        + 0.20 * phrase_coverage
        + 0.20 * experience_score
    )

    return {
        "overall_score": round(overall_score, 2),
        "skills_score": round(skills_score, 2),
        "keyword_coverage": round(keyword_coverage, 2),
        "phrase_coverage": round(phrase_coverage, 2),
        "experience_score": round(experience_score, 2),
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "matched_skill_phrases": matched_skill_phrases,
        "missing_skill_phrases": missing_skill_phrases,
        "parsed_cv": parsed_cv,
        "jd_keywords": sorted(jd_keywords),
        "jd_skill_phrases": sorted(jd_skill_phrases),
    }
