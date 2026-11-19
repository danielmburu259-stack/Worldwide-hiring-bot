# RemoteJobsHiringNow - V5 FIXED - GitHub ONLY
# Fixes: Reads all secrets, shows real Telegram error, does NOT save if post fails
import os, json, requests, html, random, re, sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

# --- READ FROM GITHUB SECRETS - All 3 ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
# You added TELEGRAM_CHAT_ID and CHANNEL_ID as secrets - we use both
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip() or os.getenv("TELEGRAM_CHAT_ID", "").strip() or os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
if not CHANNEL_ID:
    CHANNEL_ID = "@RemoteJobsHiringNow"

ADMIN = "@dantez4u"
MAX_AGE_DAYS = 7

print(f"DEBUG: BOT_TOKEN exists? {bool(BOT_TOKEN)} len={len(BOT_TOKEN)}")
print(f"DEBUG: CHANNEL_ID = {CHANNEL_ID}")
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN is empty! Check Secrets - name must be exactly BOT_TOKEN")
    sys.exit(1)

SOURCES = ["remoteok", "remotive", "arbeitnow", "wwr_all", "wwr_design", "jobicy", "remote_co", "himalayas"]

def load_json(name, default):
    try:
        with open(name) as f: return json.load(f)
    except Exception as e:
        print(f"load {name} failed: {e}")
        return default

def save_json(name, data):
    with open(name, "w") as f: json.dump(data, f, indent=2)

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

def is_fresh(posted_date):
    if not posted_date: return True
    return (datetime.now(timezone.utc) - posted_date).days <= MAX_AGE_DAYS

def fetch_remoteok():
    try:
        r = requests.get("https://remoteok.com/api?tag=remote", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        out = []
        for j in r.json():
            if not isinstance(j, dict) or not j.get("position"): continue
            out.append({"title": j.get("position"), "company": j.get("company"), "url": j.get("url"), "location": j.get("location","Remote"), "desc": " ".join(j.get("tags",[])), "salary": f"${j.get('salary_min','')} - ${j.get('salary_max','')}" if j.get("salary_min") else "See link", "source": "RemoteOK", "posted_date": parse_date(j.get("date"))})
        print(f"RemoteOK fetched {len(out)} jobs")
        return out
    except Exception as e:
        print(f"RemoteOK error: {e}")
        return []

def fetch_remotive():
    try:
        r = requests.get("https://remotive.com/api/remote-jobs?limit=100", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        out = []
        for j in r.json().get("jobs", []):
            out.append({"title": j.get("title"), "company": j.get("company_name"), "url": j.get("url"), "location": j.get("candidate_required_location","Remote"), "desc": j.get("description","")[:800], "salary": j.get("salary") or "See link", "source": "Remotive", "posted_date": parse_date(j.get("publication_date"))})
        print(f"Remotive fetched {len(out)} jobs")
        return out
    except Exception as e:
        print(f"Remotive error: {e}")
        return []

def fetch_arbeitnow():
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        out = []
        for j in r.json().get("data", []):
            out.append({"title": j.get("title"), "company": j.get("company_name"), "url": j.get("url"), "location": j.get("location") or "Remote", "desc": j.get("description","")[:800], "salary": "See link", "source": "Arbeitnow", "posted_date": parse_date(j.get("created_at"))})
        print(f"Arbeitnow fetched {len(out)} jobs")
        return out
    except Exception as e:
        print(f"Arbeitnow error: {e}")
        return []

def fetch_rss(url, source_name):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        root = ET.fromstring(r.content)
        out = []
        for item in root.findall(".//item")[:40]:
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            desc = re.sub("<[^>]+>", " ", item.findtext("description") or "")[:800]
            pub = item.findtext("pubDate") or ""
            out.append({"title": title, "company": source_name, "url": link, "location": "Remote", "desc": desc, "salary": "See link", "source": source_name, "posted_date": parse_date(pub)})
        print(f"{source_name} RSS fetched {len(out)} jobs")
        return out
    except Exception as e:
        print(f"{source_name} RSS error: {e}")
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
    if any(x in text for x in ["position filled", "job closed", "no longer accepting", "applications closed", "expired"]):
        return True
    if any(x in text for x in ["pay to apply", "pay fee", "deposit", "training fee", "activation fee"]):
        return True
    if job.get("posted_date") and not is_fresh(job["posted_date"]):
        return True
    return False

def analyze_job(job):
    text = (job["title"] + " " + job["desc"] + " " + job["location"]).lower()
    if any(x in text for x in ["us only", "united states only", "us-based", "must be in us", "usa only"]):
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
    if job.get("posted_date"):
        age = (datetime.now(timezone.utc) - job["posted_date"]).days
        if age <= 1: score += 5
        elif age <= 3: score += 3
    return who, score

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}, timeout=20)
    print(f"TELEGRAM RESPONSE: {resp.status_code} - {resp.text[:500]}")
    return resp

def main():
    state = load_json("state.json", {"last_source": -1, "last_categories": [], "ad_posted_today": ""})
    posted = set(load_json("posted.json", []))
    print(f"Posted memory: {len(posted)} jobs already posted")
    today = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now(timezone.utc).hour
    print(f"UTC Hour now: {hour}, Today: {today}")

    # --- DAILY AD ---
    if hour == 6 and state.get("ad_posted_today") != today:
        ad_text = f"""📢 <b>ADVERTISE HERE - TO GLOBAL JOB SEEKERS</b>

Want your skills posted here?
Are you hiring?
Do you have a job / service / course for job seekers?

👉 <b>DM Admin: {ADMIN}</b>
💬 Message Admin for details - We will agree in DM

⚠️ We never charge to APPLY for a job. You only pay if YOU want to advertise.

Share this channel 👉 https://t.me/RemoteJobsHiringNow
"""
        resp = send_to_telegram(ad_text)
        if resp.status_code == 200:
            state["ad_posted_today"] = today
            save_json("state.json", state)
            print("Ad posted OK")
        else:
            print("Ad FAILED - not saving state, will retry next run")
        return

    next_src_idx = (state["last_source"] + 1) % len(SOURCES)
    source_name = SOURCES[next_src_idx]
    print(f"Trying source: {source_name} (index {next_src_idx})")
    jobs = FETCHERS[source_name]()
    random.shuffle(jobs)
    last_cats = state.get("last_categories", [])
    print(f"Last categories to avoid: {last_cats}")

    best = None
    best_score = -999
    best_cat = ""
    skipped_closed = 0
    skipped_repeat = 0
    skipped_cat = 0

    for job in jobs:
        if job["url"] in posted:
            skipped_repeat += 1
            continue
        if is_closed(job):
            skipped_closed += 1
            continue
        cat = get_category(job["title"])
        if any(is_similar(cat, old) for old in last_cats):
            skipped_cat += 1
            continue
        who, score = analyze_job(job)
        if score > best_score:
            best_score = score
            best = (job, who)
            best_cat = cat

    print(f"Filtered: repeat={skipped_repeat}, closed/old={skipped_closed}, same-category={skipped_cat}, found_best={bool(best)}")

    if not best:
        for job in jobs:
            if job["url"] in posted: continue
            if is_closed(job): continue
            who, score = analyze_job(job)
            best = (job, who)
            best_cat = get_category(job["title"])
            print(f"Fallback used: {job['title']} cat={best_cat}")
            break

    if not best:
        print(f"No OPEN job from {source_name} - will try next source in 5h")
        state["last_source"] = next_src_idx
        save_json("state.json", state)
        return

    job, who = best
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
    resp = send_to_telegram(message)
    if resp.status_code == 200:
        # ONLY save if Telegram actually posted - this was the bug
        posted.add(job["url"])
        last_cats.append(best_cat)
        state["last_categories"] = last_cats[-15:]
        state["last_source"] = next_src_idx
        save_json("state.json", state)
        save_json("posted.json", list(posted))
        print(f"SUCCESS: Posted {best_cat} from {source_name}")
    else:
        print("FAILED: Not saving to posted.json, will retry same job next time")
        # Still advance source so we don't get stuck on broken source
        state["last_source"] = next_src_idx
        save_json("state.json", state)

if __name__ == "__main__":
    main()
