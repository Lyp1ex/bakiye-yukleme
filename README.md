# Telegram Coin Shop Bot (Python)

A production-ready MVP Telegram bot with:

- Manual bank deposit requests (receipt upload + admin approval)
- TRX payment request + blockchain detection watcher + **manual admin approval only**
- Coin shop purchase flow
- Post-purchase required fields: Game User ID, IBAN, Name Surname, Bank Name
- Admin panel for deposits, orders, games, products, packages, templates, user search, manual coin add/remove

## Important Security Rule

This bot enforces:

- **No automatic coin loading**
- **All bank and crypto deposits require admin approval**

---

## Project Structure

```text
bot/
  main.py
  config/
  database/
  models/
  services/
  handlers/
  keyboards/
  admin/
  crypto/
  texts/
  utils/
  migrations/
```

---

## 1) Where to paste the code (beginner)

If you already have this project folder, skip this section.

If you are starting from scratch:

1. Create a folder named `telegram-coin-shop-bot`.
2. Put each file into the exact path shown in this repository.
3. Open Terminal (or Command Prompt) and move into that folder.

Mac example:

```bash
cd /path/to/telegram-coin-shop-bot
```

---

## 2) Install Python (beginner)

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Install Python **3.11 or newer**.
3. Verify installation:

Mac/Linux:

```bash
python3 --version
```

Windows:

```bash
python --version
```

You should see something like `Python 3.11.x`.

---

## 3) Install dependencies

### Mac/Linux

```bash
cd /Users/yasindemirci/Documents/AI
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Windows (PowerShell)

```powershell
cd C:\path\to\telegram-coin-shop-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4) Create `.env` file

1. Copy example file:

Mac/Linux:

```bash
cp .env.example .env
```

Windows:

```powershell
copy .env.example .env
```

2. Open `.env` and fill values:

```env
BOT_TOKEN=
ADMIN_IDS=
IBAN_TEXT=
TRON_RPC_URL=https://api.trongrid.io
TRON_WALLET_ADDRESS=
TRON_PRIVATE_KEY=
CRYPTO_AUTO_APPROVE=false
DATABASE_URL=sqlite:///./bot.db
LOG_LEVEL=INFO
TRON_CHECK_INTERVAL_SEC=45
```

### How to get values

- `BOT_TOKEN`: Create bot with Telegram `@BotFather` -> `/newbot`
- `ADMIN_IDS`: Your Telegram numeric ID (example: `123456789`), comma-separated for multiple admins
- `IBAN_TEXT`: Bank instructions shown to users
- `TRON_WALLET_ADDRESS`: Your receiving TRON wallet address

---

## 5) Run bot locally (step-by-step)

### Step A: Run migration

```bash
alembic upgrade head
```

### Step B: Start bot

```bash
python -m bot.main
```

You should see logs and bot starts with **long polling**.

### Step C: First checks

1. In Telegram, send `/start` to bot.
2. In Telegram, from admin account send `/admin`.
3. In admin panel, add/manage games/products/packages if needed.
4. Test full flow: load coins (bank and TRX), approve from admin, buy product.

---

## Admin Panel (`/admin`)

Includes:

- Pending Bank Deposits
- Pending Crypto Deposits
- Pending Orders
- Manage Games
- Manage Products
- Manage Coin Packages
- Search Users
- Manual coin add/remove
- Message Templates

---

## Free Hosting Guide (Render) for 3+ months

This project includes `render.yaml`.

### Why Render in this repo

- Railway and Fly plans commonly move to paid/trial limits.
- Render free web service can be used for one bot if you keep a health ping running.

### Step-by-step (beginner)

1. Create GitHub account: [github.com](https://github.com)
2. Create new repository.
3. Upload this whole project to that repo.
4. Create Render account: [render.com](https://render.com)
5. In Render dashboard: `New +` -> `Blueprint`
6. Connect your GitHub repo.
7. Render reads `render.yaml` automatically.
8. In Render service -> `Environment`, fill these variables:
   - `BOT_TOKEN`
   - `ADMIN_IDS`
   - `IBAN_TEXT`
   - `TRON_WALLET_ADDRESS`
   - `TRON_PRIVATE_KEY`
9. Click deploy.
10. After deploy, open:
    - `https://YOUR_RENDER_URL/health`
    - Must return `ok`

### Keep it running 24/7 on free plan

Render free instances can sleep when no inbound traffic. To avoid sleep:

1. Create free monitor at [UptimeRobot](https://uptimerobot.com/)
2. Add HTTP monitor to `https://YOUR_RENDER_URL/health`
3. Interval: every 5-10 minutes

This keeps traffic active and helps bot stay online continuously.

---

## How to update the bot later

1. Edit code locally.
2. Test locally:

```bash
alembic upgrade head
python -m bot.main
```

3. Push changes to GitHub.
4. Render auto-deploys from new commit.
5. Watch Render logs for startup errors.

---

## Notes

- SQLite is default for MVP (`DATABASE_URL=sqlite:///./bot.db`).
- For PostgreSQL later, set `DATABASE_URL` to your Postgres URL.
- `CRYPTO_AUTO_APPROVE` exists for compatibility, but this bot still requires admin approval by design.
