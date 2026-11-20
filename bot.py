# RemoteJobsHiringNow - V6 FIXED
# Fix: Try ALL sources in same run, relaxed open-check, debug why job rejected
import os, json, requests, html, random, re, sys
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip() or os.getenv("TELEGRAM_CHAT_ID", "").strip() or os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
if not CHANNEL_ID:
    CHANNEL_ID = "@RemoteJobsHiringNow"
ADMIN = "@dantez4u"
MAX_AGE_DAYS = 30  # FIXED: Was 7, too strict. RemoteOK dates are often 2-3 weeks old but still open

print(f"DEBUG: BOT_TOKEN exists? {bool(BOT_TOKEN)} len={len(BOT_TOKEN)}")
print(f"DEBUG: CHANNEL_ID = {CHANNEL_ID}")
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN empty")
    sys.exit(1)

SOURCES = ["remoteok", "remotive", "arbeitnow", "wwr_all", "wwr_design", "jobicy", "remote_co", "himalayas"]

def load_json(name, default):
    try:
        with open(name) as f: return json.load(f)
    except: return default

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

def fetch_remoteok():
    try:
        # FIXED: No ?tag=remote, use plain API - gives 100+ jobs, not 3
        r = requests.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        out = []
        for j in r.json():
            if not isinstance(j, dict) or not j.get("position"): continue
            out.append({"title": j.get("position"), "company": j.get("company"), "url": j.get("url"), "location": j.get("location","Remote"), "desc": " ".join(j.get("tags",[])) + " " + str(j.get("description",""))[:500], "salary": f"${j.get('salary_min','')} - ${j.get('salary_max','')}" if j.get("salary_min") else "See link", "source": "RemoteOK", "posted_date": parse_date(j.get("date"))})
        print(f"RemoteOK fetched {len(out)} jobs")
        return out
    except Exception as e:
        print(f"RemoteOK error: {e}")
        return []

def fetch_remotive():
    try:
        r = requests.get("https://remotive.com/api/remote-jobs?limit=100", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
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
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
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
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        root = ET.fromstring(r.content)
        out = []
        for item in root.findall(".//item")[:50]:
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

def reject_reason(job, posted):
    # FIXED: Only reject if REALLY closed. Old code rejected "disclosed", "enclosed" because they contain "closed"
    if job["url"] in posted:
        return "repeat"
    text = (job["title"] + " " + job["desc"]).lower()
    # Only exact phrases, not single word "closed"
    if any(x in text for x in ["position filled", "job is closed", "applications closed", "no longer accepting applications", "this job has expired", "position has been filled"]):
        return "really-closed"
    if any(x in text for x in ["pay to apply", "pay fee", "training fee", "activation fee", "pay $50 to apply"]):
        return "scam-fee"
    if job.get("posted_date"):
        age = (datetime.now(timezone.utc) - job["posted_date"]).days
        if age > MAX_AGE_DAYS:
            return f"too-old-{age}d"
    if not job["url"] or len(job["url"]) < 10:
        return "no-url"
    return None

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
    print(f"Posted memory: {len(posted)} jobs")
    today = datetime.now().strftime("%Y-%m-%d")
    hour = datetime.now(timezone.utc).hour
    print(f"UTC Hour: {hour}, Today: {today}")

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
        return

    # FIXED: Try ALL sources in this ONE run, in rotated order. Don't wait 5h if first fails.
    start_idx = (state.get("last_source", -1) + 1) % len(SOURCES)
    ordered_sources = SOURCES[start_idx:] + SOURCES[:start_idx]
    print(f"Will try sources in order: {ordered_sources}")
    last_cats = state.get("last_categories", [])

    best_overall = None
    best_score = -999
    best_cat = ""
    best_source_idx = start_idx

    for idx, source_name in enumerate(ordered_sources):
        jobs = FETCHERS[source_name]()
        random.shuffle(jobs)
        for job in jobs:
            reason = reject_reason(job, posted)
            if reason:
                continue
            cat = get_category(job["title"])
            if any(is_similar(cat, old) for old in last_cats):
                continue
            who, score = analyze_job(job)
            if score > best_score:
                best_score = score
                best_overall = (job, who)
                best_cat = cat
                best_source_idx = SOURCES.index(source_name)
        # If we found a good job from this source, stop - we don't need to check other sources
        if best_overall and best_score >= 10:
            print(f"Found good job from {source_name}, stopping search")
            break
        # If we found any job, but not perfect, keep it as backup and try next source for better one
        print(f"After {source_name}: best so far = {best_overall[0]['title'] if best_overall else 'None'} score={best_score}")

    if not best_overall:
        # LAST RESORT: Allow any open job even if category repeats, but NEVER repeat URL and NEVER scam
        print("No job with new category found, trying fallback - any open job")
        for source_name in ordered_sources:
            jobs = FETCHERS[source_name]()
            for job in jobs:
                if reject_reason(job, posted):
                    continue
                who, score = analyze_job(job)
                best_overall = (job, who)
                best_cat = get_category(job["title"])
                best_source_idx = SOURCES.index(source_name)
                break
            if best_overall:
                break

    if not best_overall:
        print("CRITICAL: No open job found from ANY source. Check if APIs are down.")
        return

    job, who = best_overall
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
        posted.add(job["url"])
        last_cats.append(best_cat)
        state["last_categories"] = last_cats[-15:]
        state["last_source"] = best_source_idx
        save_json("state.json", state)
        save_json("posted.json", list(posted))
        print(f"SUCCESS: Posted {best_cat} from {job['source']}")
    else:
        print("FAILED: Not saving, will retry next run")

if __name__ == "__main__":
    main()
