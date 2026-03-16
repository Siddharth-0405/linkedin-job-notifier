# 📡 LinkedIn Job Radar — Data Engineer

Monitors LinkedIn for Data Engineer openings every 15 minutes and notifies you instantly so you can apply before competition piles up.

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure your settings
cp .env.example .env
# Edit .env — set your city, keywords, and notification method

# 3. Run the notifier
python job_notifier.py

# 4. Open dashboard in browser
open dashboard.html        # macOS
start dashboard.html       # Windows
xdg-open dashboard.html    # Linux
```

---

## 📁 Files

| File | Purpose |
|------|---------|
| `job_notifier.py` | Main script — scrapes LinkedIn and sends notifications |
| `dashboard.html` | Visual dashboard to track and open jobs |
| `.env.example` | Config template — copy to `.env` |
| `requirements.txt` | Python dependencies |
| `jobs.json` | Auto-generated — stores all found jobs |
| `seen_jobs.json` | Auto-generated — tracks already seen job IDs |
| `notifier.log` | Auto-generated — script activity log |

---

## 🔔 Notification Methods

### Desktop Notifications (Default — No Config Needed)
Works out of the box on Windows, macOS, Linux via `plyer`.

### Email (Gmail)
1. Enable 2FA on your Google account
2. Generate an App Password at: `myaccount.google.com/apppasswords`
3. Set in `.env`:
```
EMAIL_NOTIFY=true
EMAIL_SENDER=you@gmail.com
EMAIL_PASSWORD=your_16_char_app_password
EMAIL_RECIPIENT=you@gmail.com
```

### Telegram
1. Message `@BotFather` on Telegram → `/newbot` → copy the token
2. Message `@userinfobot` on Telegram → copy your `id` (this is your chat_id)
3. Set in `.env`:
```
TELEGRAM_NOTIFY=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

---

## ⚙️ Customization

Edit `.env` or the `CONFIG` dict in `job_notifier.py`:

```
JOB_KEYWORDS=Data Engineer       # Change to "Senior Data Engineer", "ETL Engineer", etc.
JOB_LOCATION=Bengaluru, India    # Your city or "Remote"
CHECK_INTERVAL=15                # Minutes between checks (don't go below 10)
```

To change the posting recency, find this line in `job_notifier.py`:
```python
"f_TPR": "r3600",   # r3600 = last hour, r86400 = last 24 hours
```

---

## 🌐 Dashboard Features

- **Live job list** — auto-refreshes every 60 seconds
- **One-click apply** — opens LinkedIn directly to the job
- **"Open All Pending"** — opens all unapplied jobs in tabs at once
- **Mark as Applied** — track what you've applied to
- **Filter** — view All / Pending / Applied
- **Search** — filter by title, company, or location

---

## ⚠️ Important Notes

- This tool is for **personal use only**
- LinkedIn's ToS prohibits automated scraping — use responsibly
- If you see `No jobs fetched — might be rate limited`, the tool will auto-retry
- LinkedIn may serve a CAPTCHA after many rapid requests — keep `CHECK_INTERVAL` at 15+ minutes
- The dashboard reads from `jobs.json` — open it in the **same folder** as the script

---

## 🔄 Run on Startup (Optional)

**Windows**: Add to Task Scheduler or create a `.bat` file
**macOS**: Add a `launchd` plist or use `cron`
**Linux**:
```bash
# Add to crontab to run on system boot
@reboot cd /path/to/job-notifier && python job_notifier.py >> notifier.log 2>&1 &
```
