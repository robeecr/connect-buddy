# Connect Buddy

**Paste a Claude or ChatGPT workout → it lands on your Garmin device.**

No subscription. No calendar UI. No coaching platform. Just the bridge between AI-generated workouts and Garmin Connect.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/robeecr/connect-buddy)

---

## What it does

1. Paste a workout JSON from Claude, ChatGPT, or any AI assistant — or upload a `.json` / `.xml` file
2. See a live preview of your steps, durations, and pace targets (repeat blocks shown as grouped rows)
3. **Push to Garmin Connect** — enter your Garmin credentials and the workout lands directly in your account, ready to sync to your watch

## Privacy

Garmin credentials are sent once to the server to authenticate with Garmin Connect and are never stored. If you want zero credential exposure, deploy your own instance using the button above — your credentials then only go from your browser to your own server.

## Deploy your own (one click)

Click **Deploy to Render** above. Render will:
- Clone the repo
- Install dependencies
- Start the server

Free tier spins down after 15 minutes of inactivity and has a ~30 second cold start on first visit. Upgrade to a paid Render instance ($7/month) to keep it always-on.

## Run locally

```bash
git clone https://github.com/robeecr/connect-buddy.git
cd connect-buddy/backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open **http://localhost:8000**

## Asking AI for the right format

Ask Claude or ChatGPT to generate a workout in Connect Buddy format. Example prompt:

> Generate a 10km threshold run workout in Connect Buddy JSON format. Include a 10-minute warm-up, 20 minutes at threshold pace (4:30–4:40 /km), and a 10-minute cool-down. Use pace targets in sec/km.

The app also accepts Garmin Connect's native workout JSON if you export one directly.

## Workout JSON format

```json
{
  "name": "Threshold Run",
  "sport": "running",
  "steps": [
    {"name": "Warm Up",    "intensity": "warmup",   "duration": {"type": "time", "value_s": 600},  "target": {"type": "open"}},
    {"name": "Threshold",  "intensity": "interval", "duration": {"type": "time", "value_s": 1200}, "target": {"type": "pace", "low_ms": 3.5714, "high_ms": 3.7037}},
    {"name": "Cool Down",  "intensity": "cooldown", "duration": {"type": "time", "value_s": 600},  "target": {"type": "open"}}
  ]
}
```

Full schema reference is available in the app under **Schema Reference**.

## Stack

- **Backend**: FastAPI + Python
- **Frontend**: Vanilla JS, no build step
- **Garmin Connect**: [garminconnect](https://pypi.org/project/garminconnect/)

## Contributing

PRs welcome. The core conversion logic lives in `backend/app/core/`. Tests are in `backend/tests/`.

```bash
cd backend
pip install -r requirements-dev.txt
pytest -v
```

## License

MIT
