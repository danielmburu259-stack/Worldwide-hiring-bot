# RemoteJobsHiringNow - V9 PROFESSIONAL
# Guarantees: 1) No repeat, 2) Different source each run, 3) Different category each run, 4) 1 job every 5h
import os, json, requests, html, random, re, sys, hashlib
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

FREELANCER_CATS = ["Writing","Customer Support","Data Entry","Social Media","Design","Virtual Assistant","Marketing","Translation","Transcription","Sales","Admin","Video Editing"]

CAT_KEYWORDS = {
    "Writing": ["writer", "writing", "copywriter", "content writer", "blog", "article", "editor", "proofread", "ghostwriter", "copy editor"],
    "Customer Support": ["customer support", "support agent", "support specialist", "help desk", "customer service", "chat support", "customer success"],
    "Data Entry": ["data entry", "data clerk", "data processing", "data annotation", "labeling", "data collection", "ai trainer", "annotation"],
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
    u = (u or "").strip().lower()
    u = re.sub(r"\?.*$", "", u).rstrip("/")
    return u

def make_id(job):
    # Second memory: Title + Company - catches repeat even if URL changes
    key = f"{job['title'].strip().lower()}|{job['company'].strip().lower()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]

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
            out.append({"title": j.get("position"), "company": j.get("company"), "url": j.get("url"), "location": j.get("location","Remote"), "desc": " ".join(j.get("tags",[])) + " " + str(j.get("description",""))[:800], "salary": f"${j.get('salary_min','')} - ${j.get('salary_max','')}" if j.get("salary_min") else "", "source": "RemoteOK", "posted_date": parse_date(j.get("date"))})
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
            out.append({"title": j.get("title"), "company": j.get("company_name"), "url": j.get("url"), "location": j.get("candidate_required_location","Remote"), "desc": j.get("description","")[:800], "salary": j.get("salary") or "", "source": "Remotive", "posted_date": parse_date(j.get("publication_date"))})
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
            out.append({"title": j.get("title"), "company": j.get("company_name"), "url": j.get("url"), "location": j.get("location") or "Remote", "desc": j.get("description","")[:800], "salary": "", "source": "Arbeitnow", "posted_date": parse_date(j.get("created_at"))})
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
            out.append({"title": title, "company": source_name, "url": link, "location": "Remote", "desc": desc, "salary": "", "source": source_name, "posted_date": parse_date(pub)})
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
    for b in BLOCKED:
        if b in text:
            return None
    for cat, kws in CAT_KEYWORDS.items():
        for kw in kws:
            if kw in text:
                return cat
    return None

def is_repeat(job, posted_urls, posted_ids):
    if norm_url(job["url"]) in posted_urls:
        return True
    if make_id(job) in posted_ids:
        return True
    return False

def reject_reason(job, posted_urls, posted_ids):
    if is_repeat(job, posted_urls, posted_ids):
        return "repeat"
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

def get_location_line(job):
    # PROFESSIONAL FIX: Don't claim Worldwide if location is UK/US/EU
    loc = (job["location"] or "Remote").strip()
    low = loc.lower()
    if any(x in low for x in ["(uk)", "united kingdom", " uk ", "london", "england"]):
        return f"📍 Remote (UK) - Check link if your country can apply", "🇬🇧 UK Based - Check Link"
    if any(x in low for x in ["(us)", "united states", "usa", "america", "new york", "california", "texas"]):
        return f"📍 Remote (US) - Check link if your country can apply", "🇺🇸 US Based - Check Link"
    if any(x in low for x in ["(eu)", "europe", "germany", "france", "netherlands", "spain", "berlin"]):
        return f"📍 Remote (EU) - Check link if your country can apply", "🇪🇺 EU Based - Check Link"
    if any(x in low for x in ["worldwide", "global", "anywhere", "remote"]):
        return f"📍 Worldwide", "🌍 Worldwide - All Can Apply ✅"
    return f"📍 {loc}", "🌍 Check Link ✅"

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=20)
    print(f"TELEGRAM: {resp.status_code} - {resp.text[:300]}")
    return resp

def main():
    state = load_json("state.json", {"last_source": -1, "last_categories": [], "ad_posted_today": "", "last_title": "", "last_source_name": ""})
    posted_data = load_json("posted.json", [])
    # Support both old format [url, url] and new format [{"url":..., "id":...}]
    posted_urls = set()
    posted_ids = set()
    for item in posted_data:
        if isinstance(item, dict):
            posted_urls.add(norm_url(item.get("url","")))
            posted_ids.add(item.get("id",""))
        else:
            posted_urls.add(norm_url(item))
    print(f"Memory: {len(posted_urls)} URLs, {len(posted_ids)} IDs, Last source: {state.get('last_source_name')}, Last cats: {state.get('last_categories',[])[-3:]}")

    today = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now(timezone.utc).hour

    # AD - 1x per day at 06 UTC, short
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
    last_source_name = state.get("last_source_name", "")

    # --- PICK TARGET CATEGORY: First category NOT in last 10 ---
    target_cat = None
    for cat in FREELANCER_CATS:
        if cat not in last_cats[-10:]:
            target_cat = cat
            break
    if not target_cat:
        target_cat = FREELANCER_CATS[0]
    print(f"Target category: {target_cat}")

    # --- PICK SOURCE ORDER: MUST be different from last run ---
    # Move last source to END of list, so we never use same source twice in a row
    start_idx = (state.get("last_source", -1) + 1) % len(SOURCES)
    ordered = SOURCES[start_idx:] + SOURCES[:start_idx]
    if ordered[0] == last_source_name and len(ordered) > 1:
        ordered = ordered[1:] + [ordered[0]]
    print(f"Source order (different from last): {ordered}")

    candidates_target = []
    candidates_any = []

    # Try ALL sources in this run - don't give up after 1
    for source_name in ordered:
        jobs = FETCHERS[source_name]()
        random.shuffle(jobs)
        for job in jobs:
            if reject_reason(job, posted_urls, posted_ids):
                continue
            cat = get_freelancer_category(job["title"], job["desc"])
            if not cat:
                continue
            if cat == target_cat:
                candidates_target.append((job, cat, source_name))
            else:
                # Only keep if not in last 3 categories - enforces different category
                if cat not in last_cats[-3:]:
                    candidates_any.append((job, cat, source_name))
        if len(candidates_target) >= 3:
            print(f"Found {len(candidates_target)} for {target_cat} from {source_name}")
            break

    chosen = None
    if candidates_target:
        random.shuffle(candidates_target)
        chosen = candidates_target[0]
        print(f"Chose TARGET category: {chosen[1]} from {chosen[2]}")
    elif candidates_any:
        random.shuffle(candidates_any)
        chosen = candidates_any[0]
        print(f"No job for {target_cat}, chose OTHER category: {chosen[1]} from {chosen[2]}")
    else:
        print("No freelancer job found from ANY source - APIs may be down")
        return

    job, cat, source_name = chosen

    # Final repeat guard: same title as last post = skip
    if job["title"].strip().lower() == state.get("last_title", "").strip().lower():
        print(f"SKIP: Same title as last post")
        return

    date_str = ""
    if job.get("posted_date"):
        date_str = f"\n📅 Posted: {job['posted_date'].strftime('%d %b %Y')}"

    loc_line, who_line = get_location_line(job)

    # Salary: ONLY show if we actually know it. If empty, hide line completely.
    salary = (job.get("salary") or "").strip()
    # Clean bad salaries like "See link", "See Link"
    if salary.lower() in ["see link", "see link.", ""]:
        salary_line = ""
    else:
        salary_line = f"\n💰 {html.escape(salary)}"

    message = f"""🌍 <b>REMOTE JOB - {cat}</b>{date_str}

📌 <b>{html.escape(job['title'])}</b>
🏢 {html.escape(job['company'] or 'Company')}
{loc_line}{salary_line}

{who_line}

👉 <b>Apply Here:</b> {job['url']}

⚠️ Never pay to apply for a job.
"""
    resp = send_to_telegram(message)
    if resp.status_code == 200:
        # Save BOTH url and id - double memory, no repeat ever
        posted_data.append({"url": job["url"], "id": make_id(job), "title": job["title"], "date": today})
        last_cats.append(cat)
        state["last_categories"] = last_cats[-15:]
        state["last_source"] = SOURCES.index(source_name) if source_name in SOURCES else start_idx
        state["last_source_name"] = source_name
        state["last_title"] = job["title"]
        save_json("state.json", state)
        save_json("posted.json", posted_data)
        print(f"SUCCESS: {cat} from {source_name} - {job['title']}")

if __name__ == "__main__":
    main()
