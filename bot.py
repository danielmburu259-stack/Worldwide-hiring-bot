# RemoteJobsHiringNow - V10 - Share line + Block ALL Engineers + Title-only category
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
SHARE_LINK = "https://t.me/RemoteJobsHiringNow"

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

# FIXED: Block ANY engineer, ANY senior, ANY graduate engineer, ANY 2027 start
BLOCKED = [
    "engineer", "engineering", "developer", "devops", "software", "backend", "frontend",
    "data scientist", "machine learning", "ai engineer", "architect", "cto", "principal",
    "staff engineer", "java", "python", "react", "node", "kubernetes",
    "cybersecurity", "security engineer", "blockchain", "quant", "phd", "research scientist",
    "product manager", "engineering manager", "director", "vp ", "head of",
    "medical", "doctor", "nurse", "lawyer", "attorney", "accountant cpa",
    "mechanical", "electrical", "civil", "chemical", "aerospace",
    "graduate", "internship", "intern", "2027", "2028", "apprentice",
    "senior", "lead engineer", "principal",
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
    # FIXED: 1) Block check on TITLE + DESC - any engineer word = block
    # 2) Category check on TITLE ONLY - not description. Stops "Mechanical Engineer" becoming "Writing" because description says "writing reports"
    t = title.lower()
    d = desc.lower()
    for b in BLOCKED:
        if b in t or b in d:
            # Special: "engineering" in desc but title is freelancer? Still block to be safe
            # But allow "sales engineer" ? No - block all engineer titles
            if b in t:
                return None
            # If blocked word only in desc and title is clearly freelancer, allow it
            # Example: "Customer Support" desc says "engineering team" - that's OK
            # So only block desc if it's strong: engineer, developer, software
            if b in ["engineer", "engineering", "developer", "software", "devops", "mechanical", "electrical", "civil"]:
                if b in d:
                    # Check if title is NOT freelancer - if title matches freelancer, still allow? No, for engineer jobs desc will have engineer, title will also have it, already blocked above
                    pass
    # If title contains any blocked word, reject
    for b in BLOCKED:
        if b in t:
            return None
    # Category from TITLE ONLY
    for cat, kws in CAT_KEYWORDS.items():
        for kw in kws:
            if kw in t:
                return cat
    return None

def reject_reason(job, posted_urls, posted_ids):
    if norm_url(job["url"]) in posted_urls: return "repeat"
    if make_id(job) in posted_ids: return "repeat-id"
    if not job["url"] or len(job["url"]) < 10: return "no-url"
    text = (job["title"] + " " + job["desc"]).lower()
    if any(x in text for x in ["position filled", "job is closed", "applications closed", "no longer accepting applications"]): return "closed"
    if any(x in text for x in ["pay to apply", "pay fee", "training fee", "activation fee"]): return "scam-fee"
    if job.get("posted_date"):
        age = (datetime.now(timezone.utc) - job["posted_date"]).days
        if age > MAX_AGE_DAYS: return f"too-old-{age}d"
    return None

def get_location_line(job):
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
    posted_urls = set()
    posted_ids = set()
    for item in posted_data:
        if isinstance(item, dict):
            posted_urls.add(norm_url(item.get("url","")))
            posted_ids.add(item.get("id",""))
        else:
            posted_urls.add(norm_url(item))
    print(f"Memory: {len(posted_urls)} URLs, Last source: {state.get('last_source_name')}, Last cats: {state.get('last_categories',[])[-3:]}")

    today = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now(timezone.utc).hour

    if hour == 6 and state.get("ad_posted_today") != today:
        ad = f"""📢 <b>ADVERTISE HERE</b>

Hiring? Have a job / service for job seekers?
Your post will be seen by job seekers worldwide.

👉 DM Admin: {ADMIN}

📣 Share this channel: {SHARE_LINK}
"""
        resp = send_to_telegram(ad)
        if resp.status_code == 200:
            state["ad_posted_today"] = today
            save_json("state.json", state)
        return

    last_cats = state.get("last_categories", [])
    last_source_name = state.get("last_source_name", "")
    target_cat = None
    for cat in FREELANCER_CATS:
        if cat not in last_cats[-10:]:
            target_cat = cat
            break
    if not target_cat:
        target_cat = FREELANCER_CATS[0]
    print(f"Target category: {target_cat}")

    start_idx = (state.get("last_source", -1) + 1) % len(SOURCES)
    ordered = SOURCES[start_idx:] + SOURCES[:start_idx]
    if ordered[0] == last_source_name and len(ordered) > 1:
        ordered = ordered[1:] + [ordered[0]]
    print(f"Source order: {ordered}")

    candidates_target = []
    candidates_any = []
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
                if cat not in last_cats[-3:]:
                    candidates_any.append((job, cat, source_name))
        if len(candidates_target) >= 3:
            break

    chosen = None
    if candidates_target:
        random.shuffle(candidates_target)
        chosen = candidates_target[0]
    elif candidates_any:
        random.shuffle(candidates_any)
        chosen = candidates_any[0]
    else:
        print("No freelancer job found")
        return

    job, cat, source_name = chosen
    if job["title"].strip().lower() == state.get("last_title", "").strip().lower():
        print("SKIP: Same title as last")
        return

    date_str = ""
    if job.get("posted_date"):
        date_str = f"\n📅 Posted: {job['posted_date'].strftime('%d %b %Y')}"
    loc_line, who_line = get_location_line(job)
    salary = (job.get("salary") or "").strip()
    salary_line = ""
    if salary and salary.lower() not in ["see link", "see link."]:
        salary_line = f"\n💰 {html.escape(salary)}"

    # PROFESSIONAL POST + SHARE LINE AT BOTTOM
    message = f"""🌍 <b>REMOTE JOB - {cat}</b>{date_str}

📌 <b>{html.escape(job['title'])}</b>
🏢 {html.escape(job['company'] or 'Company')}
{loc_line}{salary_line}

{who_line}

👉 <b>Apply Here:</b> {job['url']}

⚠️ Never pay to apply for a job.

📣 Share with a friend who needs a job 👉 {SHARE_LINK}
"""
    resp = send_to_telegram(message)
    if resp.status_code == 200:
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
