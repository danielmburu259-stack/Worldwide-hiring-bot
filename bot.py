# RemoteJobsHiringNow - FINAL v2 - Checked 3 times
# Rules:
# 1. Remote ONLY - say what the source platform says about location.
#    If source says Worldwide, say Worldwide. If source says a place, say Only that place.
#    (e.g. USA, Philippines, Germany, Kenya, Brazil - any place, not just those examples)
#    NEVER invent Worldwide when source only says Remote.
# 2. Better sources first (RemoteOK, Remotive), Backup only if empty
# 3. Freelancer = skill-based, NOT engineering/professional degree jobs
#    ALLOWED: Representative, Manager, Senior, Executive, Lead - if remote + worldwide
#    BLOCKED: Engineer, Developer, Doctor, Lawyer, Accountant, etc.
# 4. NEVER post tag soup. Tags are not a description.
# 5. Salary: show period ONLY if job itself says it (per year / per month / per week / per hour). Never invent.
#    Title pay ($70) is real pay - show it even if < $100. Description noise ($3 million) is not.
# 6. Worldwide: company can be in US/UK/EU, but job scope must NOT be US/UK/EU-only (e.g. US Oncology, UK Sales).
import os, json, requests, html, random, re, sys, hashlib
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip() or os.getenv("TELEGRAM_CHAT_ID", "").strip() or os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
if not CHANNEL_ID:
    CHANNEL_ID = "@RemoteJobsHiringNow"
CHANNEL_USERNAME = CHANNEL_ID.lstrip("@") if CHANNEL_ID.startswith("@") else "RemoteJobsHiringNow"
ADMIN = "@dantez4u"
SHARE_LINK = "https://t.me/RemoteJobsHiringNow"
MAX_AGE_DAYS = 7
PREFERRED_AGE_DAYS = 2
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN empty")
    sys.exit(1)

FREELANCER_CATS = ["Writing", "Customer Support", "Data Entry", "Social Media", "Design", "Virtual Assistant", "Marketing", "Translation", "Transcription", "Sales", "Admin", "Video Editing"]

CAT_KEYWORDS = {
    "Writing": ["writer", "writing", "copywriter", "content writer", "blog", "article", "editor", "proofread", "ghostwriter", "copy editor"],
    "Customer Support": ["customer support", "support agent", "support specialist", "help desk", "customer service", "chat support", "customer success"],
    "Data Entry": ["data entry", "data clerk", "data processing", "data annotation", "labeling", "data collection", "ai trainer", "annotation"],
    "Social Media": ["social media", "community manager", "social media manager", "content creator", "tiktok", "instagram"],
    "Design": ["graphic design", "designer", "canva", "logo", "illustrator", "photoshop", "ui design", "thumbnail"],
    "Virtual Assistant": ["virtual assistant", "personal assistant", "executive assistant", "admin assistant", "office assistant"],
    "Marketing": ["marketing", "seo", "email marketing", "digital marketing", "affiliate", "lead generation"],
    "Translation": ["translator", "translation", "interpreter", "bilingual"],
    "Transcription": ["transcription", "transcriber", "caption", "subtitle"],
    "Sales": ["sales", "sales rep", "appointment setter", "cold caller", "business development", "lead gen"],
    "Admin": ["administrative", "admin", "bookkeeping", "bookkeeper", "receptionist", "scheduling"],
    "Video Editing": ["video edit", "video editor", "video editing", "youtube editor", "reels editor"],
}

# Only truly professional / degree jobs blocked.
# ALLOWED: representative, manager, senior, lead, executive, director, supervisor
BLOCKED_IN_TITLE = [
    "engineer", "engineering", "developer", "devops", "software", "backend", "frontend",
    "data scientist", "machine learning", "architect", "cto",
    "java", "python", "react", "node", "kubernetes",
    "cybersecurity", "security", "blockchain", "quant", "phd", "research scientist",
    "medical", "doctor", "nurse", "lawyer", "attorney", "accountant", "accounting",
    "mechanical", "electrical", "civil", "chemical", "aerospace",
    "graduate", "internship", "intern", "2027", "2028", "apprentice",
    "underwriting", "underwriter", "insurance", "finance", "banking", "bank", "loan", "mortgage", "field",
    "steuerberatung", "steuer", "m/w/d",
    # --- ONLY ADDED HERE: medical/pharma titles, never freelancer jobs ---
    "oncology", "pharma", "pharmaceutical", "clinical",
]

BLOCKED_IN_DESC = ["pay to apply", "pay fee", "training fee", "activation fee", "membership fee", "position filled", "job is closed", "applications closed", "no longer accepting"]

NON_WORLDWIDE = ["(eu)", "europe", "germany", "berlin", "france", "netherlands", "spain", "switzerland", "swiss", "zurich", "austria", "belgium", "(uk)", "united kingdom", "london", "england", " uk", "(us)", "united states", "usa", "america", "new york", "california", "texas", " us", "canada", "australia", "india", "philippines", "nigeria", "kenya", "south africa"]

RESTRICTED_IN_DESC = [
    r"\bus and european\b", r"\bus & european\b", r"\b us and europe\b", r"\busa and europe\b",
    r"\bunited states and europe\b", r"\bnorth america\b", r"\bnorth america only\b",
    r"\bus only\b", r"\busa only\b", r"\bunited states only\b", r"\beurope only\b", r"\buk only\b", r"\beu only\b",
    r"\bus-based\b", r"\busa-based\b", r"\b europe-based\b", r"\buk-based\b",
    r"\bmust be located in\b", r"\bmust reside in\b", r"\bmust live in\b",
    r"\beligible to work in (the )?us\b", r"\beligible to work in (the )?uk\b", r"\bwork authorization in (the )?us\b",
    r"\bcandidates? (must be )?in (the )?us\b", r"\bapplicants? (must be )?in (the )?us\b",
    r"\bacross the us\b", r"\bacross the united states\b", r"\bthroughout the us\b",
    r"\bus market", r"\beuropean market", r"\bus clients", r"\beuropean clients",
]

# --- ONLY ADDED HERE: Title region-scope patterns ---
# SAFE RULE: Block ONLY when a region is the JOB SCOPE in the title.
# "US Oncology", "US Sales", "UK Marketing", "EMEA Sales" = job is for that market, not worldwide.
# DO NOT block just "US" alone: "US Company hiring worldwide" and "US English Translator" must still pass.
# Company location is checked separately, never in title.
TITLE_REGION_SCOPE = [
    r"\bus\s+(oncology|sales|marketing|market|operations|business|commercial|growth|partnerships)\b",
    r"\busa\s+(oncology|sales|marketing|market|operations|business|commercial|growth|partnerships)\b",
    r"\buk\s+(sales|marketing|market|operations|business|commercial|growth|partnerships)\b",
    r"\beu\s+(sales|marketing|market|operations|business|commercial|growth|partnerships)\b",
    r"\beurope(an)?\s+(sales|marketing|market|operations|business|commercial|growth|partnerships)\b",
    r"\bemea\b",
    r"\bapac\b",
    r"\blatam\b",
]

BETTER_SOURCES = ["remoteok", "remotive"]
BACKUP_SOURCES = ["arbeitnow", "wwr_all", "wwr_design", "jobicy", "remote_co", "himalayas"]
SOURCES = BETTER_SOURCES + BACKUP_SOURCES

def load_json(name, default):
    try:
        with open(name) as f:
            return json.load(f)
    except:
        return default

def save_json(name, data):
    with open(name, "w") as f:
        json.dump(data, f, indent=2)

def norm_url(u):
    u = (u or "").strip().lower()
    u = re.sub(r"\?.*$", "", u).rstrip("/")
    return u

def make_id(job):
    key = f"{job['title'].strip().lower()}|{job['company'].strip().lower()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

def parse_date(raw):
    if not raw:
        return None
    try:
        if "T" in str(raw):
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        if str(raw).isdigit():
            return datetime.fromtimestamp(int(raw), tz=timezone.utc)
        return parsedate_to_datetime(str(raw))
    except:
        return None

def get_age_days(job):
    if not job.get("posted_date"):
        return 0
    return (datetime.now(timezone.utc) - job["posted_date"]).days

def is_fresh(job):
    return get_age_days(job) <= PREFERRED_AGE_DAYS

def fetch_channel_posted_urls():
    urls = set()
    titles = set()
    try:
        r = requests.get(f"https://t.me/s/{CHANNEL_USERNAME}", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        page_html = r.text
        all_links = re.findall(r'href="([^"]+)"', page_html)
        for link in all_links:
            link = html.unescape(link)
            if "t.me/" in link or "telegram.me" in link or "telegram.org" in link:
                continue
            if link.startswith("http") and len(link) > 12:
                urls.add(norm_url(link))
        texts = re.findall(r"📌[^<]*<b>(.*?)</b>", page_html)
        for t in texts:
            clean_t = re.sub(r"<[^>]+>", "", t).strip().lower()
            if clean_t:
                titles.add(clean_t)
        print(f"Channel history: {len(urls)} URLs, {len(titles)} titles from t.me/s/{CHANNEL_USERNAME}")
    except Exception as e:
        print(f"Channel history error (will use posted.json backup): {e}")
    return urls, titles

# --- ONLY CHANGED FUNCTION IN THIS FILE: clean_title_company ---
def clean_title_company(title, company, url):
    t = (title or "").strip()
    c = (company or "").strip()
    # Original rule - UNTOUCHED, works for short company names.
    # Example: "Acme: Designer" -> Company=Acme, Title=Designer
    if ":" in t and len(t.split(":")[0]) < 30:
        maybe_company, maybe_title = t.split(":", 1)
        if maybe_title.strip():
            c = maybe_company.strip()
            t = maybe_title.strip()
    # NEW SAFE RULE - ONLY for RSS jobs where company is still just the source name.
    # Example that was broken: "Trusted Building Technologies Inc.: Executive Assistant / Project Manager"
    # with company="WeWorkRemotely". Old rule failed because company part is 33 chars, not <30.
    # We ONLY run this when we do NOT already have a real company, so real API jobs
    # (RemoteOK/Remotive with real company) are never affected.
    if ":" in t:
        generic_companies = {"", "himalayas", "jobicy", "weworkremotely", "remote.co", "arbeitnow", "remotive", "remoteok"}
        if c.lower() in generic_companies:
            maybe_company, maybe_title = t.split(":", 1)
            maybe_company = maybe_company.strip()
            maybe_title = maybe_title.strip()
            # Company names are rarely >60 chars. Title part must be real (at least 3 chars).
            # This prevents splitting "Note: ..." or very long sentences.
            if 0 < len(maybe_company) <= 60 and len(maybe_title) >= 3:
                c = maybe_company
                t = maybe_title
    if " at " in t.lower():
        parts = re.split(r"\s+at\s+", t, flags=re.I)
        if len(parts) == 2 and len(parts[1]) < 30:
            t = parts[0].strip()
            c = parts[1].strip().title()
    m = re.search(r"/companies/([^/]+)/", url or "")
    if m and c.lower() in ["himalayas", "jobicy", "weworkremotely", "remote.co", ""]:
        c = m.group(1).replace("-", " ").title()
    return t, c
# --- END OF ONLY CHANGED FUNCTION ---

# --- ONLY CHANGED PART STARTS HERE: Salary period + Tiny salary guard ---
# Professional rule: return salary exactly as job states it, plus its period if job states it.
# Never invent a period. If job says "$50,000" with no period, return "$50,000".
# NEW: $3 alone is NOT a salary (it is "$3 million revenue" etc. in the description). Throw it away.
# BUT: $70 in the TITLE is real pay ("Paid Task ($70)") - title pay is never thrown away.
def _find_period(text):
    if not text:
        return ""
    # Check if text already has a period - avoid double "per per year"
    # Order matters: check longer forms first
    m = re.search(r"\bper\s+annum\b", text, flags=re.I)
    if m:
        return "per year"
    m = re.search(r"\bper\s+(hour|week|month|year)\b", text, flags=re.I)
    if m:
        return "per " + m.group(1).lower()
    m = re.search(r"/\s*(hour|hr|week|month|year|yr)\b", text, flags=re.I)
    if m:
        w = m.group(1).lower()
        if w in ("hr",):
            return "per hour"
        if w in ("yr",):
            return "per year"
        return "per " + w
    m = re.search(r"\bannually\b", text, flags=re.I)
    if m:
        return "per year"
    m = re.search(r"\bmonthly\b", text, flags=re.I)
    if m:
        return "per month"
    m = re.search(r"\bweekly\b", text, flags=re.I)
    if m:
        return "per week"
    m = re.search(r"\bhourly\b", text, flags=re.I)
    if m:
        return "per hour"
    m = re.search(r"\ba\s+(year|month|week|hour)\b", text, flags=re.I)
    if m:
        return "per " + m.group(1).lower()
    return ""

def _has_period(text):
    return _find_period(text) != ""

def _is_tiny_salary(salary_part, period):
    # $3, $5, $9 with no period and no range = not a salary, it is a price / revenue mention.
    # Keep: $25/hour (has period), $85k, $50,000, $50,000 - $58,000, $15 - $20/hour
    if period:
        return False
    if "-" in salary_part or "–" in salary_part:
        return False
    if "k" in salary_part.lower():
        return False
    nums = re.findall(r"[\d,]+", salary_part)
    if not nums:
        return False
    try:
        val = float(nums[0].replace(",", ""))
    except:
        return False
    # A real salary without period is at least $100 (e.g. $500 project). Below that, it is noise.
    # NOTE: This guard is ONLY for description / API salary. Title pay is handled separately and never goes through here.
    return val < 100

def extract_salary_from_title(title):
    # Title pay is real: "Paid Task ($70)", "Writer - $50", "Design - $85 - $100"
    # Return it as-is, even if < $100. Never invent a period.
    if not title:
        return ""
    m = re.search(r"\$\s?[\d,]+(?:\s?[-–]\s?\$?\s?[\d,]+)?", title, flags=re.I)
    if not m:
        return ""
    salary_part = m.group(0).strip()
    period = _find_period(title)
    if period:
        return f"{salary_part} {period}"
    return salary_part

def extract_salary(desc):
    if not desc:
        return ""
    # 1. $ amount with optional period right after it: "$50,000 - $58,000 per year" / "$25/hour" / "$2,000 monthly"
    # Search ALL $ amounts, not just the first one - first one may be "$3 million" noise.
    for m in re.finditer(r"\$\s?[\d,]+(?:\s?[-–]\s?\$?\s?[\d,]+)?", desc, flags=re.I):
        salary_part = m.group(0).strip()
        after = desc[m.end():m.end()+40]
        period = _find_period(after)
        if not period:
            period = _find_period(desc)
        if _is_tiny_salary(salary_part, period):
            continue
        if period:
            return f"{salary_part} {period}"
        return salary_part
    # 2. Fallback: 60k - 80k / $60k / € / £ - same period logic
    m2 = re.search(r"(\d{2,3}k\s?[-–]\s?\d{2,3}k|\$\d+k|€\s?[\d,]+|£\s?[\d,]+)", desc, flags=re.I)
    if m2:
        salary_part = m2.group(0).strip()
        after = desc[m2.end():m2.end()+40]
        period = _find_period(after)
        if not period:
            period = _find_period(desc)
        if _is_tiny_salary(salary_part, period):
            return ""
        if period:
            return f"{salary_part} {period}"
        return salary_part
    return ""
# --- ONLY CHANGED PART ENDS HERE: Salary period + Tiny salary guard ---

def extract_job_type(desc, title):
    text = ((title or "") + " " + (desc or "")).lower()
    if "part-time" in text or "part time" in text:
        return "Part-time"
    if "contract" in text:
        return "Contract"
    if "freelance" in text:
        return "Freelance"
    if "full-time" in text or "full time" in text:
        return "Full-time"
    if "temporary" in text:
        return "Temporary"
    return ""

def extract_snippet(desc, title="", company=""):
    # ONLY CHANGE IN THIS FILE:
    # Old version tried to pick a sentence from desc. It kept picking wrong ones:
    # - "product manager exec salesforce hr..." (tag soup)
    # - "A zeal to live, and to share life..." (mission fluff)
    # New version: no picking, always safe fallback. Never wrong.
    t = (title or "").strip()
    c = (company or "").strip()
    if t and c:
        return f"Open role: {t} at {c}. Check the Apply link for full duties, requirements and pay."
    if t:
        return f"Open role: {t}. Check the Apply link for full duties, requirements and pay."
    return ""

def is_english(title, desc):
    text = (title or "") + " " + (desc or "")[:500]
    if re.search(r"[äöüßÄÖÜ]", text):
        return False
    german_words = [" und ", " die ", " der ", " für ", " mit ", " von ", " bist ", " hast ", " wirst ", " gerne ", " neue ", " deine ", " unser", "steuer"]
    low = " " + text.lower() + " "
    for w in german_words:
        if w in low:
            return False
    return True

def is_worldwide(job):
    loc = (job.get("location") or "").lower()
    for bad in NON_WORLDWIDE:
        if bad in loc:
            return False
    # --- ONLY ADDED HERE in is_worldwide: title region-scope check ---
    # Title only, not company. Company can be in US/UK/EU and still hire worldwide.
    title_text = (job.get("title") or "").lower()
    for pat in TITLE_REGION_SCOPE:
        if re.search(pat, title_text):
            return False
    desc_text = ((job.get("title") or "") + " " + (job.get("desc") or "")).lower()
    for pat in RESTRICTED_IN_DESC:
        if re.search(pat, desc_text):
            return False
    if loc.strip() in ["", "remote", "worldwide", "global", "anywhere", "remote - worldwide"]:
        return True
    if any(x in loc for x in ["worldwide", "global", "anywhere", "remote"]):
        return True
    return False

# --- ONLY CHANGED FUNCTION HERE: get_location_label - fix "Only Us Only" ---
# Say what the source platform says. Never invent Worldwide.
# FIX 1: Source may already say "US Only" / "Philippines Only". Strip that trailing "Only" first,
#        then add ONE "Only". Otherwise we get "Only Us Only".
# FIX 2: Fix US / UK / USA inside ANY phrase, not just whole string.
#        "Southeast US" -> "Southeast US", not "Southeast Us". "USA, Canada" -> "USA, Canada".
def _format_place_list(raw):
    # 1. Strip trailing " Only" if source already included it: "US Only" -> "US"
    s = raw.strip()
    s = re.sub(r"\s+only\s*$", "", s, flags=re.I).strip()
    if not s:
        return ""
    # 2. Split on comma / " and ", keep separators.
    parts = re.split(r"(\s*,\s*|\s+and\s+)", s)
    out = []
    for p in parts:
        stripped = p.strip()
        low = stripped.lower()
        if stripped == "" or low in (",", "and"):
            out.append(p)
            continue
        # 3. Fix each WORD inside the part: "southeast us" -> "Southeast US"
        words = stripped.split()
        fixed_words = []
        for w in words:
            lw = w.lower().strip(",")
            if lw in ("usa", "us", "u.s.", "u.s.a.", "united"):
                # "united" alone is handled below with next word, keep as-is for now
                fixed_words.append(w)
            else:
                fixed_words.append(w)
        # Rebuild, then fix known phrases / abbreviations as whole tokens.
        rebuilt = " ".join(fixed_words)
        # Token-level fix: replace whole words us/usa/uk/uae/eu, case-insensitive, keep other words Title-cased.
        tokens = rebuilt.split()
        final_tokens = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            low_tok = tok.lower().strip(",")
            # "United States" -> "US", "United Kingdom" -> "UK"
            if low_tok == "united" and i + 1 < len(tokens) and tokens[i+1].lower().strip(",") in ("states", "kingdom"):
                nxt = tokens[i+1].lower().strip(",")
                final_tokens.append("US" if nxt == "states" else "UK")
                i += 2
                continue
            if low_tok in ("usa", "us", "u.s.", "u.s.a."):
                final_tokens.append("USA")
            elif low_tok in ("uk", "u.k."):
                final_tokens.append("UK")
            elif low_tok in ("uae",):
                final_tokens.append("UAE")
            elif low_tok in ("eu", "e.u."):
                final_tokens.append("EU")
            else:
                final_tokens.append(tok.title())
            i += 1
        out.append(" ".join(final_tokens))
    joined = "".join(out)
    joined = re.sub(r"\s+", " ", joined).strip()
    joined = re.sub(r"\s*,\s*", ", ", joined)
    return joined

def get_location_label(job):
    loc = (job.get("location") or "").strip()
    loc_low = loc.lower()
    desc_text = ((job.get("title") or "") + " " + (job.get("desc") or "")).lower()
    # 1. Source explicitly says Worldwide / Global / Anywhere -> Worldwide, only then.
    if any(x in loc_low for x in ["worldwide", "global", "anywhere"]):
        return ("Worldwide", "Worldwide - All Can Apply ✅")
    # 2. Source location names ANY specific place -> Only that place, word-for-word.
    # No country list. Whatever source wrote, we repeat it.
    # Skip only the non-place values: blank, "Remote", "Remote - Worldwide".
    if loc and loc_low not in ("", "remote", "remote - worldwide"):
        place = _format_place_list(loc)
        if place:
            return (f"Only {place}", f"Only {place} Can Apply")
    # 3. Location is just "Remote" but description clearly says "<Place> only" -> use that place.
    # Generic: any 1-2 word place, not a hard-coded country list.
    stopwords = {"candidates", "applicants", "remote", "online", "fully", "all", "those", "this", "that", "eligible", "qualified", "based", "located", "residing"}
    m = re.search(r"\b([a-z]+(?:\s+[a-z]+)?)\s+only\b", desc_text)
    if m:
        place_raw = m.group(1).strip()
        words = place_raw.split()
        if 1 <= len(words) <= 2 and all(w not in stopwords for w in words) and len(place_raw) <= 30:
            place = _format_place_list(place_raw)
            if place:
                return (f"Only {place}", f"Only {place} Can Apply")
    # 4. Source only says Remote / blank -> say Remote, do NOT invent Worldwide.
    return ("Remote", "Check Apply link for who can apply")

def fetch_remoteok():
    try:
        r = requests.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        out = []
        for j in r.json():
            if not isinstance(j, dict) or not j.get("position"):
                continue
            title, company = clean_title_company(j.get("position"), j.get("company"), j.get("url"))
            # FIXED: ONLY real description. NEVER add tags to desc. Tags caused Maya HTT tag soup.
            out.append({"title": title, "company": company, "url": j.get("url"), "location": j.get("location", "Remote"), "desc": str(j.get("description", ""))[:1500], "salary": f"${j.get('salary_min','')} - ${j.get('salary_max','')}" if j.get("salary_min") else "", "source": "RemoteOK", "posted_date": parse_date(j.get("date"))})
        print(f"RemoteOK {len(out)}")
        return out
    except Exception as e:
        print(f"RemoteOK error {e}")
        return []

def fetch_remotive():
    try:
        r = requests.get("https://remotive.com/api/remote-jobs?limit=100", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        out = []
        for j in r.json().get("jobs", []):
            title, company = clean_title_company(j.get("title"), j.get("company_name"), j.get("url"))
            out.append({"title": title, "company": company, "url": j.get("url"), "location": j.get("candidate_required_location", "Remote"), "desc": j.get("description", "")[:1500], "salary": j.get("salary") or "", "source": "Remotive", "posted_date": parse_date(j.get("publication_date"))})
        print(f"Remotive {len(out)}")
        return out
    except Exception as e:
        print(f"Remotive error {e}")
        return []

def fetch_arbeitnow():
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        out = []
        for j in r.json().get("data", []):
            title, company = clean_title_company(j.get("title"), j.get("company_name"), j.get("url"))
            out.append({"title": title, "company": company, "url": j.get("url"), "location": j.get("location") or "Remote", "desc": j.get("description", "")[:1500], "salary": "", "source": "Arbeitnow", "posted_date": parse_date(j.get("created_at"))})
        print(f"Arbeitnow {len(out)}")
        return out
    except Exception as e:
        print(f"Arbeitnow error {e}")
        return []

def fetch_rss(url, source_name):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        root = ET.fromstring(r.content)
        out = []
        for item in root.findall(".//item")[:50]:
            title_raw = item.findtext("title") or ""
            link = item.findtext("link") or ""
            desc = re.sub("<[^>]+>", " ", item.findtext("description") or "")[:1500]
            pub = item.findtext("pubDate") or ""
            title, company = clean_title_company(title_raw, source_name, link)
            out.append({"title": title, "company": company, "url": link, "location": "Remote", "desc": desc, "salary": "", "source": source_name, "posted_date": parse_date(pub)})
        print(f"{source_name} {len(out)}")
        return out
    except Exception as e:
        print(f"{source_name} error {e}")
        return []

FETCHERS = {"remoteok": fetch_remoteok, "remotive": fetch_remotive, "arbeitnow": fetch_arbeitnow, "wwr_all": lambda: fetch_rss("https://weworkremotely.com/categories/remote-programming-jobs.rss", "WeWorkRemotely"), "wwr_design": lambda: fetch_rss("https://weworkremotely.com/categories/remote-design-jobs.rss", "WeWorkRemotely"), "jobicy": lambda: fetch_rss("https://jobicy.com/feed/", "Jobicy"), "remote_co": lambda: fetch_rss("https://remote.co/remote-jobs/feed/", "Remote.co"), "himalayas": lambda: fetch_rss("https://himalayas.app/jobs/rss", "Himalayas")}

def get_freelancer_category(title, desc):
    t = (title or "").lower()
    for b in BLOCKED_IN_TITLE:
        if re.search(r"\b" + re.escape(b) + r"\b", t):
            return None
    for cat, kws in CAT_KEYWORDS.items():
        for kw in kws:
            if re.search(r"\b" + re.escape(kw) + r"\b", t):
                return cat
    return None

def reject_reason(job, posted_urls, posted_ids, channel_titles, max_age=MAX_AGE_DAYS):
    if norm_url(job["url"]) in posted_urls:
        return "repeat-url-channel-or-json"
    if make_id(job) in posted_ids:
        return "repeat-id"
    if job["title"].strip().lower() in channel_titles:
        return "repeat-title-channel"
    if not job["url"] or len(job["url"]) < 10:
        return "no-url"
    text = (job["title"] + " " + job["desc"]).lower()
    for bad in BLOCKED_IN_DESC:
        if bad in text:
            return f"blocked-{bad}"
    age = get_age_days(job)
    if age > max_age:
        return f"too-old-{age}d"
    # --- ONLY CHANGED HERE in reject_reason: no longer reject for region ---
    # Old: if not worldwide, reject. That meant a real "Only Philippines" job could never post.
    # New: post it, but label it correctly with get_location_label(). Location honesty is in the label, not in rejection.
    # is_worldwide() is kept for reference, but no longer used to reject.
    if not is_english(job["title"], job["desc"]):
        return "not-english"
    return None

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=20)
    print(f"TELEGRAM: {resp.status_code} - {resp.text[:300]}")
    return resp

def pick_best(candidates, last_cat):
    def score(item):
        job, cat, source_name = item
        salary = (job.get("salary") or "").strip() or extract_salary(job.get("desc", ""))
        has_salary = 1 if salary else 0
        diff_cat = 1 if cat != last_cat else 0
        age = get_age_days(job)
        return (has_salary, diff_cat, -age)
    candidates_sorted = sorted(candidates, key=score, reverse=True)
    return candidates_sorted[0] if candidates_sorted else None

def collect_candidates(source_list, posted_urls, posted_ids, channel_titles, last_cat):
    candidates = []
    for source_name in source_list:
        jobs = FETCHERS[source_name]()
        random.shuffle(jobs)
        for job in jobs:
            if reject_reason(job, posted_urls, posted_ids, channel_titles, max_age=MAX_AGE_DAYS):
                continue
            if not is_fresh(job):
                continue
            cat = get_freelancer_category(job["title"], job["desc"])
            if not cat:
                continue
            candidates.append((job, cat, source_name))
        if len(candidates) >= 20:
            break
    if candidates:
        return candidates
    candidates = []
    for source_name in source_list:
        jobs = FETCHERS[source_name]()
        random.shuffle(jobs)
        for job in jobs:
            if reject_reason(job, posted_urls, posted_ids, channel_titles, max_age=MAX_AGE_DAYS):
                continue
            cat = get_freelancer_category(job["title"], job["desc"])
            if not cat:
                continue
            candidates.append((job, cat, source_name))
        if len(candidates) >= 20:
            break
    return candidates

def main():
    state = load_json("state.json", {"last_source": -1, "last_categories": [], "ad_posted_today": "", "last_title": "", "last_source_name": ""})
    posted_data = load_json("posted.json", [])
    posted_urls = set()
    posted_ids = set()
    for item in posted_data:
        if isinstance(item, dict):
            posted_urls.add(norm_url(item.get("url", "")))
            posted_ids.add(item.get("id", ""))
        else:
            posted_urls.add(norm_url(item))
    channel_urls, channel_titles = fetch_channel_posted_urls()
    posted_urls = posted_urls.union(channel_urls)
    print(f"Total memory: {len(posted_urls)} URLs (JSON + Channel) | Last source: {state.get('last_source_name')} | Last cat: {state.get('last_categories', [])[-1:] if state.get('last_categories') else []}")
    today = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now(timezone.utc).hour
    if hour == 6 and state.get("ad_posted_today") != today:
        ad = f"""📢 <b>ADVERTISE HERE</b>\n\nHiring? Have a job / service for job seekers?\nYour post will be seen by job seekers worldwide.\n\n👉 DM Admin: {ADMIN}\n\n📣 Share this channel: {SHARE_LINK}\n"""
        resp = send_to_telegram(ad)
        if resp.status_code == 200:
            state["ad_posted_today"] = today
            save_json("state.json", state)
        return
    last_cats = state.get("last_categories", [])
    last_cat = last_cats[-1] if last_cats else ""
    last_source_name = state.get("last_source_name", "")
    better_ordered = [s for s in BETTER_SOURCES if s != last_source_name] + [s for s in BETTER_SOURCES if s == last_source_name]
    backup_ordered = [s for s in BACKUP_SOURCES if s != last_source_name]
    print(f"TIER 1 - Better sources: {better_ordered}")
    candidates = collect_candidates(better_ordered, posted_urls, posted_ids, channel_titles, last_cat)
    chosen = pick_best(candidates, last_cat) if candidates else None
    if not chosen:
        print("TIER 1 empty - TIER 2 Backup sources only")
        print(f"TIER 2 - Backup sources: {backup_ordered}")
        candidates = collect_candidates(backup_ordered, posted_urls, posted_ids, channel_titles, last_cat)
        chosen = pick_best(candidates, last_cat) if candidates else None
    if not chosen:
        print("No freelancer job found - Worldwide + English + Not in channel")
        return
    job, cat, source_name = chosen
    if job["title"].strip().lower() == state.get("last_title", "").strip().lower():
        print("SKIP: Same title as last post")
        return
    date_str = ""
    if job.get("posted_date"):
        date_str = f"\n📅 Posted: {job['posted_date'].strftime('%d %b %Y')}"
    else:
        date_str = "\n📅 Posted: Recently"
    # Salary: ONLY CHANGED HERE in main() - title pay first, then API / description
    # Order: 1) Title pay ($70) - always real, never tiny-guarded. 2) API salary. 3) Description salary.
    salary_raw = (job.get("salary") or "").strip()
    title_salary = extract_salary_from_title(job.get("title", ""))
    if title_salary:
        salary = title_salary
    elif salary_raw:
        if _has_period(salary_raw):
            salary = salary_raw
        else:
            period = _find_period(job.get("desc", ""))
            salary = f"{salary_raw} {period}" if period else salary_raw
    else:
        salary = extract_salary(job.get("desc", ""))
    # Tiny guard ONLY for API / description salary, NEVER for title salary.
    if not title_salary and salary and _is_tiny_salary(salary.split(" per ")[0] if " per " in salary else salary, _find_period(salary)):
        salary = ""
    salary_line = f"\n💰 Salary: {html.escape(salary)}" if salary else "\n💰 Salary: Not listed"
    job_type = extract_job_type(job.get("desc", ""), job.get("title", ""))
    type_line = f"\n🕒 Type: {job_type}" if job_type else ""
    snippet = extract_snippet(job.get("desc", ""), job.get("title", ""), job.get("company", ""))
    snippet_line = f"\n📋 {html.escape(snippet)}" if snippet else ""
    # --- ONLY CHANGED HERE in main(): location label comes from source, not hardcoded Worldwide ---
    location_label, eligibility_label = get_location_label(job)
    location_line = f"\n📍 {html.escape(location_label)}"
    message = f"""🌍 <b>REMOTE JOB - {cat}</b>{date_str}\n\n📌 <b>{html.escape(job['title'])}</b>\n🏢 {html.escape(job['company'] or 'Company')}{location_line}{salary_line}{type_line}{snippet_line}\n\n🌍 {html.escape(eligibility_label)}\n\n👉 <b>Apply Here:</b> {job['url']}\n\n⚠️ Never pay to apply for a job.\n\n📣 Share with a friend who needs a job 👉 {SHARE_LINK}\n"""
    # --- ONLY NEW CHECK HERE: duplicate guard RIGHT before sending ---
    # Fixes double-send when bot runs twice at the same time (e.g. on deploy).
    # Re-load fresh posted.json + channel. If this job appeared in between, skip.
    try:
        fresh_posted = load_json("posted.json", [])
        fresh_urls = set()
        fresh_ids = set()
        for item in fresh_posted:
            if isinstance(item, dict):
                fresh_urls.add(norm_url(item.get("url", "")))
                fresh_ids.add(item.get("id", ""))
            else:
                fresh_urls.add(norm_url(item))
        fresh_channel_urls, fresh_channel_titles = fetch_channel_posted_urls()
        fresh_urls = fresh_urls.union(fresh_channel_urls)
        if norm_url(job["url"]) in fresh_urls or make_id(job) in fresh_ids or job["title"].strip().lower() in fresh_channel_titles:
            print("SKIP: Duplicate detected just before send - already posted by another run")
            return
    except Exception as e:
        print(f"Pre-send duplicate check error (will still try to send once): {e}")
    resp = send_to_telegram(message)
    if resp.status_code == 200:
        posted_data.append({"url": job["url"], "id": make_id(job), "title": job["title"], "date": today, "category": cat, "source": source_name})
        last_cats.append(cat)
        state["last_categories"] = last_cats[-15:]
        state["last_source"] = SOURCES.index(source_name) if source_name in SOURCES else 0
        state["last_source_name"] = source_name
        state["last_title"] = job["title"]
        save_json("state.json", state)
        save_json("posted.json", posted_data)
        print(f"SUCCESS: {cat} from {source_name} - {job['title']} - Salary: {'YES' if salary else 'Not listed'}")

if __name__ == "__main__":
    main()
