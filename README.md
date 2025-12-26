# 🚢 Rock Boat XXV Schedule Calendar

Auto-updating ICS calendar for The Rock Boat XXV (January 29 - February 4, 2025).

This repository automatically checks for schedule updates twice daily and:
- Updates the ICS calendar file
- Sends a Slack notification when changes are detected
- Hosts a subscribable calendar URL via GitHub Pages

## 📅 Subscribe to the Calendar

Once set up, you can subscribe to this calendar at:

```
[https://topperge.github.io/rockboat-calendar/rockboat_schedule.ics](https://topperge.github.io/rockboat-2025-schedule/rockboat_schedule.ics)
```

### Subscribe in Apple Calendar
1. Open Calendar app
2. File → New Calendar Subscription
3. Paste the URL above
4. Set refresh frequency to "Every day"

### Subscribe in Google Calendar
1. Open Google Calendar
2. Click the `+` next to "Other calendars"
3. Select "From URL"
4. Paste the URL above

### Subscribe in Outlook
1. Open Outlook Calendar
2. Add calendar → Subscribe from web
3. Paste the URL above

## 🚀 Setup Instructions

### 1. Fork or Clone This Repository

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/rockboat-calendar.git
cd rockboat-calendar
```

### 2. Enable GitHub Pages

1. Go to your repository on GitHub
2. Settings → Pages
3. Source: "Deploy from a branch"
4. Branch: `main` / `root`
5. Save

Your calendar will be available at:
```
[https://YOUR_USERNAME.github.io/rockboat-calendar/rockboat_schedule.ics](https://topperge.github.io/rockboat-2025-schedule/rockboat_schedule.ics)
```

### 3. Configure Slack Notifications (Optional)

To receive Slack notifications when the schedule updates:

#### Create a Slack Webhook:
1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Create New App → From scratch
3. Name it "Rock Boat Schedule" and select your workspace
4. Go to "Incoming Webhooks"
5. Activate Incoming Webhooks
6. Click "Add New Webhook to Workspace"
7. Select the channel for notifications
8. Copy the Webhook URL

#### Add the Webhook to GitHub:
1. Go to your repository on GitHub
2. Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `SLACK_WEBHOOK_URL`
5. Value: Paste your Slack webhook URL
6. Click "Add secret"

### 4. Test the Workflow

1. Go to Actions tab in your repository
2. Click "Update Rock Boat Schedule"
3. Click "Run workflow"
4. Verify the workflow completes and the ICS file is updated

## 📁 Files

| File | Description |
|------|-------------|
| `update_schedule.py` | Python script that scrapes the schedule and generates ICS |
| `rockboat_schedule.ics` | The generated calendar file (auto-updated) |
| `requirements.txt` | Python dependencies |
| `.github/workflows/update-schedule.yml` | GitHub Actions workflow |
| `.content_hash` | Hash of last scraped content (for change detection) |

## ⏰ Schedule

The workflow runs automatically:
- **8:00 AM Eastern** - Morning check
- **8:00 PM Eastern** - Evening check

You can also trigger it manually from the Actions tab.

## 🎸 Event Details

**The Rock Boat XXV** - 25th Anniversary Cruise!

**Dates:** January 29 - February 4, 2025

**Ports:**
- Miami, FL (Embarkation)
- St. Maarten
- San Juan, Puerto Rico

**Headliners:**
- NEEDTOBREATHE
- The Struts
- Sister Hazel
- Matt Nathanson
- Bowling For Soup
- Judah & the Lion
- And many more!

## 🔧 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the updater
python update_schedule.py
```

## 📝 License

MIT License - Feel free to use and modify!

---

🌊 See you on the boat! 🎸
