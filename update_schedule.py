#!/usr/bin/env python3
"""
Rock Boat XXV Schedule Scraper and ICS Generator

Scrapes the schedule from The Rock Boat website, generates an ICS calendar file,
detects changes from the previous version, and sends Slack notifications.
"""

import hashlib
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

SCHEDULE_URL = "https://www.therockboat.com/schedule/print/"
TIMEZONE = ZoneInfo("America/New_York")

# The Rock Boat XXV dates (January 29 - February 4, 2026)
DATES = {
    "thursday, january 29": (2026, 1, 29),
    "friday, january 30": (2026, 1, 30),
    "saturday, january 31": (2026, 1, 31),
    "sunday, february 1": (2026, 2, 1),
    "monday, february 2": (2026, 2, 2),
    "tuesday, february 3": (2026, 2, 3),
    "wednesday, february 4": (2026, 2, 4),
}

# VTIMEZONE component for America/New_York (required for Google Calendar)
VTIMEZONE = """BEGIN:VTIMEZONE
TZID:America/New_York
X-LIC-LOCATION:America/New_York
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE"""


def fetch_schedule() -> str:
    """Fetch the schedule page HTML."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; RockBoatCalendarBot/1.0)"
    }
    response = requests.get(SCHEDULE_URL, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def generate_hash(content: str) -> str:
    """Generate SHA256 hash of content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def parse_time_to_minutes(time_str: str) -> int:
    """Convert time string like '8:00' to minutes since midnight."""
    time_str = time_str.strip()
    match = re.match(r'(\d{1,2}):(\d{2})', time_str)
    if not match:
        raise ValueError(f"Cannot parse time: {time_str}")
    hours = int(match.group(1))
    minutes = int(match.group(2))
    return hours * 60 + minutes


def minutes_to_datetime(minutes: int, base_date: datetime, is_end_time: bool = False, start_minutes: int = None) -> datetime:
    """
    Convert minutes since midnight to datetime.
    
    Cruise schedule runs ~9am to ~3am. We need to determine if a time is AM or PM
    based on context. Times 9-11 are morning, 12 is noon, 1-8 need context.
    """
    hours = minutes // 60
    mins = minutes % 60
    
    # Determine the actual hour in 24-hour format
    if hours >= 9 and hours <= 11:
        # Morning: 9am, 10am, 11am
        actual_hour = hours
    elif hours == 12:
        # Noon (or midnight if it's an end time after a late event)
        if is_end_time and start_minutes and start_minutes >= 20 * 60:
            # If start was 8pm or later and end is 12, it's midnight
            actual_hour = 0
        else:
            actual_hour = 12
    elif hours >= 1 and hours <= 3:
        # Could be 1am-3am (late night) or 1pm-3pm (afternoon)
        if is_end_time and start_minutes:
            start_hour = start_minutes // 60
            if start_hour >= 9 and start_hour <= 12:
                # Start was morning/noon, so 1-3 is afternoon
                actual_hour = hours + 12
            elif start_hour >= 13 or start_hour >= 20:
                # Start was afternoon/evening, 1-3 is after midnight
                actual_hour = hours
            else:
                actual_hour = hours + 12
        else:
            # For start times, 1-3 during the day means PM
            actual_hour = hours + 12
    elif hours >= 4 and hours <= 8:
        # 4pm-8pm (afternoon/evening)
        actual_hour = hours + 12
    else:
        actual_hour = hours
    
    result_date = base_date
    
    # Handle day rollover
    if is_end_time and start_minutes:
        start_actual = minutes_to_datetime(start_minutes, base_date, False, None)
        if actual_hour < start_actual.hour or (actual_hour == 0 and start_actual.hour >= 20):
            result_date = base_date + timedelta(days=1)
    
    return result_date.replace(hour=actual_hour, minute=mins, second=0, microsecond=0)


def parse_events(html: str) -> list[dict]:
    """Parse events from the schedule HTML."""
    soup = BeautifulSoup(html, 'html.parser')
    events = []
    
    # Get all text content
    text = soup.get_text(separator='\n')
    
    current_date = None
    current_theme = None
    
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Check for date headers
        line_lower = line.lower()
        for date_str, (year, month, day) in DATES.items():
            if date_str in line_lower:
                current_date = datetime(year, month, day, tzinfo=TIMEZONE)
                # Theme is usually on the next non-empty line
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and not any(d in next_line.lower() for d in DATES.keys()):
                        if not re.search(r'\d{1,2}:\d{2}', next_line):
                            current_theme = next_line
                            break
                break
        
        # Look for event patterns: "Event Name  HH:MM- HH:MM"
        # This regex matches text followed by a time range
        event_match = re.search(
            r'^(.+?)\s+(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})\s*$',
            line
        )
        
        if event_match and current_date:
            event_name = event_match.group(1).strip()
            start_time = event_match.group(2)
            end_time = event_match.group(3)
            
            # Skip table headers and non-event lines
            if any(skip in event_name.lower() for skip in ['pool deck', 'stardust', 'spinnaker', 'atrium', "magnum's", 'sports court', 'deck']):
                if len(event_name) < 20:
                    continue
            
            try:
                start_minutes = parse_time_to_minutes(start_time)
                end_minutes = parse_time_to_minutes(end_time)
                
                start_dt = minutes_to_datetime(start_minutes, current_date, False, None)
                end_dt = minutes_to_datetime(end_minutes, current_date, True, start_minutes)
                
                # Generate a unique ID
                uid = f"trb25-{hashlib.md5(f'{event_name}{start_dt.isoformat()}'.encode()).hexdigest()[:8]}@rockboat.com"
                
                events.append({
                    'summary': event_name,
                    'start': start_dt,
                    'end': end_dt,
                    'uid': uid,
                    'theme': current_theme,
                })
            except ValueError as e:
                print(f"Warning: Could not parse time for '{event_name}': {e}")
                continue
    
    return events


def escape_ics_text(text: str) -> str:
    """Escape special characters for ICS format."""
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\n", "\\n")
    return text


def generate_ics(events: list[dict]) -> str:
    """Generate ICS content from events with proper timezone support for Google Calendar."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Rock Boat XXV Schedule//github.com//",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:The Rock Boat XXV",
        "X-WR-TIMEZONE:America/New_York",
    ]
    
    # Add VTIMEZONE component (required for Google Calendar compatibility)
    lines.append(VTIMEZONE)
    
    for event in events:
        # Format datetime with TZID parameter (Google Calendar requirement)
        start_str = event['start'].strftime("%Y%m%dT%H%M%S")
        end_str = event['end'].strftime("%Y%m%dT%H%M%S")
        
        lines.extend([
            "BEGIN:VEVENT",
            f"DTSTART;TZID=America/New_York:{start_str}",
            f"DTEND;TZID=America/New_York:{end_str}",
            f"SUMMARY:{escape_ics_text(event['summary'])}",
            f"UID:{event['uid']}",
        ])
        
        if event.get('location'):
            lines.append(f"LOCATION:{escape_ics_text(event['location'])}")
        
        if event.get('description'):
            lines.append(f"DESCRIPTION:{escape_ics_text(event['description'])}")
        
        lines.append("END:VEVENT")
    
    lines.append("END:VCALENDAR")
    
    # Use CRLF line endings as per ICS spec
    return "\r\n".join(lines)


def compare_events(old_events: list[dict], new_events: list[dict]) -> dict:
    """Compare old and new events to find changes."""
    changes = {
        'added': [],
        'removed': [],
        'modified': [],
    }
    
    old_by_uid = {e['uid']: e for e in old_events}
    new_by_uid = {e['uid']: e for e in new_events}
    
    # Find added events
    for uid, event in new_by_uid.items():
        if uid not in old_by_uid:
            changes['added'].append(event['summary'])
    
    # Find removed events
    for uid, event in old_by_uid.items():
        if uid not in new_by_uid:
            changes['removed'].append(event['summary'])
    
    # Find modified events (same UID but different times)
    for uid in set(old_by_uid.keys()) & set(new_by_uid.keys()):
        old_event = old_by_uid[uid]
        new_event = new_by_uid[uid]
        if old_event['start'] != new_event['start'] or old_event['end'] != new_event['end']:
            changes['modified'].append(f"{new_event['summary']} (time changed)")
    
    return changes


def send_slack_notification(webhook_url: str, changes: dict, schedule_url: str):
    """Send Slack notification about schedule changes."""
    if not webhook_url:
        print("No Slack webhook configured, skipping notification")
        return
    
    # Build change summary
    change_lines = []
    if changes['added']:
        change_lines.append(f"*Added:* {', '.join(changes['added'][:5])}")
        if len(changes['added']) > 5:
            change_lines.append(f"  ...and {len(changes['added']) - 5} more")
    
    if changes['removed']:
        change_lines.append(f"*Removed:* {', '.join(changes['removed'][:5])}")
        if len(changes['removed']) > 5:
            change_lines.append(f"  ...and {len(changes['removed']) - 5} more")
    
    if changes['modified']:
        change_lines.append(f"*Modified:* {', '.join(changes['modified'][:5])}")
        if len(changes['modified']) > 5:
            change_lines.append(f"  ...and {len(changes['modified']) - 5} more")
    
    if not change_lines:
        change_lines.append("Schedule content has changed")
    
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚢🎸 Rock Boat XXV Schedule Updated!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(change_lines)
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Schedule"
                        },
                        "url": "https://www.therockboat.com/schedule/"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Download Calendar"
                        },
                        "url": schedule_url
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=message, timeout=10)
        response.raise_for_status()
        print("✓ Slack notification sent")
    except requests.RequestException as e:
        print(f"✗ Failed to send Slack notification: {e}")


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    ics_file = script_dir / "rockboat_schedule.ics"
    hash_file = script_dir / ".content_hash"
    
    print(f"🚢 Rock Boat XXV Schedule Updater")
    print(f"{'=' * 40}")
    print(f"Fetching schedule from {SCHEDULE_URL}...")
    
    try:
        html = fetch_schedule()
    except requests.RequestException as e:
        print(f"✗ Error fetching schedule: {e}")
        sys.exit(1)
    
    print("✓ Schedule fetched successfully")
    
    # Check if content changed
    new_hash = generate_hash(html)
    old_hash = hash_file.read_text().strip() if hash_file.exists() else None
    
    if new_hash == old_hash:
        print("✓ No changes detected")
        sys.exit(0)
    
    print("! Changes detected, parsing schedule...")
    
    # Parse events
    events = parse_events(html)
    print(f"✓ Parsed {len(events)} events")
    
    # Generate ICS with Google Calendar compatible format
    ics_content = generate_ics(events)
    
    # Compare with old ICS if it exists
    changes = {'added': [], 'removed': [], 'modified': []}
    if ics_file.exists():
        # For detailed comparison, we'd parse the old ICS
        # For now, just note that it changed
        changes['added'] = [f"{len(events)} events in updated schedule"]
    
    # Save new files
    ics_file.write_text(ics_content)
    hash_file.write_text(new_hash)
    print(f"✓ Calendar saved to {ics_file}")
    
    # Send Slack notification
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    calendar_url = os.environ.get("CALENDAR_URL", "https://github.com/YOUR_USERNAME/rockboat-calendar")
    
    if slack_webhook and old_hash is not None:
        send_slack_notification(slack_webhook, changes, calendar_url)
    elif old_hash is None:
        print("✓ Initial run, skipping notification")
    
    # Set output for GitHub Actions
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write("changes_detected=true\n")
    
    print(f"{'=' * 40}")
    print("✓ Update complete!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
