# ============================================================
# WorldwideHiringBot - FINAL VERSION - RENDER FREE WEB SERVICE
# Channel: @RemoteJobsHiringNow | Admin: @dantez4u
# Bot: @WorldwideHiringBot
# Features: Services Stars, Bundles, Daily Ad, Jobs Poster,
# Scam Check 15 Stars / FREE 1x per 15 days with Share-to-5,
# Posting via Admin ONLY, Permanent Memory SQLite
# Deploy: Render Free Web Service - Start: python bot.py
# ============================================================

import os
import sqlite3
import html
import random
import logging
import time
import asyncio
from datetime import datetime, timezone, timedelta
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "PASTE_YOUR_BOT_TOKEN_HERE")
ADMIN_ID_ENV = int(os.getenv("ADMIN_ID", "0") or 0)
ADMIN_USERNAME = "dantez4u"
CHANNEL_ID = "@RemoteJobsHiringNow"
CHANNEL_LINK = "https://t.me/RemoteJobsHiringNow"
GROUP_LINK = "https://t.me/RemoteJobsDiscussion"
DB_FILE = "bot_memory.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Anti-spam: user_id -> last message timestamp
_last_msg: dict = {}

SCAM_PRICE = 15
FREE_COOLDOWN_DAYS = 15

SERVICES = {
    "cv": {"name": "ATS CV Rewrite", "price": 385, "desc": "ATS CV rewritten for remote jobs worldwide. Send your old CV."},
    "cover": {"name": "Cover Letter", "price": 231, "desc": "Tailored cover letter for 1 job. Send job link."},
    "linkedin": {"name": "LinkedIn Optimization", "price": 385, "desc": "Headline + About + Experience optimized for recruiters."},
    "interview": {"name": "Interview Prep", "price": 385, "desc": "30 min prep + 20 likely questions + answers."},
    "roadmap": {"name": "Career Roadmap", "price": 616, "desc": "90-day plan to get remote job."},
    "salary": {"name": "Salary Negotiation", "price": 308, "desc": "Script + numbers to negotiate your offer."},
    "scam": {"name": "Scam Check", "price": 15, "desc": "We check if a job / company is scam. 15 Stars, or FREE 1x every 15 days if you share channel to 5 people."},
}

BUNDLES = {
    "starter": {"name": "STARTER Bundle", "price": 539, "desc": "CV + Cover Letter. Save 77 Stars."},
    "gethired": {"name": "GET HIRED - Best Seller", "price": 1154, "desc": "CV + Cover + LinkedIn + Interview Prep. Save 231 Stars."},
    "allin": {"name": "ALL-IN Bundle", "price": 1847, "desc": "Everything: CV + Cover + LinkedIn + Interview + Roadmap + Salary."},
    "freelancer": {"name": "FREELANCER Bundle", "price": 1000, "desc": "CV + LinkedIn + Roadmap for freelancers."},
}

# ---------------- KEEP-ALIVE FOR RENDER FREE WEB SERVICE ----------------
# Render Web Service Free needs an open HTTP port, otherwise it thinks bot crashed.
# This tiny server answers "Bot is alive!" - it does NOT affect Telegram bot.
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive! WorldwideHiringBot running.")
    def log_message(self, format, *args):
        pass

def run_keep_alive():
    port = int(os.getenv("PORT", "10000"))
    try:
        logger.info(f"Keep-alive web server on port {port}")
        HTTPServer(("0.0.0.0", port), KeepAliveHandler).serve_forever()
    except Exception as e:
        logger.error(f"Keep alive error: {e}")

# ---------------- DATABASE ----------------
def db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    c = db()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        first_seen TEXT, last_seen TEXT,
        total_orders INTEGER DEFAULT 0, total_stars INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        role TEXT, message TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        item TEXT, price INTEGER, status TEXT, created_at TEXT, payload TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS posted_jobs (
        job_id TEXT PRIMARY KEY, posted_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS scam_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
        text TEXT, result TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS daily_stats (
        date TEXT PRIMARY KEY, ad_posted INTEGER DEFAULT 0, posted_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    # Scam FREE system
    c.execute("""CREATE TABLE IF NOT EXISTS scam_free (
        user_id INTEGER PRIMARY KEY, last_free_at TEXT,
        last_proof_status TEXT, free_count INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS scam_free_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        proof_text TEXT, status TEXT DEFAULT 'PENDING', created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS scam_credits (
        user_id INTEGER PRIMARY KEY, credits INTEGER DEFAULT 0)""")
    c.commit()
    c.close()

def save_user(user):
    try:
        c = db()
        now = datetime.now(timezone.utc).isoformat()
        c.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, first_seen, last_seen) VALUES (?,?,?,?,?)",
            (user.id, user.username or "", user.first_name or "", now, now),
        )
        c.execute(
            "UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
            (user.username or "", user.first_name or "", now, user.id),
        )
        if user.username == ADMIN_USERNAME:
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_id', ?)", (str(user.id),))
        c.commit()
        c.close()
    except Exception as e:
        logger.error(f"save_user: {e}")

def get_admin_id() -> int:
    if ADMIN_ID_ENV and ADMIN_ID_ENV != 0:
        return ADMIN_ID_ENV
    try:
        c = db()
        r = c.execute("SELECT value FROM settings WHERE key='admin_id'").fetchone()
        c.close()
        if r:
            return int(r[0])
    except Exception:
        pass
    return 0

def is_admin(user) -> bool:
    if not user:
        return False
    aid = get_admin_id()
    if aid and user.id == aid:
        return True
    if not aid and user.username == ADMIN_USERNAME:
        return True
    return False

async def notify_admin(context, text: str) -> bool:
    aid = get_admin_id()
    if not aid:
        logger.warning("Admin ID not saved yet. Admin must /start bot first.")
        return False
    try:
        await context.bot.send_message(chat_id=aid, text=text)
        return True
    except Exception as e:
        logger.error(f"notify_admin failed: {e}")
        return False

def save_chat(user_id, username, role, message):
    if not message:
        return
    try:
        c = db()
        c.execute(
            "INSERT INTO chats (user_id, username, role, message, created_at) VALUES (?,?,?,?,?)",
            (user_id, username or "", role, message[:2000], datetime.now(timezone.utc).isoformat()),
        )
        c.commit()
        c.close()
    except Exception as e:
        logger.error(f"save_chat: {e}")

def is_posted(job_id: str) -> bool:
    try:
        c = db()
        r = c.execute("SELECT 1 FROM posted_jobs WHERE job_id=?", (job_id,)).fetchone()
        c.close()
        return bool(r)
    except Exception:
        return False

def mark_posted(job_id: str):
    try:
        c = db()
        c.execute("INSERT OR IGNORE INTO posted_jobs VALUES (?,?)", (job_id, datetime.now(timezone.utc).isoformat()))
        c.commit()
        c.close()
    except Exception as e:
        logger.error(f"mark_posted: {e}")

def clear_user_state(context):
    context.user_data.pop("awaiting_scam", None)
    context.user_data.pop("awaiting_scam_proof", None)
    context.user_data.pop("awaiting_details", None)
    context.user_data.pop("scam_paid", None)

# ---------------- SCAM FREE HELPERS ----------------
def can_claim_free(user_id: int):
    try:
        c = db()
        row = c.execute("SELECT last_free_at FROM scam_free WHERE user_id=?", (user_id,)).fetchone()
        c.close()
        if not row or not row[0]:
            return True, 0
        last = datetime.fromisoformat(row[0])
        days_passed = (datetime.now(timezone.utc) - last).days
        if days_passed >= FREE_COOLDOWN_DAYS:
            return True, 0
        return False, FREE_COOLDOWN_DAYS - days_passed
    except Exception:
        return True, 0

def get_credits(user_id: int) -> int:
    try:
        c = db()
        r = c.execute("SELECT credits FROM scam_credits WHERE user_id=?", (user_id,)).fetchone()
        c.close()
        return r[0] if r else 0
    except Exception:
        return 0

def add_credit(user_id: int):
    try:
        c = db()
        c.execute("INSERT OR IGNORE INTO scam_credits (user_id, credits) VALUES (?,0)", (user_id,))
        c.execute("UPDATE scam_credits SET credits=credits+1 WHERE user_id=?", (user_id,))
        c.commit()
        c.close()
    except Exception as e:
        logger.error(f"add_credit: {e}")

def use_credit(user_id: int):
    try:
        c = db()
        c.execute("UPDATE scam_credits SET credits=credits-1 WHERE user_id=? AND credits>0", (user_id,))
        c.commit()
        c.close()
    except Exception as e:
        logger.error(f"use_credit: {e}")

# ---------------- KEYBOARDS ----------------
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💼 Services - Pay with Stars", callback_data="services")],
        [InlineKeyboardButton("📦 Bundles - Save Stars", callback_data="bundles")],
        [InlineKeyboardButton("⭐ Get Your Thing Posted - Contact Admin", callback_data="post_my_thing")],
        [InlineKeyboardButton("🛡️ Scam Check - 15⭐ or FREE", callback_data="scamcheck")],
        [InlineKeyboardButton("📺 Channel", url=CHANNEL_LINK), InlineKeyboardButton("💬 Discussion", url=GROUP_LINK)],
        [InlineKeyboardButton("👨‍💼 Talk to Admin @dantez4u", url="https://t.me/dantez4u")],
    ])

def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu")],
    ])

def scam_menu_kb(user_id: int):
    credits = get_credits(user_id)
    can_free, wait_days = can_claim_free(user_id)
    if credits > 0:
        free_text = f"✅ You have {credits} FREE credit."
    elif can_free:
        free_text = "🎁 You CAN claim FREE now."
    else:
        free_text = f"⏳ FREE in {wait_days} days left."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐ Pay {SCAM_PRICE} Stars - Instant", callback_data="scam_pay")],
        [InlineKeyboardButton("🎁 Claim FREE - Share to 5 People", callback_data="scam_free_claim")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu")],
    ])
    return free_text, kb

# ---------------- BASIC HANDLERS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    clear_user_state(context)
    save_chat(user.id, user.username, "user", "/start")
    text = (
        f"👋 Hi {html.escape(user.first_name or 'there')}!\n\n"
        "🌍 <b>Remote Jobs Worldwide Only. No US-only.</b>\n"
        "Jobs posted several times a day in @RemoteJobsHiringNow - FREE\n\n"
        "💼 <b>Services - Stars ONLY:</b>\n"
        "CV 385⭐ | Cover 231⭐ | LinkedIn 385⭐\n"
        "Interview 385⭐ | Roadmap 616⭐ | Salary 308⭐\n"
        f"Scam Check {SCAM_PRICE}⭐ or FREE 1x / 15 days - Share to 5\n\n"
        "⭐ <b>Want YOUR thing posted?</b>\n"
        "Freelancer skill, Job Seeker, Hiring - Contact Admin @dantez4u to post it in channel.\n\n"
        "📦 Bundles: 539 / 1154 / 1847 / 1000\n\n"
        "⚠️ <b>Never pay to get a job.</b> I remember you - chats & orders saved."
    )
    await update.message.reply_text(text, reply_markup=main_kb(), parse_mode=ParseMode.HTML)
    save_chat(user.id, user.username, "bot", text)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_user_state(context)
    if update.callback_query:
        q = update.callback_query
        await q.answer("Cancelled")
        await q.edit_message_text("❌ Cancelled. Back to menu:", reply_markup=main_kb())
    else:
        await update.message.reply_text("❌ Cancelled. Back to menu:", reply_markup=main_kb())

async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    clear_user_state(context)
    await q.edit_message_text("🌍 <b>Main Menu - Worldwide Hiring</b>\nChoose below:", reply_markup=main_kb(), parse_mode=ParseMode.HTML)

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    btns = [[InlineKeyboardButton(f"{s['name']} - {s['price']}⭐", callback_data=f"buy:{k}")] for k, s in SERVICES.items()]
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="menu")])
    await q.edit_message_text(
        "💼 <b>Services - Stars ONLY</b>\nTap a service to see details & pay:",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.HTML,
    )

async def show_bundles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    btns = [[InlineKeyboardButton(f"{s['name']} - {s['price']}⭐", callback_data=f"bundle:{k}")] for k, s in BUNDLES.items()]
    btns.append([InlineKeyboardButton("⬅️ Back", callback_data="menu")])
    await q.edit_message_text(
        "📦 <b>Bundles - Save Stars</b>\nTap a bundle to see details & pay:",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.HTML,
    )

async def post_my_thing_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "⭐ <b>Want YOUR Thing Posted In Channel?</b>\n\n"
        "We post for:\n"
        "💼 <b>Freelancers</b> - Your skill / service\n"
        "🔍 <b>Job Seekers</b> - You looking for a job\n"
        "📢 <b>Hiring People / Companies</b> - You hiring someone\n\n"
        "<b>How it works - ONLY via Admin:</b>\n"
        "1. DM Admin @dantez4u\n"
        "2. Tell him what you want posted\n"
        "3. Pay as he tells you (TRC20 / Wise / Stars)\n"
        "4. Admin posts it to @RemoteJobsHiringNow\n\n"
        "⚠️ No free ads in group. Only paid posts via Admin get posted.\n"
        "⚠️ Never pay to get a job - this is only if YOU want to advertise.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("👨‍💼 DM Admin @dantez4u Now", url="https://t.me/dantez4u")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu")],
        ]),
        parse_mode=ParseMode.HTML,
    )

async def detail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        _, kind, key = q.data.split(":")
    except ValueError:
        await q.edit_message_text("Error. Go back to menu.", reply_markup=main_kb())
        return
    item = SERVICES.get(key) if kind == "buy" else BUNDLES.get(key) if kind == "bundle" else None
    if not item:
        await q.edit_message_text("Service not found.", reply_markup=main_kb())
        return
    text = f"<b>{item['name']} - {item['price']}⭐</b>\n\n{item['desc']}\n\nPay with Stars below. After payment, send your details here. Admin @dantez4u will deliver."
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⭐ Pay {item['price']} Stars", callback_data=f"pay:{kind}:{key}")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu")],
    ])
    await q.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def pay_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        _, kind, key = q.data.split(":")
    except ValueError:
        return
    if kind == "buy":
        item = SERVICES.get(key)
    elif kind == "bundle":
        item = BUNDLES.get(key)
    else:
        item = None
    if not item:
        await q.message.reply_text("Service not found.")
        return
    payload = f"{kind}:{key}:{q.from_user.id}"
    try:
        await context.bot.send_invoice(
            chat_id=q.from_user.id,
            title=item["name"],
            description=item["desc"][:255],
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(item["name"], item["price"])],
        )
        await q.message.reply_text("⭐ Invoice sent above. Tap Pay to pay with Stars.")
    except Exception as e:
        logger.error(f"invoice: {e}")
        await q.message.reply_text("⚠️ Could not create invoice. Stars payments may not be enabled. Contact @dantez4u. Go to @BotFather > Payments > Enable Stars.")

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pay = update.message.successful_payment
    user = update.effective_user
    save_user(user)
    try:
        c = db()
        c.execute(
            "INSERT INTO orders (user_id, username, item, price, status, created_at, payload) VALUES (?,?,?,?,?,?,?)",
            (user.id, user.username or "", pay.invoice_payload, pay.total_amount, "PAID", datetime.now(timezone.utc).isoformat(), pay.invoice_payload),
        )
        c.execute(
            "UPDATE users SET total_orders=total_orders+1, total_stars=total_stars+? WHERE user_id=?",
            (pay.total_amount, user.id),
        )
        c.commit()
        c.close()
    except Exception as e:
        logger.error(f"success db: {e}")
    save_chat(user.id, user.username, "user", f"PAID {pay.total_amount} Stars for {pay.invoice_payload}")

    if "scam" in pay.invoice_payload:
        context.user_data["awaiting_scam"] = True
        context.user_data["scam_paid"] = True
        await update.message.reply_text(
            f"✅ Paid {pay.total_amount}⭐ for Scam Check.\n\nNow send the job link / company name. This check is paid, instant.",
            reply_markup=back_kb(),
        )
    else:
        context.user_data["awaiting_details"] = pay.invoice_payload
        await update.message.reply_text(
            f"✅ Payment received: {pay.total_amount}⭐ for {pay.invoice_payload}\n\nPlease send your details now (CV / job link / etc). Admin @dantez4u will deliver.",
            reply_markup=back_kb(),
        )
    await notify_admin(context, f"💰 NEW ORDER\nUser: @{user.username} ({user.id})\nItem: {pay.invoice_payload}\nAmount: {pay.total_amount}⭐")

# ---------------- SCAM CHECK ----------------
async def scamcheck_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    free_text, kb = scam_menu_kb(update.effective_user.id)
    await update.message.reply_text(
        f"🛡️ <b>Scam Check - Only {SCAM_PRICE}⭐</b>\n\n{free_text}\n\n"
        "<b>2 Ways:</b>\n"
        f"1. <b>Pay {SCAM_PRICE}⭐</b> - Instant, use daily, no sharing\n"
        f"2. <b>FREE 1x every {FREE_COOLDOWN_DAYS} days</b> - Share @RemoteJobsHiringNow to 5 people/groups, send proof, Admin approves, you get 1 FREE check\n\n"
        "❌ Scam if: Asks you to pay to get job, asks bank / OTP, salary too high, Gmail / WhatsApp only.\n\nChoose:",
        reply_markup=kb, parse_mode=ParseMode.HTML,
    )

async def scamcheck_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    free_text, kb = scam_menu_kb(q.from_user.id)
    await q.edit_message_text(
        f"🛡️ <b>Scam Check - Only {SCAM_PRICE}⭐</b>\n\n{free_text}\n\n"
        "<b>2 Ways:</b>\n"
        f"1. Pay {SCAM_PRICE}⭐ - Instant, daily\n"
        f"2. FREE 1x / {FREE_COOLDOWN_DAYS} days - Share to 5 people, send proof, Admin approves\n\nChoose:",
        reply_markup=kb, parse_mode=ParseMode.HTML,
    )

async def scam_pay_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    try:
        await context.bot.send_invoice(
            chat_id=q.from_user.id,
            title="Scam Check",
            description="1 Scam Check - Check if job is scam",
            payload=f"buy:scam:{q.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice("Scam Check", SCAM_PRICE)],
        )
        await q.message.reply_text(f"⭐ Invoice for {SCAM_PRICE}⭐ sent above. Pay, then send the job link.")
    except Exception as e:
        logger.error(f"scam invoice: {e}")
        await q.message.reply_text("⚠️ Could not create invoice. Contact @dantez4u.")

async def scam_free_claim_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    if get_credits(user.id) > 0:
        context.user_data["awaiting_scam"] = True
        context.user_data["scam_paid"] = False
        await q.edit_message_text(
            "✅ You have a FREE credit! Send the job link / company now - this check is FREE.",
            reply_markup=back_kb(), parse_mode=ParseMode.HTML,
        )
        return
    can_free, wait_days = can_claim_free(user.id)
    if not can_free:
        await q.edit_message_text(
            f"⏳ <b>Not Yet - Wait {wait_days} More Days</b>\n\nYou already got FREE Scam Check in last {FREE_COOLDOWN_DAYS} days.\n\nYou can still check today by paying {SCAM_PRICE}⭐ - very cheap.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"⭐ Pay {SCAM_PRICE} Stars Now", callback_data="scam_pay")],
                [InlineKeyboardButton("⬅️ Back", callback_data="menu")],
            ]),
            parse_mode=ParseMode.HTML,
        )
        return
    context.user_data["awaiting_scam_proof"] = True
    await q.edit_message_text(
        "🎁 <b>Claim FREE Scam Check - Share To 5</b>\n\n"
        "<b>Do this:</b>\n"
        "1. Open @RemoteJobsHiringNow\n"
        "2. Forward / Share any 5 job posts to 5 different people OR groups\n"
        "3. Take 5 screenshots of your shares\n"
        "4. Send the 5 screenshots HERE (or send text: 'Shared to: @name1, @name2...')\n\n"
        "Admin @dantez4u will check & approve. Then you get 1 FREE Scam Check.\n"
        "⚠️ Fake proof = No free. Be honest.\n\n"
        "Send your 5 proofs now:",
        reply_markup=back_kb(), parse_mode=ParseMode.HTML,
    )

async def approve_free_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_admin(q.from_user):
        await q.answer("Admin only", show_alert=True)
        return
    await q.answer()
    try:
        _, rid = q.data.split(":")
        rid = int(rid)
    except ValueError:
        return
    c = db()
    row = c.execute("SELECT user_id, username FROM scam_free_requests WHERE id=?", (rid,)).fetchone()
    if not row:
        await q.edit_message_text("Already handled.")
        c.close()
        return
    user_id, username = row
    c.execute("UPDATE scam_free_requests SET status='APPROVED' WHERE id=?", (rid,))
    c.execute(
        "INSERT OR REPLACE INTO scam_free (user_id, last_free_at, last_proof_status, free_count) VALUES (?,?,?, COALESCE((SELECT free_count FROM scam_free WHERE user_id=?),0)+1)",
        (user_id, datetime.now(timezone.utc).isoformat(), "APPROVED", user_id),
    )
    c.commit()
    c.close()
    add_credit(user_id)
    await q.edit_message_text(f"✅ Approved FREE for @{username} - 1 credit added.")
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 Approved! You shared to 5 people - you got 1 FREE Scam Check!\n\nTap below to use it:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛡️ Use FREE Scam Check Now", callback_data="scamcheck")]]),
        )
    except Exception:
        pass

async def reject_free_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_admin(q.from_user):
        await q.answer("Admin only", show_alert=True)
        return
    await q.answer()
    try:
        _, rid = q.data.split(":")
        rid = int(rid)
    except ValueError:
        return
    c = db()
    row = c.execute("SELECT user_id, username FROM scam_free_requests WHERE id=?", (rid,)).fetchone()
    if not row:
        await q.edit_message_text("Already handled.")
        c.close()
        return
    user_id, username = row
    c.execute("UPDATE scam_free_requests SET status='REJECTED' WHERE id=?", (rid,))
    c.commit()
    c.close()
    await q.edit_message_text(f"❌ Rejected FREE for @{username}")
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ Your FREE proof was not approved. Share to 5 real people/groups and try again, or pay {SCAM_PRICE}⭐ for instant check.",
        )
    except Exception:
        pass

def run_scam_check(text: str) -> str:
    low = text.lower()
    flags = []
    if any(w in low for w in ["pay", "fee", "deposit", "activation", "training fee"]):
        flags.append("Asks for money")
    if any(w in low for w in ["whatsapp only", "gmail", "dm me", "telegram only"]):
        flags.append("Unofficial contact")
    if any(w in low for w in ["crypto", "wallet", "otp", "pin", "bank details"]):
        flags.append("Asks sensitive info")
    if any(w in low for w in ["no interview", "instant job", "guaranteed"]):
        flags.append("Too good / urgent")
    if flags:
        return f"⚠️ HIGH RISK - Possible SCAM. Flags: {', '.join(flags)}. DO NOT PAY. Forward to @dantez4u."
    return "✅ Looks OK on basic check, but still be careful: Never pay to get a job. Verify company website + LinkedIn. If unsure, forward to @dantez4u."

# ---------------- TEXT & PHOTO HANDLERS ----------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    text = (update.message.text or "").strip()
    if not text:
        return
    now = time.time()
    if user.id in _last_msg and now - _last_msg[user.id] < 2:
        return
    _last_msg[user.id] = now
    save_chat(user.id, user.username, "user", text)

    if context.user_data.get("awaiting_scam_proof"):
        try:
            c = db()
            cur = c.execute(
                "INSERT INTO scam_free_requests (user_id, username, proof_text, status, created_at) VALUES (?,?,?,?,?)",
                (user.id, user.username or "", text, "PENDING", datetime.now(timezone.utc).isoformat()),
            )
            rid = cur.lastrowid
            c.commit()
            c.close()
        except Exception as e:
            logger.error(f"proof save: {e}")
            return
        context.user_data["awaiting_scam_proof"] = False
        await update.message.reply_text(
            "✅ Proof received! Sent to Admin @dantez4u for review. You will get a message when approved. Thank you for sharing!",
            reply_markup=main_kb(),
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve FREE", callback_data=f"approve_free:{rid}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"reject_free:{rid}")]
        ])
        await notify_admin(context, f"🎁 FREE SCAM CLAIM #{rid}\nUser: @{user.username} ({user.id})\nProof: {text[:500]}\n\nCheck proof. Approve?")
        aid = get_admin_id()
        if aid:
            try:
                await context.bot.send_message(chat_id=aid, text=f"Approve FREE #{rid}?", reply_markup=kb)
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_scam"):
        context.user_data["awaiting_scam"] = False
        was_paid = context.user_data.get("scam_paid")
        context.user_data.pop("scam_paid", None)
        if not was_paid and get_credits(user.id) > 0:
            use_credit(user.id)
        result = run_scam_check(text)
        try:
            c = db()
            c.execute(
                "INSERT INTO scam_checks (user_id, text, result, created_at) VALUES (?,?,?,?)",
                (user.id, text, result, datetime.now(timezone.utc).isoformat()),
            )
            c.commit()
            c.close()
        except Exception as e:
            logger.error(f"scam save: {e}")
        await update.message.reply_text(result, reply_markup=main_kb())
        save_chat(user.id, user.username, "bot", result)
        return

    if context.user_data.get("awaiting_details"):
        item = context.user_data.pop("awaiting_details")
        await update.message.reply_text(
            f"✅ Details received for {item}. Saved. Admin @dantez4u will deliver. Thank you!",
            reply_markup=main_kb(),
        )
        await notify_admin(context, f"📄 DETAILS from @{user.username} ({user.id}) for {item}:\n{text[:1000]}")
        save_chat(user.id, user.username, "bot", "Details received")
        return

    await update.message.reply_text(
        "Got it ✅ Saved. Admin @dantez4u will reply.\nUse /start for menu, /cancel to stop.",
        reply_markup=main_kb(),
    )

async def handle_photo_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)
    if not context.user_data.get("awaiting_scam_proof"):
        await update.message.reply_text(
            "Got photo ✅. If you want FREE Scam Check, tap Scam Check > Claim FREE first.",
            reply_markup=main_kb(),
        )
        return
    try:
        c = db()
        cur = c.execute(
            "INSERT INTO scam_free_requests (user_id, username, proof_text, status, created_at) VALUES (?,?,?,?,?)",
            (user.id, user.username or "", "Sent photo proof - see forwarded photo to admin", "PENDING", datetime.now(timezone.utc).isoformat()),
        )
        rid = cur.lastrowid
        c.commit()
        c.close()
    except Exception as e:
        logger.error(f"photo proof save: {e}")
        return
    context.user_data["awaiting_scam_proof"] = False
    await update.message.reply_text("✅ Photo proof received! Sent to Admin for review.", reply_markup=main_kb())
    aid = get_admin_id()
    if aid:
        try:
            await context.bot.send_photo(
                chat_id=aid,
                photo=update.message.photo[-1].file_id,
                caption=f"🎁 FREE CLAIM #{rid} from @{user.username} ({user.id})",
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Approve FREE", callback_data=f"approve_free:{rid}"),
                 InlineKeyboardButton("❌ Reject", callback_data=f"reject_free:{rid}")]
            ])
            await context.bot.send_message(chat_id=aid, text=f"Approve FREE #{rid}?", reply_markup=kb)
        except Exception as e:
            logger.error(f"forward photo: {e}")

async def myorders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        c = db()
        rows = c.execute(
            "SELECT item, price, status, created_at FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10",
            (update.effective_user.id,),
        ).fetchall()
        c.close()
    except Exception as e:
        logger.error(f"myorders: {e}")
        rows = []
    if not rows:
        await update.message.reply_text("No orders yet. Use /start.")
        return
    txt = "🧾 <b>Your Orders:</b>\n\n" + "\n".join([f"• {r[0]} - {r[1]}⭐ - {r[2]} - {r[3][:10]}" for r in rows])
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("Admin only.")
        return
    try:
        c = db()
        users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        chats = c.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
        c.close()
    except Exception:
        users = orders = chats = 0
    channel_ok = "Unknown"
    try:
        msg = await context.bot.send_message(chat_id=CHANNEL_ID, text="🔧 Status check - bot is alive. Delete this.")
        channel_ok = "✅ Bot CAN post to channel"
        try:
            await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=msg.message_id)
        except Exception:
            pass
    except Exception as e:
        channel_ok = f"❌ Bot CANNOT post to channel: {e}\nMake bot Admin in @RemoteJobsHiringNow"
    await update.message.reply_text(
        f"📊 <b>Bot Status</b>\nUsers: {users}\nOrders: {orders}\nChats saved: {chats}\nAdmin ID saved: {get_admin_id()}\nChannel: {channel_ok}",
        parse_mode=ParseMode.HTML,
    )

# ---------------- AUTO POSTER ----------------
async def fetch_jobs():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://remoteok.com/api?tag=remote", headers={"User-Agent": "Mozilla/5.0"}, timeout=20) as r:
                data = await r.json()
                jobs = [j for j in data if isinstance(j, dict) and j.get("position")]
                clean = []
                for j in jobs:
                    loc = (j.get("location") or "").lower()
                    if "us only" in loc or "united states only" in loc:
                        continue
                    clean.append(j)
                random.shuffle(clean)
                return clean[:5]
    except Exception as e:
        logger.error(f"fetch_jobs: {e}")
        return []

async def post_jobs_job(context: ContextTypes.DEFAULT_TYPE):
    jobs = await fetch_jobs()
    for j in jobs:
        jid = str(j.get("id") or j.get("slug"))
        if not jid or is_posted(jid):
            continue
        title = html.escape(j.get("position", "Remote Job"))
        company = html.escape(j.get("company", "Company"))
        loc = html.escape(j.get("location") or "Remote Worldwide")
        tags = ", ".join(j.get("tags", [])[:4])
        salary = f"{j.get('salary_min', '')} - {j.get('salary_max', '')}" if j.get("salary_min") else "See link"
        url = j.get("url") or j.get("apply_url") or "https://remoteok.com"
        text = (
            f"🌍 <b>{title}</b>\n🏢 {company} | 📍 {loc}\n💰 {salary}\n🏷️ {tags}\n\n"
            "✅ Remote Worldwide | No US-only\n"
            "⚠️ Never pay to get a job. Use /scamcheck in bot.\n\n"
            f"👉 Apply: {url}\n🤖 Bot: @WorldwideHiringBot | Admin: @dantez4u"
        )
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)
            mark_posted(jid)
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"post_jobs: {e}")

async def daily_ad_job(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        c = db()
        row = c.execute("SELECT ad_posted FROM daily_stats WHERE date=?", (today,)).fetchone()
        if row and row[0] >= 1:
            c.close()
            logger.info(f"Daily ad already posted {today}, skipping")
            return
        c.execute(
            "INSERT OR REPLACE INTO daily_stats (date, ad_posted, posted_at) VALUES (?,?,?)",
            (today, 1, datetime.now(timezone.utc).isoformat()),
        )
        c.commit()
        c.close()
    except Exception as e:
        logger.error(f"daily_ad db: {e}")

    ads = [
        f"🚀 <b>Want Remote Work? We Build Your CV To Get It.</b>\n\n"
        f"💼 ATS CV 385⭐ | Cover 231⭐ | LinkedIn 385⭐\n"
        f"📦 GET HIRED Bundle 1154⭐ - Save 231⭐\n"
        f"🛡️ Scam Check {SCAM_PRICE}⭐ or FREE 1x / 15 days if you share to 5\n\n"
        f"⭐ <b>Want YOUR Thing Posted?</b>\n"
        f"Freelancer skill, Job Seeker, or Hiring? Contact Admin @dantez4u to get your post in this channel.\n\n"
        f"🤖 Start: @WorldwideHiringBot\n👨‍💼 Admin: @dantez4u\n⚠️ Never pay to get a job.",
        "🌍 <b>Freelancer? Job Seeker? Hiring Someone?</b>\n\n"
        "⭐ <b>Get Posted In This Channel!</b>\n"
        "If you want your skill, your job search, or your hiring post published here, DM Admin @dantez4u. He will tell you payment & post it for you.\n\n"
        "💼 Need CV? CV 385⭐ - ATS ready\n"
        f"🛡️ Scam Check {SCAM_PRICE}⭐ or FREE 1x / 15 days - Share to 5\n\n"
        "🤖 Bot: @WorldwideHiringBot | Admin: @dantez4u",
        f"🛡️ <b>Got a Job Offer? Check If It's Scam - {SCAM_PRICE}⭐ or FREE</b>\n\n"
        "Send job to @WorldwideHiringBot > Scam Check\n"
        "Share channel to 5 people = 1 FREE check every 15 days.\n\n"
        "💼 While you wait, upgrade your CV 385⭐\n"
        "⭐ Want to advertise yourself? Freelancer / Job Seeker / Hiring - DM Admin @dantez4u to get posted.\n\n"
        "👨‍💼 Admin: @dantez4u | Never pay to get a job.",
    ]
    text = random.choice(ads)
    try:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"daily_ad send: {e}")

async def post_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("Admin only.")
        return
    await post_jobs_job(context)
    await update.message.reply_text("✅ Posted jobs (new ones only).")

async def ad_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user):
        await update.message.reply_text("Admin only.")
        return
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        c = db()
        c.execute("DELETE FROM daily_stats WHERE date=?", (today,))
        c.commit()
        c.close()
    except Exception:
        pass
    await daily_ad_job(context)
    await update.message.reply_text("✅ Daily Ad Posted (forced test).")

# ---------------- MAIN - FIXED FOR PYTHON 3.14 ----------------
def main():
    # FIX for Python 3.14 - create event loop manually, otherwise run_polling crashes
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
    except Exception:
        pass
    init_db()
    # Start keep-alive FIRST - Render needs port open immediately
    Thread(target=run_keep_alive, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CommandHandler("myorders", myorders))
    app.add_handler(CommandHandler("scamcheck", scamcheck_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("postnow", post_now))
    app.add_handler(CommandHandler("adnow", ad_now))

    app.add_handler(CallbackQueryHandler(cancel_cmd, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(menu_cb, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(show_services, pattern="^services$"))
    app.add_handler(CallbackQueryHandler(show_bundles, pattern="^bundles$"))
    app.add_handler(CallbackQueryHandler(post_my_thing_cb, pattern="^post_my_thing$"))
    app.add_handler(CallbackQueryHandler(scamcheck_cb, pattern="^scamcheck$"))
    app.add_handler(CallbackQueryHandler(scam_pay_cb, pattern="^scam_pay$"))
    app.add_handler(CallbackQueryHandler(scam_free_claim_cb, pattern="^scam_free_claim$"))
    app.add_handler(CallbackQueryHandler(approve_free_cb, pattern="^approve_free:"))
    app.add_handler(CallbackQueryHandler(reject_free_cb, pattern="^reject_free:"))
    app.add_handler(CallbackQueryHandler(detail_cb, pattern="^(buy|bundle):"))
    app.add_handler(CallbackQueryHandler(pay_cb, pattern="^pay:"))

    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_proof))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    jq = app.job_queue
    jq.run_repeating(post_jobs_job, interval=timedelta(hours=4), first=10)
    jq.run_repeating(daily_ad_job, interval=timedelta(hours=24), first=60)

    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
