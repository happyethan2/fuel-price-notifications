# fuel-price-notifications

Checks Adelaide fuel prices and sends a short push note with advice.
Uses SA Fuel API for prices, OpenAI for the sentence, and Pushover to notify.
Stores data in a CSV (no database).

## How it works
- Cron runs the script on my server
- Appends a row to `pricedata.csv` (one per day)
- Reads `users.json` (recipients) and `config.py` (API keys) — both local only

## Setup
    git clone https://github.com/<your-username>/fuel-price-notifications.git
    cd fuel-price-notifications
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

Create `src/config.py` and `src/users.json` from the examples and put your own values.

## Do not commit secrets
Add to `.gitignore` (already in repo):
- `src/config.py`
- `src/users.json`
- `venv/`, logs, caches

## Run
    source venv/bin/activate
    python src/main.py

## Cron (server)
Runs daily at 9am ACST; the script itself only sends on Mon/Thu/Sat.
    CRON_TZ=Australia/Adelaide
    0 9 * * * /home/ethan/apps/fuel-alerts/run.sh

## Notes
- Logs land in `logs/` as `run.YYYY-MM-DD.log`
- Simple side project; PRs welcome but no guarantees 🙂
