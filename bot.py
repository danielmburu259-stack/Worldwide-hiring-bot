import os, sqlite3, json, asyncio, html, random, logging, re
from datetime import datetime, timezone, timedelta
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, PreCheckoutQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

# ============ CONFIG ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
ADMIN_USERNAME = "dantez4u"
CHANNEL_ID = "@RemoteJobsHiringNow"
CHANNEL_LINK = "https://t.me/RemoteJobsHiringNow"
GROUP_LINK = "https://t.me/RemoteJobsDiscussion"
DB_FILE = "bot_memory.db"

logging.basicConfig(level=logging.INFO)

# Prices in Stars (XTR) - FEE ON BUYER, you get full amount
SERVICES = {
    "cv": {"name": "ATS CV Rewrite", "price": 385, "desc": "ATS CV rewritten for remote jobs worldwide. Send your old CV."},
    "cover": {"name": "Cover Letter", "price": 231, "desc": "Tailored cover letter for 1 job. Send job link."},
    "linkedin": {"name": "LinkedIn Optimization", "price": 385, "desc": "Headline + About + Experience optimized for recruiters."},
    "interview": {"name": "Interview Prep", "price": 385, "desc": "30 min prep + 20 likely questions + answers for your role."},
    "roadmap": {"name": "Career Roadmap", "price": 616, "desc": "90-day plan to get remote job: skills, portfolio, where to apply."},
    "salary": {"name": "Salary Negotiation", "price": 308, "desc": "Script + numbers to negotiate your offer. Send offer details."},
    "scam": {"name": "Scam Check", "price": 77, "desc": "We check if a job / company is scam. FREE if you share channel to 5 people."},
}
BUNDLES = {
    "starter": {"name": "STARTER Bundle", "price": 539, "desc": "CV + Cover Letter. Save 77 Stars."},
    "gethired": {"name": "GET HIRED - Best Seller", "price": 1154, "desc": "CV + Cover + LinkedIn + Interview Prep. Save 231 Stars."},
    "allin": {"name": "ALL-IN Bundle", "price": 1847, "desc": "Everything: CV + Cover + LinkedIn + Interview + Roadmap + Salary."},
    "freelancer": {"name": "FREELANCER Bundle", "price": 1000, "desc": "CV + LinkedIn + Roadmap for freelancers."},
}

# ============ DATABASE - PERMANENT MEMORY (FREE) ============
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, first_seen TEXT, last_seen TEXT, total_orders INTEGER DEFAULT 0, total_stars INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, role TEXT, message TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, item TEXT, price INTEGER, status TEXT, created_at TEXT, payload TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS posted_jobs (job_id TEXT PRIMARY KEY, posted_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS scam_checks (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT, result TEXT, created_at TEXT)""")
    c.commit(); c.close()

def save_user(user):
    c = db(); now = datetime.now(timezone.utc).isoformat()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, first_seen, last_seen) VALUES (?,?,?,?,?)", (user.id, user.username or "", user.first_name or "", now, now))
    c.execute("UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?", (user.username or "", user.first_name or "", now, user.id))
    c.commit(); c.close()

def save_chat(user_id, username, role, message):
    if not message: return
    c = db(); c.execute("INSERT INTO chats (user_id, username, role, message, created_at) VALUES (?,?,?,?,?)", (user_id, username or "", role, message[:2000], datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()

def get_history(user_id, limit=20):
    c = db(); cur = c.execute("SELECT role, message FROM chats WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))
    rows = list(reversed(cur.fetchall())); c.close()
    return rows

def is_posted(job_id):
    c = db(); r = c.execute("SELECT 1 FROM posted_jobs WHERE job_id=?", (job_id,)).fetchone(); c.close(); return bool(r)

def mark_posted(job_id):
    c = db(); c.execute("INSERT OR IGNORE INTO posted_jobs VALUES (?,?)", (job_id, datetime.now(timezone.utc).isoformat())); c.commit(); c.close()

# ============ KEYBOARDS ============
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💼 Services - Pay with Stars", callback_data="services")],
        [InlineKeyboardButton("📦 Bundles - Save Stars", callback_data="bundles")],
        [InlineKeyboardButton("🛡️ FREE Scam Check", callback_data="scamcheck")],
        [InlineKeyboardButton("📢 Advertise / Post a Job", callback_data="ads")],
        [InlineKeyboardButton("📺 Channel", url=CHANNEL_LINK), InlineKeyboardButton("💬 Discussion", url=GROUP_LINK)],
        [InlineKeyboardButton("👨‍💼 Talk to Admin @dantez4u", url="https://t.me/dantez4u")],
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu")]])

# ============ HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; save_user(user); save_chat(user.id, user.username, "user", "/start")
    text = (
        f"👋 Hi {html.escape(user.first_name or 'there')}!\n\n"
        "🌍 <b>Remote Jobs Worldwide Only. No US-only.</b>\n"
        "Jobs posted several times a day in @RemoteJobsHiringNow - FREE\n\n"
        "💼 <b>Build Your Career - Pay with Stars ONLY:</b>\n"
        "CV 385⭐ | Cover 231⭐ | LinkedIn 385⭐\nInterview 385⭐ | Roadmap 616⭐ | Salary 308⭐\nScam Check 77⭐ or FREE\n\n"
        "📦 Bundles save Stars: 539 / 1154 / 1847 / 1000\n\n"
        "⚠️ <b>Never pay to get a job.</b> If unsure, use Scam Check.\n"
        "I remember you - your chats & orders are saved."
    )
    await update.message.reply_text(text, reply_markup=main_kb(), parse_mode=ParseMode.HTML)
    save_chat(user.id, user.username, "bot", text)

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text("🌍 <b>Main Menu - Worldwide Hiring</b>\nChoose below:", reply_markup=main_kb(), parse_mode=ParseMode.HTML)

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    btns = []
    for key, s in SERVICES.items():
        btns.append([InlineKeyboardButton(f"{s['name']} - {s['price']}⭐", callback_data=f"buy:{key}")])
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="menu")])
    await q.edit_message_text("💼 <b>Services - Stars ONLY</b>\nTap to pay with Telegram Stars:", reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.HTML)

async def show_bundles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    btns = []
    for key, s in BUNDLES.items():
        btns.append([InlineKeyboardButton(f"{s['name']} - {s['price']}⭐", callback_data=f"bundle:{key}")])
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="menu")])
    await q.edit_message_text("📦 <b>Bundles - Save Stars</b>", reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.HTML)

async def detail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, kind, key = q.data.split(":")
    item = SERVICES[key] if kind == "buy" else BUNDLES[key]
    text = f"<b>{item['name']} - {item['price']}⭐</b>\n\n{item['desc']}\n\nPay with Stars below. After payment, send your details here. Admin @dantez4u will deliver."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐ Pay {item['price']} Stars", callback_data=f"pay:{kind}:{key}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu")]
    ])
    await q.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def pay_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    _, kind, key = q.data.split(":")
    item = SERVICES[key] if kind == "pay" or kind == "buy" else BUNDLES[key]
    # Actually handle pay: format is pay:buy:key or pay:bundle:key
    # Fix parsing: q.data = pay:buy:cv -> parts = [pay, buy, cv]
    # Above split gives kind=buy, key=cv - correct
    payload = f"{kind}:{key}:{q.from_user.id}"
    await context.bot.send_invoice(
        chat_id=q.from_user.id, title=item['name'], description=item['desc'][:255],
        payload=payload, provider_token="", currency="XTR",
        prices=[LabeledPrice(item['name'], item['price'])],
    )
    await q.message.reply_text("⭐ Invoice sent above. Tap Pay to pay with Stars. No dollars, no card needed.")

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pay = update.message.successful_payment
    user = update.effective_user; save_user(user)
    c = db(); c.execute("INSERT INTO orders (user_id, username, item, price, status, created_at, payload) VALUES (?,?,?,?,?,?,?)", (user.id, user.username or "", pay.invoice_payload, pay.total_amount, "PAID", datetime.now(timezone.utc).isoformat(), pay.invoice_payload))
    c.execute("UPDATE users SET total_orders=total_orders+1, total_stars=total_stars+? WHERE user_id=?", (pay.total_amount, user.id))
    c.commit(); c.close()
    save_chat(user.id, user.username, "user", f"PAID {pay.total_amount} Stars for {pay.invoice_payload}")
    await update.message.reply_text(f"✅ Payment received: {pay.total_amount}⭐ for {pay.invoice_payload}\n\nPlease send your details now (CV / job link / etc). Admin @dantez4u will deliver. Thank you!", reply_markup=back_kb())
    # Notify admin
    try:
        await context.bot.send_message(chat_id="@dantez4u", text=f"💰 NEW ORDER\nUser: @{user.username} ({user.id})\nItem: {pay.invoice_payload}\nAmount: {pay.total_amount}⭐")
    except: pass

async def scamcheck_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "🛡️ <b>Scam Check - FREE or 77⭐</b>\n\nSend me the job link / company name / screenshot text.\n\n<b>RED FLAGS - Scam if:</b>\n❌ Asks you to pay to get job\n❌ Asks for bank / crypto wallet / OTP\n❌ Salary too high, no interview\n❌ Gmail / WhatsApp only, no website\n\nSend the job now, I will check it.",
        reply_markup=back_kb(), parse_mode=ParseMode.HTML)
    context.user_data["awaiting_scam"] = True

async def ads_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    await q.edit_message_text(
        "📢 <b>Advertise / Post a Job</b>\n\nWe do NOT show payment addresses in bot.\n\nContact Admin for TRC20 / Wise payment:\n👨‍💼 @dantez4u\n\nSend him: Job title, link, location (Remote Worldwide), salary, how to apply.\nAfter payment, your job is posted to @RemoteJobsHiringNow",
        reply_markup=back_kb(), parse_mode=ParseMode.HTML)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user; save_user(user); text = update.message.text or ""
    save_chat(user.id, user.username, "user", text)
    if context.user_data.get("awaiting_scam"):
        context.user_data["awaiting_scam"] = False
        low = text.lower()
        flags = []
        if any(w in low for w in ["pay", "fee", "deposit", "activation", "training fee", "buy", "investment"]): flags.append("Asks for money")
        if any(w in low for w in ["whatsapp only", "telegram only", "gmail", "dm me"]): flags.append("Unofficial contact")
        if any(w in low for w in ["no interview", "instant", "urgent", "guaranteed"]): flags.append("Too good / urgent")
        if any(w in low for w in ["crypto", "wallet", "bank details", "otp", "pin"]): flags.append("Asks sensitive info")
        if flags:
            result = f"⚠️ HIGH RISK - Possible SCAM. Flags: {', '.join(flags)}. DO NOT PAY. Ask admin @dantez4u."
        else:
            result = "✅ Looks OK on basic check, but still be careful: Never pay to get a job. Verify company website + LinkedIn. If unsure, forward to @dantez4u."
        c = db(); c.execute("INSERT INTO scam_checks (user_id, text, result, created_at) VALUES (?,?,?,?)", (user.id, text, result, datetime.now(timezone.utc).isoformat())); c.commit(); c.close()
        await update.message.reply_text(result, reply_markup=back_kb())
        save_chat(user.id, user.username, "bot", result)
        return
    # General chat - remember history
    hist = get_history(user.id, 5)
    await update.message.reply_text("Got it ✅ Saved. Admin @dantez4u will reply.\nUse /start to see menu, or /scamcheck to check a job.", reply_markup=main_kb())
    save_chat(user.id, user.username, "bot", "Got it - saved")

async def myorders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = db(); rows = c.execute("SELECT item, price, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (update.effective_user.id,)).fetchall(); c.close()
    if not rows:
        await update.message.reply_text("You have no orders yet. Use /start to buy.")
        return
    txt = "🧾 <b>Your Orders (I remember all):</b>\n\n" + "\n".join([f"• {r[0]} - {r[1]}⭐ - {r[2]} - {r[3][:10]}" for r in rows])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

# ============ AUTO POSTER - FREE ============
async def fetch_jobs():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://remoteok.com/api?tag=remote", headers={"User-Agent": "Mozilla/5.0"}, timeout=20) as r:
                data = await r.json()
                jobs = [j for j in data if isinstance(j, dict) and j.get("position")]
                # Filter: no US-only
                clean = []
                for j in jobs:
                    loc = (j.get("location") or "").lower()
                    if "us only" in loc or "united states only" in loc: continue
                    clean.append(j)
                random.shuffle(clean)
                return clean[:5]
    except Exception as e:
        logging.error(e); return []

async def post_jobs_job(context: ContextTypes.DEFAULT_TYPE):
    jobs = await fetch_jobs()
    for j in jobs:
        jid = str(j.get("id") or j.get("slug"))
        if is_posted(jid): continue
        title = html.escape(j.get("position","Remote Job"))
        company = html.escape(j.get("company","Company"))
        loc = html.escape(j.get("location") or "Remote Worldwide")
        tags = ", ".join(j.get("tags", [])[:4])
        salary = f"{j.get('salary_min','')} - {j.get('salary_max','')}" if j.get("salary_min") else "See link"
        url = j.get("url") or j.get("apply_url") or "https://remoteok.com"
        text = f"🌍 <b>{title}</b>\n🏢 {company} | 📍 {loc}\n💰 {salary}\n🏷️ {tags}\n\n✅ Remote Worldwide | No US-only\n⚠️ Never pay to get a job. Use /scamcheck in bot.\n\n👉 Apply: {url}\n🤖 Bot: @WorldwideHiringBot | Admin: @dantez4u"
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
            mark_posted(jid); await asyncio.sleep(2)
        except Exception as e: logging.error(e)

async def post_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.username != ADMIN_USERNAME:
        await update.message.reply_text("Admin only."); return
    await post_jobs_job(context); await update.message.reply_text("✅ Posted.")

def main():
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myorders", myorders))
    app.add_handler(CommandHandler("scamcheck", scamcheck_cb))
    app.add_handler(CommandHandler("postnow", post_now))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(show_services, pattern="^services$"))
    app.add_handler(CallbackQueryHandler(show_bundles, pattern="^bundles$"))
    app.add_handler(CallbackQueryHandler(scamcheck_cb, pattern="^scamcheck$"))
    app.add_handler(CallbackQueryHandler(ads_cb, pattern="^ads$"))
    app.add_handler(CallbackQueryHandler(detail_cb, pattern="^(buy|bundle):"))
    app.add_handler(CallbackQueryHandler(pay_cb, pattern="^pay:"))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    # Auto-poster: several times a day, free job queue
    jq = app.job_queue
    jq.run_repeating(post_jobs_job, interval=timedelta(hours=4), first=10)
    app.run_polling()

if __name__ == "__main__":
    main()
