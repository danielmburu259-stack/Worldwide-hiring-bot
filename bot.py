# RemoteJobsHiringNow - V4 FINAL - GitHub ONLY
# Rules: NO public prices. NO fixed categories. ONLY OPEN jobs. NEVER repeat.
# Bot: Free job every 5h + 1 ad post per day (DM admin only)
# Paid posts: MANUAL by @dantez4u only
import os, json, requests, html, random, re
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@RemoteJobsHiringNow"
ADMIN = "@dantez4u"
MAX_AGE_DAYS = 7  # Only jobs posted in last 7 days = still open

SOURCES = ["remoteok", "remotive", "arbeitnow", "wwr_all", "wwr_design", "jobicy", "remote_co", "himalayas"]

def load_json(name, default):
    try:
        with open(name) as f: return json.load(f)
    except: return default

def save_json(name, data):
    with open(name, "w") as f: json.dump(data, f, indent=2)

# --- DATE PARSING: Every source has different date format ---
def parse_date(raw):
    if not raw: return None
    try:
        # ISO: 2026-11-19T10:00:00
        if "T" in str(raw):
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        # Unix timestamp: 1732000000
        if str(raw).isdigit():
            return datetime.fromtimestamp(int(raw), tz=timezone.utc)
        # RSS: Tue, 19 Nov 2026 10:00:00 GMT
        return parsedate_to_datetime(str(raw))
    except:
        return None

def is_fresh(posted_date):
    if not posted_date: return True  # If source has no date, allow but lower score
    now = datetime.now(timezone.utc)
    age = now - posted_date
    return age.days <= MAX_AGE_DAYS

# --- FETCHERS - Now also return posted_date ---
def fetch_remoteok():
    try:
        r = requests.get("https://remoteok.com/api?tag=remote", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        out = []
        for j in r.json():
            if not isinstance(j, dict) or not j.get("position"): continue
            out.append({"title": j.get("position"), "company": j.get("company"), "url": j.get("url"), "location": j.get("location","Remote"), "desc": " ".join(j.get("tags",[])), "salary": f"${j.get('salary_min','')} - ${j.get('salary_max','')}" if j.get("salary_min") else "See link", "source": "RemoteOK", "posted_date": parse_date(j.get("date"))})
        return out
    except: return []

def fetch_remotive():
    try:
        r = requests.get("https://remotive.com/api/remote-jobs?limit=100", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        out = []
        for j in r.json().get("jobs", []):
            out.append({"title": j.get("title"), "company": j.get("company_name"), "url": j.get("url"), "location": j.get("candidate_required_location","Remote"), "desc": j.get("description","")[:800], "salary": j.get("salary") or "See link", "source": "Remotive", "posted_date": parse_date(j.get("publication_date"))})
        return out
    except: return []

def fetch_arbeitnow():
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        out = []
        for j in r.json().get("data", []):
            out.append({"title": j.get("title"), "company": j.get("company_name"), "url": j.get("url"), "location": j.get("location") or "Remote", "desc": j.get("description","")[:800], "salary": "See link", "source": "Arbeitnow", "posted_date": parse_date(j.get("created_at"))})
        return out
    except: return []

def fetch_rss(url, source_name):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        root = ET.fromstring(r.content)
        out = []
        for item in root.findall(".//item")[:40]:
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            desc = re.sub("<[^>]+>", " ", item.findtext("description") or "")[:800]
            pub = item.findtext("pubDate") or item.findtext("{http://purl.org/dc/elements/1.1/}date") or ""
            out.append({"title": title, "company": source_name, "url": link, "location": "Remote", "desc": desc, "salary": "See link", "source": source_name, "posted_date": parse_date(pub)})
        return out
    except: return []

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

def get_category(title):
    t = title.lower()
    t = re.sub(r"\b(remote|junior|senior|lead|principal|part-time|full-time|contract)\b", "", t)
    t = re.sub(r"[^a-z ]", " ", t)
    words = [w for w in t.split() if len(w) > 2]
    if len(words) >= 2: return " ".join(words[:2]).title()
    return words[0].title() if words else "General"

def is_similar(cat1, cat2):
    return len(set(cat1.lower().split()) & set(cat2.lower().split())) > 0

def is_closed(job):
    text = (job["title"] + " " + job["desc"]).lower()
    # Closed keywords
    if any(x in text for x in ["position filled", "job closed", "no longer accepting", "closed", "filled", "expired", "applications closed"]):
        return True
    # Scam / pay to apply
    if any(x in text for x in ["pay to apply", "pay fee", "deposit", "training fee", "activation fee"]):
        return True
    # Too old = treat as closed
    if job.get("posted_date") and not is_fresh(job["posted_date"]):
        return True
    return False

def is_link_alive(url):
    # Quick check: Does apply link still exist? 404 = closed
    try:
        r = requests.head(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, allow_redirects=True)
        if r.status_code in [404, 410, 451]:
            return False
        return True
    except:
        return True  # If we can't check, don't block - let user try

def analyze_job(job):
    text = (job["title"] + " " + job["desc"] + " " + job["location"]).lower()
    if any(x in text for x in ["us only", "united states only", "us-based", "must be in us", "usa only", "us citizens only"]):
        who = "🇺🇸 US ONLY - Do not apply if outside US"
        score = 2
    elif any(x in text for x in ["eu only", "europe only", "uk only", "must be in eu", "must be in uk"]):
        who = "🇪🇺 EU / UK ONLY"
        score = 2
    elif any(x in text for x in ["worldwide", "global", "anywhere", "all countries"]):
        who = "🌍 Worldwide - All Countries Can Apply ✅"
        score = 10
    else:
        who = "🌍 Worldwide - All Countries (Check link for details) ✅"
        score = 6
    # Freshness bonus: Posted today = +5, Posted 2 days ago = +3
    if job.get("posted_date"):
        age = (datetime.now(timezone.utc) - job["posted_date"]).days
        if age <= 1: score += 5
        elif age <= 3: score += 3
    return who, score

def main():
    state = load_json("state.json", {"last_source": -1, "last_categories": [], "ad_posted_today": ""})
    # posted.json is PERMANENT memory - never delete it, never repeat
    posted = set(load_json("posted.json", []))
    today = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now().hour

    # --- DAILY AD: 1x per day, NO PRICE ---
    if hour == 6 and state.get("ad_posted_today") != today:
        ad_text = f"""📢 <b>ADVERTISE HERE - TO GLOBAL JOB SEEKERS</b>

Want your skills posted here?
Are you hiring?
Do you have a job / service / course for job seekers?

Your post will be seen by job seekers worldwide in this channel.

👉 <b>DM Admin: {ADMIN}</b>
💬 Message Admin for details - We will agree in DM

⚠️ We never charge to APPLY for a job. You only pay if YOU want to advertise.

Share this channel 👉 https://t.me/RemoteJobsHiringNow
"""
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHANNEL_ID, "text": ad_text, "parse_mode": "HTML"})
        state["ad_posted_today"] = today
        save_json("state.json", state)
        print("Ad posted")
        return

    # --- JOB POST ---
    next_src_idx = (state["last_source"] + 1) % len(SOURCES)
    source_name = SOURCES[next_src_idx]
    jobs = FETCHERS[source_name]()
    random.shuffle(jobs)
    last_cats = state.get("last_categories", [])

    best = None
    best_score = -999
    best_cat = ""

    for job in jobs:
        # 1. NEVER REPEAT - Check posted.json first
        if job["url"] in posted:
            continue
        # 2. MUST BE OPEN - Check date + closed words
        if is_closed(job):
            continue
        # 3. DIFFERENT CATEGORY - Not same as last 15
        cat = get_category(job["title"])
        if any(is_similar(cat, old) for old in last_cats):
            continue
        who, score = analyze_job(job)
        if score > best_score:
            # 4. LINK ALIVE - Only check for the best candidate, to save time
            if not is_link_alive(job["url"]):
                continue
            best_score = score
            best = (job, who)
            best_cat = cat

    # Fallback: If all filtered out, try any open job from same source (even if category repeats, but still never repeat URL + still open)
    if not best:
        for job in jobs:
            if job["url"] in posted: continue
            if is_closed(job): continue
            who, score = analyze_job(job)
            if not is_link_alive(job["url"]): continue
            best = (job, who)
            best_cat = get_category(job["title"])
            break

    if not best:
        print(f"No OPEN job found from {source_name} - skipping this run, will try next source in 5h")
        # IMPORTANT: Still advance source, so next run tries different source
        state["last_source"] = next_src_idx
        save_json("state.json", state)
        return

    job, who = best
    # --- SAVE BEFORE POSTING - So even if Telegram fails, we never post same job twice ---
    posted.add(job["url"])
    last_cats.append(best_cat)
    state["last_categories"] = last_cats[-15:]
    state["last_source"] = next_src_idx
    save_json("state.json", state)
    save_json("posted.json", list(posted))

    # Show posted date to user - proves it's fresh
    date_str = ""
    if job.get("posted_date"):
        date_str = f"\n📅 Posted: {job['posted_date'].strftime('%d %b %Y')} - Still Open ✅"

    message = f"""🌍 <b>FREE JOB - {best_cat}</b> {date_str}

📌 <b>{html.escape(job['title'])}</b>
🏢 {html.escape(job['company'] or 'Company')}
📍 {html.escape(job['location'])}
💰 {html.escape(job['salary'])}
🏷️ Source: {job['source']}

{who}

<b>HOW TO APPLY:</b>
1. Tap Apply link below
2. Click Apply on company site
3. Upload CV + fill form (2-5 mins)
4. No fee - If they ask for money, it's SCAM, leave it

👉 <b>Apply Here:</b> {job['url']}

⚠️ Never pay to get a job.
📢 Want your skills / hiring post here? DM Admin {ADMIN}
Share 👉 https://t.me/RemoteJobsHiringNow
"""
    resp = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHANNEL_ID, "text": message, "parse_mode": "HTML"})
    print(f"Posted OPEN job {best_cat} from {source_name}: {resp.status_code} - Total ever posted: {len(posted)}")

if __name__ == "__main__":
    main()
