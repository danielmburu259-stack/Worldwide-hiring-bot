# RemoteJobsHiringNow - FINAL BEST - Do Not Change
import os, json, requests, html, random, re, sys, hashlib
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip() or os.getenv("TELEGRAM_CHAT_ID", "").strip() or os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
if not CHANNEL_ID:
    CHANNEL_ID = "@RemoteJobsHiringNow"
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
    "Translation": ["translator", "translation", "interpreter", "bilingual", "transcription"],
    "Transcription": ["transcription", "transcriber", "caption", "subtitle"],
    "Sales": ["sales", "sales rep", "appointment setter", "cold caller", "business development", "lead gen"],
    "Admin": ["administrative", "admin", "bookkeeping", "bookkeeper", "receptionist", "scheduling"],
    "Video Editing": ["video edit", "video editor", "video editing", "youtube editor", "reels editor"],
}

BLOCKED_IN_TITLE = [
    "engineer", "engineering", "developer", "devops", "software", "backend", "frontend",
    "data scientist", "machine learning", "architect", "cto", "principal",
    "staff", "java", "python", "react", "node", "kubernetes",
    "cybersecurity", "security", "blockchain", "quant", "phd", "research scientist",
    "product manager", "engineering manager", "director", "vp ", "head of",
    "medical", "doctor", "nurse", "lawyer", "attorney", "accountant", "accounting",
    "mechanical", "electrical", "civil", "chemical", "aerospace",
    "graduate", "internship", "intern", "2027", "2028", "apprentice",
    "senior", "lead", "manager", "supervisor",
    "underwriting", "underwriter", "insurance", "finance", "banking", "bank", "loan", "mortgage", "consultant", "field",
]

BLOCKED_IN_DESC = ["pay to apply", "pay fee", "training fee", "activation fee", "membership fee", "position filled", "job is closed", "applications closed", "no longer accepting"]

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
        if str(raw).isdigit(): return datetime.fromtimestamp(int(raw), tz=timezone.utc)
        return parsedate_to_datetime(str(raw))
    except: return None

def get_age_days(job):
    if not job.get("posted_date"): return 0
    return (datetime.now(timezone.utc) - job["posted_date"]).days

def is_fresh(job): return get_age_days(job) <= PREFERRED_AGE_DAYS

def clean_title_company(title, company, url):
    t = (title or "").strip()
    c = (company or "").strip()
    # Fix "Tebra: Product Designer" -> Title=Product Designer, Company=Tebra
    if ":" in t and len(t.split(":")[0]) < 30:
        maybe_company, maybe_title = t.split(":", 1)
        if maybe_title.strip():
            c = maybe_company.strip()
            t = maybe_title.strip()
    # Fix "Product Designer at Tebra"
    if " at " in t.lower():
        parts = re.split(r"\s+at\s+", t, flags=re.I)
        if len(parts) == 2 and len(parts[1]) < 30:
            t = parts[0].strip()
            c = parts[1].strip().title()
    # Fix company from Himalayas URL: /companies/manulife/jobs/...
    m = re.search(r"/companies/([^/]+)/", url or "")
    if m and c.lower() in ["himalayas", "jobicy", "weworkremotely", "remote.co", ""]:
        c = m.group(1).replace("-", " ").title()
    return t, c

def extract_salary(desc):
    if not desc: return ""
    m = re.search(r"\$\s?[\d,]+(?:\s?[-–]\s?\$?\s?[\d,]+)?(?:\s?/\s?(hour|hr|year|yr|month))?", desc, flags=re.I)
    if m: return m.group(0).strip()
    m2 = re.search(r"(\d{2,3}k\s?[-–]\s?\d{2,3}k|\$\d+k)", desc, flags=re.I)
    if m2: return m2.group(0)
    return ""

def extract_job_type(desc, title):
    text = ((title or "") + " " + (desc or "")).lower()
    if "part-time" in text or "part time" in text: return "Part-time"
    if "contract" in text: return "Contract"
    if "freelance" in text: return "Freelance"
    if "full-time" in text or "full time" in text: return "Full-time"
    if "temporary" in text: return "Temporary"
    return ""

def extract_snippet(desc):
    if not desc: return ""
    clean = re.sub(r"\s+", " ", desc).strip()
    clean = re.sub(r"^(about.*?:|job description:?|description:?)\s*", "", clean, flags=re.I)
    if len(clean) < 20: return ""
    # First sentence, max 160 chars
    sentence = clean.split(". ")[0].strip()
    if len(sentence) > 160: sentence = sentence[:157] + "..."
    if not sentence.endswith(".") and not sentence.endswith("..."): sentence += "."
    return sentence

def fetch_remoteok():
    try:
        r = requests.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        out = []
        for j in r.json():
            if not isinstance(j, dict) or not j.get("position"): continue
            title, company = clean_title_company(j.get("position"), j.get("company"), j.get("url"))
            out.append({"title": title, "company": company, "url": j.get("url"), "location": j.get("location", "Remote"), "desc": " ".join(j.get("tags", [])) + " " + str(j.get("description", ""))[:1200], "salary": f"${j.get('salary_min','')} - ${j.get('salary_max','')}" if j.get("salary_min") else "", "source": "RemoteOK", "posted_date": parse_date(j.get("date"))})
        print(f"RemoteOK {len(out)}")
        return out
    except Exception as e:
        print(f"RemoteOK error {e}"); return []

def fetch_remotive():
    try:
        r = requests.get("https://remotive.com/api/remote-jobs?limit=100", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        out = []
        for j in r.json().get("jobs", []):
            title, company = clean_title_company(j.get("title"), j.get("company_name"), j.get("url"))
            out.append({"title": title, "company": company, "url": j.get("url"), "location": j.get("candidate_required_location", "Remote"), "desc": j.get("description", "")[:1200], "salary": j.get("salary") or "", "source": "Remotive", "posted_date": parse_date(j.get("publication_date"))})
        print(f"Remotive {len(out)}")
        return out
    except Exception as e:
        print(f"Remotive error {e}"); return []

def fetch_arbeitnow():
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        out = []
        for j in r.json().get("data", []):
            title, company = clean_title_company(j.get("title"), j.get("company_name"), j.get("url"))
            out.append({"title": title, "company": company, "url": j.get("url"), "location": j.get("location") or "Remote", "desc": j.get("description", "")[:1200], "salary": "", "source": "Arbeitnow", "posted_date": parse_date(j.get("created_at"))})
        print(f"Arbeitnow {len(out)}")
        return out
    except Exception as e:
        print(f"Arbeitnow error {e}"); return []

def fetch_rss(url, source_name):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        root = ET.fromstring(r.content)
        out = []
        for item in root.findall(".//item")[:50]:
            title_raw = item.findtext("title") or ""
            link = item.findtext("link") or ""
            desc = re.sub("<[^>]+>", " ", item.findtext("description") or "")[:1200]
            pub = item.findtext("pubDate") or ""
            title, company = clean_title_company(title_raw, source_name, link)
            out.append({"title": title, "company": company, "url": link, "location": "Remote", "desc": desc, "salary": "", "source": source_name, "posted_date": parse_date(pub)})
        print(f"{source_name} {len(out)}")
        return out
    except Exception as e:
        print(f"{source_name} error {e}"); return []

FETCHERS = {"remoteok": fetch_remoteok, "remotive": fetch_remotive, "arbeitnow": fetch_arbeitnow, "wwr_all": lambda: fetch_rss("https://weworkremotely.com/categories/remote-programming-jobs.rss", "WeWorkRemotely"), "wwr_design": lambda: fetch_rss("https://weworkremotely.com/categories/remote-design-jobs.rss", "WeWorkRemotely"), "jobicy": lambda: fetch_rss("https://jobicy.com/feed/", "Jobicy"), "remote_co": lambda: fetch_rss("https://remote.co/remote-jobs/feed/", "Remote.co"), "himalayas": lambda: fetch_rss("https://himalayas.app/jobs/rss", "Himalayas")}

def get_freelancer_category(title, desc):
    t = (title or "").lower()
    # FIXED: Word-boundary matching - "writing" will NOT match "underwriting"
    for b in BLOCKED_IN_TITLE:
        if re.search(r"\b" + re.escape(b) + r"\b", t):
            return None
    for cat, kws in CAT_KEYWORDS.items():
        for kw in kws:
            if re.search(r"\b" + re.escape(kw) + r"\b", t):
                return cat
    return None

def reject_reason(job, posted_urls, posted_ids, max_age=MAX_AGE_DAYS):
    if norm_url(job["url"]) in posted_urls: return "repeat-url"
    if make_id(job) in posted_ids: return "repeat-id"
    if not job["url"] or len(job["url"]) < 10: return "no-url"
    text = (job["title"] + " " + job["desc"]).lower()
    for bad in BLOCKED_IN_DESC:
        if bad in text: return f"blocked-{bad}"
    age = get_age_days(job)
    if age > max_age: return f"too-old-{age}d"
    return None

def get_location_line(job):
    loc = (job["location"] or "Remote").strip()
    low = loc.lower()
    if any(x in low for x in ["(uk)", "united kingdom", " london", "england", " uk"]): return "📍 Remote (UK) - Check link if your country can apply", "🇬🇧 UK Based - Check Link"
    if any(x in low for x in ["(us)", "united states", "usa", "america", "new york", "california", "texas", " us"]): return "📍 Remote (US) - Check link if your country can apply", "🇺🇸 US Based - Check Link"
    if any(x in low for x in ["(eu)", "europe", "germany", "france", "netherlands", "spain", "berlin", "switzerland", "swiss", "zurich", "austria", "belgium"]): return "📍 Remote (EU) - Check link if your country can apply", "🇪🇺 EU Based - Check Link"
    if any(x in low for x in ["worldwide", "global", "anywhere", "remote"]): return "📍 Worldwide", "🌍 Worldwide - All Can Apply ✅"
    return f"📍 {loc}", "🌍 Check Link ✅"

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=20)
    print(f"TELEGRAM: {resp.status_code} - {resp.text[:300]}")
    return resp

def main():
    state = load_json("state.json", {"last_source": -1, "last_categories": [], "ad_posted_today": "", "last_title": "", "last_source_name": ""})
    posted_data = load_json("posted.json", [])
    posted_urls = set(); posted_ids = set()
    for item in posted_data:
        if isinstance(item, dict):
            posted_urls.add(norm_url(item.get("url", ""))); posted_ids.add(item.get("id", ""))
        else: posted_urls.add(norm_url(item))
    print(f"Memory: {len(posted_urls)} URLs | Last source: {state.get('last_source_name')} | Last cats: {state.get('last_categories', [])[-3:]}")
    today = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now(timezone.utc).hour
    if hour == 6 and state.get("ad_posted_today") != today:
        ad = f"""📢 <b>ADVERTISE HERE</b>\n\nHiring? Have a job / service for job seekers?\nYour post will be seen by job seekers worldwide.\n\n👉 DM Admin: {ADMIN}\n\n📣 Share this channel: {SHARE_LINK}\n"""
        resp = send_to_telegram(ad)
        if resp.status_code == 200:
            state["ad_posted_today"] = today; save_json("state.json", state)
        return
    last_cats = state.get("last_categories", [])
    last_source_name = state.get("last_source_name", "")
    target_cat = None
    for cat in FREELANCER_CATS:
        if cat not in last_cats[-10:]:
            target_cat = cat; break
    if not target_cat: target_cat = FREELANCER_CATS[0]
    print(f"Target category: {target_cat}")
    start_idx = (state.get("last_source", -1) + 1) % len(SOURCES)
    ordered = SOURCES[start_idx:] + SOURCES[:start_idx]
    ordered = [s for s in ordered if s != last_source_name]
    print(f"Source order (last source removed): {ordered}")
    candidates_target = []; candidates_any = []
    print("PASS 1: Fresh 2 days")
    for source_name in ordered:
        jobs = FETCHERS[source_name]()
        random.shuffle(jobs)
        for job in jobs:
            if reject_reason(job, posted_urls, posted_ids, max_age=MAX_AGE_DAYS): continue
            if not is_fresh(job): continue
            cat = get_freelancer_category(job["title"], job["desc"])
            if not cat: continue
            if cat == target_cat: candidates_target.append((job, cat, source_name))
            else:
                if cat not in last_cats[-3:]: candidates_any.append((job, cat, source_name))
        if len(candidates_target) >= 3: break
    if not candidates_target:
        print("PASS 2: Backup 7 days, target only")
        for source_name in ordered:
            jobs = FETCHERS[source_name]()
            random.shuffle(jobs)
            for job in jobs:
                if reject_reason(job, posted_urls, posted_ids, max_age=MAX_AGE_DAYS): continue
                cat = get_freelancer_category(job["title"], job["desc"])
                if cat == target_cat: candidates_target.append((job, cat, source_name))
            if len(candidates_target) >= 3: break
    chosen = None
    if candidates_target:
        random.shuffle(candidates_target); chosen = candidates_target[0]; print(f"Chose TARGET: {chosen[1]} from {chosen[2]}")
    elif candidates_any:
        for cat_in_order in FREELANCER_CATS:
            if cat_in_order in last_cats[-3:]: continue
            group = [c for c in candidates_any if c[1] == cat_in_order]
            if group:
                random.shuffle(group); chosen = group[0]; print(f"Chose NEXT-ORDER: {chosen[1]} from {chosen[2]}"); break
    if not chosen:
        print("No freelancer job found"); return
    job, cat, source_name = chosen
    if job["title"].strip().lower() == state.get("last_title", "").strip().lower():
        print("SKIP: Same title"); return
    date_str = ""
    if job.get("posted_date"): date_str = f"\n📅 Posted: {job['posted_date'].strftime('%d %b %Y')}"
    else: date_str = "\n📅 Posted: Recently"
    loc_line, who_line = get_location_line(job)
    salary = (job.get("salary") or "").strip() or extract_salary(job.get("desc", ""))
    salary_line = f"\n💰 Salary: {html.escape(salary)}" if salary else "\n💰 Salary: Not listed - Check link"
    job_type = extract_job_type(job.get("desc", ""), job.get("title", ""))
    type_line = f"\n🕒 Type: {job_type}" if job_type else ""
    snippet = extract_snippet(job.get("desc", ""))
    snippet_line = f"\n📋 {html.escape(snippet)}" if snippet else ""
    message = f"""🌍 <b>REMOTE JOB - {cat}</b>{date_str}\n\n📌 <b>{html.escape(job['title'])}</b>\n🏢 {html.escape(job['company'] or 'Company')}\n{loc_line}{salary_line}{type_line}{snippet_line}\n\n{who_line}\n\n👉 <b>Apply Here:</b> {job['url']}\n\n⚠️ Never pay to apply for a job.\n\n📣 Share with a friend who needs a job 👉 {SHARE_LINK}\n"""
    resp = send_to_telegram(message)
    if resp.status_code == 200:
        posted_data.append({"url": job["url"], "id": make_id(job), "title": job["title"], "date": today, "category": cat, "source": source_name})
        last_cats.append(cat)
        state["last_categories"] = last_cats[-15:]
        state["last_source"] = SOURCES.index(source_name) if source_name in SOURCES else start_idx
        state["last_source_name"] = source_name
        state["last_title"] = job["title"]
        save_json("state.json", state); save_json("posted.json", posted_data)
        print(f"SUCCESS: {cat} from {source_name} - {job['title']}")

if __name__ == "__main__":
    main()
