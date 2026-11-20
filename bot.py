# RemoteJobsHiringNow - V8 - Freelancer jobs only, short post, no repeat
import os, json, requests, html, random, re, sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip() or os.getenv("TELEGRAM_CHAT_ID", "").strip() or os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
if not CHANNEL_ID:
    CHANNEL_ID = "@RemoteJobsHiringNow"
ADMIN = "@dantez4u"
MAX_AGE_DAYS = 30

if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN empty")
    sys.exit(1)

# --- FREELANCER CATEGORIES ONLY - In rotation order ---
# Bot will go: Writing -> Support -> Data Entry -> Social Media -> Design -> VA -> Marketing -> Translation -> ... then repeat
# It will NEVER post same category twice in a row, and will try to avoid last 10 categories
FREELANCER_CATS = [
    "Writing",
    "Customer Support",
    "Data Entry",
    "Social Media",
    "Design",
    "Virtual Assistant",
    "Marketing",
    "Translation",
    "Transcription",
    "Sales",
    "Admin",
    "Video Editing",
]

# Map keywords -> category. If title matches none, skip it (don't post engineers)
CAT_KEYWORDS = {
    "Writing": ["writer", "writing", "copywriter", "content writer", "blog", "article", "editor", "proofread", "ghostwriter"],
    "Customer Support": ["customer support", "support agent", "support specialist", "help desk", "customer service", "chat support", "customer success"],
    "Data Entry": ["data entry", "data clerk", "data processing", "data annotation", "labeling", "data collection"],
    "Social Media": ["social media", "community manager", "social media manager", "content creator", "tiktok", "instagram"],
    "Design": ["graphic design", "designer", "canva", "logo", "illustrator", "photoshop", "ui design", "thumbnail"],
    "Virtual Assistant": ["virtual assistant", "personal assistant", "executive assistant", "admin assistant", "office assistant"],
    "Marketing": ["marketing", "seo", "email marketing", "digital marketing", "affiliate", "lead generation"],
    "Translation": ["translator", "translation", "interpreter", "bilingual", "translat"],
    "Transcription": ["transcription", "transcriber", "caption", "subtitle"],
    "Sales": ["sales", "sales rep", "appointment setter", "cold caller", "business development", "lead gen"],
    "Admin": ["administrative", "admin", "bookkeeping", "bookkeeper", "accounting assistant", "receptionist", "scheduling"],
    "Video Editing": ["video edit", "video editor", "video editing", "youtube editor", "reels editor"],
}

# --- BLOCK high-professional jobs ---
BLOCKED = [
    "senior engineer", "software engineer", "software developer", "full stack", "backend", "frontend",
    "devops", "data scientist", "machine learning", "ai engineer", "architect", "cto", "principal",
    "staff engineer", "java developer", "python developer", "react developer", "node", "kubernetes",
    "cybersecurity", "security engineer", "blockchain", "quant", "phd", "research scientist",
    "product manager", "engineering manager", "director", "vp ", "head of engineering",
    "medical", "doctor", "nurse", "lawyer", "attorney", "accountant cpa",
]

SOURCES = ["remoteok", "remotive", "arbeitnow", "wwr_all", "wwr_design", "jobicy", "remote_co", "himalayas"]

def load_json(name, default):
    try:
        with open(name) as f: return json.load(f)
    except: return default

def save_json(name, data):
    with open(name, "w") as f: json.dump(data, f, indent=2)

def norm_url(u):
    # Fix repeat bug: https://.../job/ and https://.../job are same job
    # Also lower case, remove trailing / and ?utm...
    u = (u or "").strip().lower()
    u = re.sub(r"\?.*$", "", u)
    u = u.rstrip("/")
    return u

def parse_date(raw):
    if not raw: return None
    try:
        if "T" in str(raw):
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        if str(raw).isdigit():
            return datetime.fromtimestamp(int(raw), tz=timezone.utc)
        return parsedate_to_datetime(str(raw))
    except:
        return None

def fetch_remoteok():
    try:
        r = requests.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        out = []
        for j in r.json():
            if not isinstance(j, dict) or not j.get("position"): continue
            out.append({"title": j.get("position"), "company": j.get("company"), "url": j.get("url"), "location": j.get("location","Remote"), "desc": " ".join(j.get("tags",[])) + " " + str(j.get("description",""))[:800], "salary": f"${j.get('salary_min','')} - ${j.get('salary_max','')}" if j.get("salary_min") else "See link", "source": "RemoteOK", "posted_date": parse_date(j.get("date"))})
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
            out.append({"title": j.get("title"), "company": j.get("company_name"), "url": j.get("url"), "location": j.get("candidate_required_location","Remote"), "desc": j.get("description","")[:800], "salary": j.get("salary") or "See link", "source": "Remotive", "posted_date": parse_date(j.get("publication_date"))})
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
            out.append({"title": j.get("title"), "company": j.get("company_name"), "url": j.get("url"), "location": j.get("location") or "Remote", "desc": j.get("description","")[:800], "salary": "See link", "source": "Arbeitnow", "posted_date": parse_date(j.get("created_at"))})
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
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            desc = re.sub("<[^>]+>", " ", item.findtext("description") or "")[:800]
            pub = item.findtext("pubDate") or ""
            out.append({"title": title, "company": source_name, "url": link, "location": "Remote", "desc": desc, "salary": "See link", "source": source_name, "posted_date": parse_date(pub)})
        print(f"{source_name} {len(out)}")
        return out
    except Exception as e:
        print(f"{source_name} error {e}")
        return []

FETCHERS = {
    "remoteok": fetch_remoteok,
    "remotive": fetch_remotive,
    "arbeitnow": fetch_arbeitnow,
    "wwr_all": lambda: fetch_rss("https://weworkremotely.com/categories/remote-programming-jobs.rss", "WeWorkRemotely"),
    "wwr_design": lambda: fetch_rss("https://weworkremotely.com/categories/remote-design-jobs.rss", "WeWorkRemotely"),
    "jobicy": lambda: fetch_rss("https://jobicy.com/feed/", "Jobicy"),
    "remote_co": lambda: fetch_rss("https://remote.co/remote-jobs/feed/", "Remote.co"),
    "himalayas": lambda: fetch_rss("https://himalayas.app/jobs/rss", "Himalayas"),
}

def get_freelancer_category(title, desc):
    text = (title + " " + desc).lower()
    # 1. Block engineers / senior roles first
    for b in BLOCKED:
        if b in text:
            return None
    # 2. Match to freelancer category
    for cat, kws in CAT_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                return cat
    return None  # Not a freelancer job - skip it

def reject_reason(job, posted_norm):
    if norm_url(job["url"]) in posted_norm:
        return "repeat-url"
    if not job["url"] or len(job["url"]) < 10:
        return "no-url"
    text = (job["title"] + " " + job["desc"]).lower()
    if any(x in text for x in ["position filled", "job is closed", "applications closed", "no longer accepting applications"]):
        return "closed"
    if any(x in text for x in ["pay to apply", "pay fee", "training fee", "activation fee"]):
        return "scam-fee"
    if job.get("posted_date"):
        age = (datetime.now(timezone.utc) - job["posted_date"]).days
        if age > MAX_AGE_DAYS:
            return f"too-old-{age}d"
    return None

def analyze_job(job):
    text = (job["title"] + " " + job["desc"] + " " + job["location"]).lower()
    if any(x in text for x in ["us only", "united states only", "us-based", "must be in us", "usa only"]):
        return "🇺🇸 US ONLY", 2
    if any(x in text for x in ["eu only", "europe only", "uk only", "must be in eu", "must be in uk"]):
        return "🇪🇺 EU / UK ONLY", 2
    if any(x in text for x in ["worldwide", "global", "anywhere", "all countries"]):
        return "🌍 Worldwide - All Can Apply ✅", 10
    return "🌍 Worldwide - Check link ✅", 6

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=20)
    print(f"TELEGRAM: {resp.status_code} - {resp.text[:300]}")
    return resp

def main():
    state = load_json("state.json", {"last_source": -1, "last_categories": [], "ad_posted_today": "", "last_title": ""})
    # Load posted as NORMALIZED urls - fixes repeat when same job has / vs no /
    posted_raw = load_json("posted.json", [])
    posted_norm = set([norm_url(u) for u in posted_raw])
    print(f"Posted memory: {len(posted_norm)} jobs")
    today = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now(timezone.utc).hour

    # AD - 1x per day, short, NO price
    if hour == 6 and state.get("ad_posted_today") != today:
        ad = f"""📢 <b>ADVERTISE HERE</b>

Hiring? Have a job / service for job seekers?
Your post will be seen by job seekers worldwide.

👉 DM Admin: {ADMIN}
"""
        resp = send_to_telegram(ad)
        if resp.status_code == 200:
            state["ad_posted_today"] = today
            save_json("state.json", state)
        return

    last_cats = state.get("last_categories", [])
    # --- PICK NEXT CATEGORY IN ROTATION ---
    # Find first category in FREELANCER_CATS that is NOT in last 10
    target_cat = None
    for cat in FREELANCER_CATS:
        if cat not in last_cats[-10:]:
            target_cat = cat
            break
    if not target_cat:
        # All used recently, start again from first
        target_cat = FREELANCER_CATS[0]
    print(f"Target category this run: {target_cat} | Last cats: {last_cats[-5:]}")

    start_idx = (state.get("last_source", -1) + 1) % len(SOURCES)
    ordered = SOURCES[start_idx:] + SOURCES[:start_idx]

    candidates = []
    candidates_any = []

    for source_name in ordered:
        jobs = FETCHERS[source_name]()
        random.shuffle(jobs)
        for job in jobs:
            if reject_reason(job, posted_norm):
                continue
            cat = get_freelancer_category(job["title"], job["desc"])
            if not cat:
                continue  # Not freelancer job - skip engineer etc.
            # Keep all freelancer jobs, but prefer target category
            who, score = analyze_job(job)
            if cat == target_cat:
                candidates.append((job, who, cat, score))
            else:
                candidates_any.append((job, who, cat, score))
        # If we found 3+ jobs for target category, stop searching - enough
        if len(candidates) >= 3:
            print(f"Found {len(candidates)} for {target_cat} from {source_name}, stopping")
            break

    # Prefer target category, else any freelancer category (but NOT last category)
    chosen = None
    if candidates:
        # RANDOM pick among top candidates - NOT always #1, this stops repeat when you run twice quickly
        random.shuffle(candidates)
        chosen = candidates[0]
    else:
        print(f"No job for {target_cat}, trying any freelancer category except last")
        # Filter out last category
        filtered = [c for c in candidates_any if c[2] not in last_cats[-3:]]
        if filtered:
            random.shuffle(filtered)
            chosen = filtered[0]
        elif candidates_any:
            random.shuffle(candidates_any)
            chosen = candidates_any[0]

    if not chosen:
        print("No freelancer job found from any source")
        return

    job, who, cat, score = chosen
    # Extra safety: if title same as last posted title, skip - this was your repeat bug
    if job["title"].strip().lower() == state.get("last_title", "").strip().lower():
        print(f"SKIP: Same title as last post: {job['title']}")
        return

    date_str = ""
    if job.get("posted_date"):
        date_str = f"\n📅 Posted: {job['posted_date'].strftime('%d %b %Y')}"
    # If no date, don't lie - just don't show date line

    # SHORT POST - "Never pay" appears ONCE only, at bottom
    message = f"""🌍 <b>REMOTE JOB - {cat}</b>{date_str}

📌 <b>{html.escape(job['title'])}</b>
🏢 {html.escape(job['company'] or 'Company')}
📍 {html.escape(job['location'])}
💰 {html.escape(job['salary'])}

{who}

👉 <b>Apply Here:</b> {job['url']}

⚠️ Never pay to apply for a job.
"""
    resp = send_to_telegram(message)
    if resp.status_code == 200:
        posted_raw.append(job["url"])
        last_cats.append(cat)
        state["last_categories"] = last_cats[-15:]
        state["last_source"] = SOURCES.index(job["source"]) if job["source"] in SOURCES else start_idx
        state["last_title"] = job["title"]
        save_json("state.json", state)
        save_json("posted.json", posted_raw)
        print(f"SUCCESS: {cat} - {job['title']}")

if __name__ == "__main__":
    main()
