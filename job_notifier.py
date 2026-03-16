"""
LinkedIn Job Notifier + One-Click Opener
=========================================
All settings are controlled via the .env file.
No code editing needed — just configure .env!

Usage:
  1. Copy .env.example to .env and fill in your settings
  2. pip install -r requirements.txt
  3. python job_notifier.py
"""

import os, json, time, hashlib, smtplib, logging, schedule, requests
from datetime import datetime
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("notifier.log"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)


def parse_list(val, default):
    """Parse comma-separated string into a list."""
    if not val:
        return default
    return [x.strip() for x in val.split(",") if x.strip()]

def parse_pipe_list(val, default):
    """Parse pipe-separated string into a list.
    Used for locations since city names already contain commas.
    Example: 'Bengaluru, India|Hyderabad, India|Mumbai, India'
    """
    if not val:
        return default
    return [x.strip() for x in val.split("|") if x.strip()]


# ── CONFIG — 100% driven from .env, no code changes needed ───────────────────
CONFIG = {

    # ── What jobs to search ────────────────────────────────────────────────────
    # .env: JOB_KEYWORDS=Data Engineer,Software Engineer,Data Analyst
    "keywords_list": parse_list(
        os.getenv("JOB_KEYWORDS", "Data Engineer,Software Engineer"),
        ["Data Engineer", "Software Engineer"]
    ),

    # Use pipe | to separate locations (city names already have commas)
    # .env: JOB_LOCATIONS=Bengaluru, India|Hyderabad, India|Mumbai, India|Remote
    "locations_list": parse_pipe_list(
        os.getenv("JOB_LOCATIONS", "Bengaluru, India|Hyderabad, India"),
        ["Bengaluru, India", "Hyderabad, India"]
    ),

    # .env: EASY_APPLY_ONLY=true  (true = only Easy Apply jobs, false = all jobs)
    "easy_apply_only": os.getenv("EASY_APPLY_ONLY", "true").lower() == "true",

    # .env: EXPERIENCE_LEVEL=entry
    # Options: internship | entry | associate | mid_senior | any
    "experience_level": os.getenv("EXPERIENCE_LEVEL", "entry"),

    # .env: CHECK_INTERVAL=15  (minutes between each check)
    "check_interval_minutes": int(os.getenv("CHECK_INTERVAL", "15")),

    # ── Title filtering ────────────────────────────────────────────────────────
    # Job title MUST contain at least one of these (case-insensitive)
    # .env: TITLE_INCLUDE=data engineer,software engineer,data analyst
    "title_must_include": parse_list(
        os.getenv("TITLE_INCLUDE", "data engineer,software engineer"),
        ["data engineer", "software engineer"]
    ),

    # Job title must NOT contain any of these — blocks senior/lead/manager roles
    # .env: TITLE_EXCLUDE=senior,lead,manager,director,principal,architect
    "title_must_exclude": parse_list(
        os.getenv("TITLE_EXCLUDE",
            "senior,sr.,lead,principal,staff,manager,head,director,architect,vp,vice president,team lead"),
        ["senior", "sr.", "lead", "principal", "staff", "manager",
         "head", "director", "architect", "vp", "vice president", "team lead"]
    ),

    # ── Notifications ──────────────────────────────────────────────────────────
    "desktop_notify":     os.getenv("DESKTOP_NOTIFY", "true").lower() == "true",
    "email_notify":       os.getenv("EMAIL_NOTIFY", "false").lower() == "true",
    "telegram_notify":    os.getenv("TELEGRAM_NOTIFY", "false").lower() == "true",

    "smtp_server":        os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port":          int(os.getenv("SMTP_PORT", "587")),
    "email_sender":       os.getenv("EMAIL_SENDER", ""),
    "email_password":     os.getenv("EMAIL_PASSWORD", ""),
    "email_recipient":    os.getenv("EMAIL_RECIPIENT", ""),

    "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "telegram_chat_id":   os.getenv("TELEGRAM_CHAT_ID", ""),

    "jobs_file":          "jobs.json",
    "seen_ids_file":      "seen_jobs.json",
}


# ── URL Builder ───────────────────────────────────────────────────────────────
def build_linkedin_url(keywords, location):
    exp_codes = {
        "internship": "1",
        "entry":      "2",
        "associate":  "3",
        "mid_senior": "4",
        "any":        "",
    }
    params = {
        "keywords": keywords.replace(" ", "%20"),
        "location": location.replace(" ", "%20"),
        "f_TPR":    "r86400",
        "sortBy":   "DD",
    }
    if CONFIG["easy_apply_only"]:
        params["f_LF"] = "f_AL"
    code = exp_codes.get(CONFIG["experience_level"], "2")
    if code:
        params["f_E"] = code
    return "https://www.linkedin.com/jobs/search/?" + "&".join(f"{k}={v}" for k, v in params.items())


# ── Title Filter ──────────────────────────────────────────────────────────────
def is_title_allowed(title):
    t = title.lower().strip()
    includes = [r.lower() for r in CONFIG["title_must_include"]]
    excludes = [r.lower() for r in CONFIG["title_must_exclude"]]
    if not any(role in t for role in includes):
        return False, "not a target role"
    for excl in excludes:
        if excl in t:
            return False, f"excluded keyword: '{excl}'"
    return True, ""


# ── Scraper ───────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

def fetch_jobs(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Fetch failed: {e}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []
    for card in soup.find_all("div", class_="base-card"):
        try:
            t = card.find("h3", class_="base-search-card__title")
            c = card.find("h4", class_="base-search-card__subtitle")
            l = card.find("span", class_="job-search-card__location")
            a = card.find("a", class_="base-card__full-link")
            d = card.find("time")
            title    = t.get_text(strip=True) if t else "N/A"
            company  = c.get_text(strip=True) if c else "N/A"
            location = l.get_text(strip=True) if l else "N/A"
            link     = a["href"].split("?")[0] if a else "#"
            posted   = d["datetime"] if d and d.has_attr("datetime") else "Unknown"
            jobs.append({
                "id": hashlib.md5(link.encode()).hexdigest()[:12],
                "title": title, "company": company, "location": location,
                "link": link, "posted": posted,
                "found_at": datetime.now().isoformat(),
                "applied": False, "saved": False,
            })
        except Exception as e:
            log.warning(f"Parse error: {e}")
    return jobs


# ── Storage ───────────────────────────────────────────────────────────────────
def load_seen_ids():
    if os.path.exists(CONFIG["seen_ids_file"]):
        with open(CONFIG["seen_ids_file"]) as f: return set(json.load(f))
    return set()

def save_seen_ids(seen):
    with open(CONFIG["seen_ids_file"], "w") as f: json.dump(list(seen), f)

def load_jobs():
    if os.path.exists(CONFIG["jobs_file"]):
        with open(CONFIG["jobs_file"]) as f: return json.load(f)
    return []

def save_jobs(jobs):
    with open(CONFIG["jobs_file"], "w") as f: json.dump(jobs, f, indent=2)

def merge_jobs(new_jobs, existing):
    ids = {j["id"] for j in existing}
    return [j for j in new_jobs if j["id"] not in ids] + existing


# ── Notifications ─────────────────────────────────────────────────────────────
def notify_desktop(job):
    try:
        from plyer import notification
        notification.notify(title="New Job Alert!", timeout=10,
            message=f"{job['title']} at {job['company']}\n{job['location']}")
    except Exception as e:
        log.warning(f"Desktop notify failed: {e}")

def notify_email(jobs):
    if not jobs: return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{len(jobs)} New Job(s) Found!"
        msg["From"] = CONFIG["email_sender"]
        msg["To"]   = CONFIG["email_recipient"]
        rows = "".join(
            f"<tr><td style='padding:8px'>{j['title']}</td>"
            f"<td style='padding:8px'>{j['company']}</td>"
            f"<td style='padding:8px'>{j['location']}</td>"
            f"<td style='padding:8px'><a href='{j['link']}'>Apply</a></td></tr>"
            for j in jobs)
        msg.attach(MIMEText(
            f"<html><body><table border='1' style='border-collapse:collapse'>{rows}</table></body></html>",
            "html"))
        with smtplib.SMTP(CONFIG["smtp_server"], CONFIG["smtp_port"]) as s:
            s.starttls()
            s.login(CONFIG["email_sender"], CONFIG["email_password"])
            s.sendmail(CONFIG["email_sender"], CONFIG["email_recipient"], msg.as_string())
        log.info(f"Email sent ({len(jobs)} jobs)")
    except Exception as e:
        log.error(f"Email failed: {e}")

def notify_telegram(jobs):
    token, chat_id = CONFIG["telegram_bot_token"], CONFIG["telegram_chat_id"]
    if not token or not chat_id or not jobs: return
    for job in jobs[:5]:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=10,
                json={"chat_id": chat_id, "parse_mode": "Markdown", "disable_web_page_preview": False,
                      "text": f"*{job['title']}*\n{job['company']}\n{job['location']}\n[Apply]({job['link']})"})
        except Exception as e:
            log.error(f"Telegram failed: {e}")


# ── Main Check ────────────────────────────────────────────────────────────────
def check_for_new_jobs():
    log.info("Checking for new jobs...")
    all_fetched = []

    for keyword in CONFIG["keywords_list"]:
        for location in CONFIG["locations_list"]:
            log.info(f"  Searching: '{keyword}' in {location}")
            jobs = fetch_jobs(build_linkedin_url(keyword, location))
            log.info(f"  -> {len(jobs)} raw results")
            all_fetched.extend(jobs)
            time.sleep(3)

    if not all_fetched:
        log.warning("Nothing fetched — may be rate limited. Retrying next cycle.")
        return

    filtered, skipped = [], 0
    for job in all_fetched:
        ok, reason = is_title_allowed(job["title"])
        if ok:
            filtered.append(job)
        else:
            log.info(f"  Filtered: '{job['title']}' — {reason}")
            skipped += 1
    log.info(f"  Filter: {len(filtered)} kept, {skipped} removed")

    seen = load_seen_ids()
    new_jobs = [j for j in filtered if j["id"] not in seen]
    if not new_jobs:
        log.info("No new jobs this cycle.")
        return

    log.info(f"NEW: {len(new_jobs)} job(s) found!")
    for job in new_jobs:
        log.info(f"  + {job['title']} @ {job['company']} ({job['location']})")

    seen.update(j["id"] for j in new_jobs)
    save_seen_ids(seen)
    save_jobs(merge_jobs(new_jobs, load_jobs()))

    for job in new_jobs:
        if CONFIG["desktop_notify"]: notify_desktop(job)
    if CONFIG["email_notify"]:    notify_email(new_jobs)
    if CONFIG["telegram_notify"]: notify_telegram(new_jobs)


# ── Entry Point ───────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("  LinkedIn Job Notifier")
    log.info(f"  Roles      : {', '.join(CONFIG['keywords_list'])}")
    log.info(f"  Locations  : {', '.join(CONFIG['locations_list'])}")
    log.info(f"  Experience : {CONFIG['experience_level']}")
    log.info(f"  Easy Apply : {CONFIG['easy_apply_only']}")
    log.info(f"  Interval   : every {CONFIG['check_interval_minutes']} min")
    log.info(f"  Including  : {CONFIG['title_must_include']}")
    log.info(f"  Excluding  : {CONFIG['title_must_exclude']}")
    log.info("=" * 60)

    check_for_new_jobs()
    schedule.every(CONFIG["check_interval_minutes"]).minutes.do(check_for_new_jobs)
    log.info("Scheduler running. Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    main()
