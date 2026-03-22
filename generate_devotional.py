#!/usr/bin/env python3
"""
Byrd Family Daily Devotional Generator
Generates daily devotional content via Anthropic API and updates index.html
"""

import os
import re
import json
import requests
from datetime import date, datetime, timezone, timedelta
from anthropic import Anthropic

# ── Theme & Verse Selection ──────────────────────────────────────────────────

THEMES = [
    "Faith & Trust", "Wisdom", "Courage", "Family", "Peace", "Purpose",
    "Perseverance", "Gratitude", "Leadership", "Generosity", "Forgiveness", "Hope"
]

VERSES = {
    "Faith & Trust": [
        "Proverbs 3:5-6", "Hebrews 11:1", "Isaiah 41:10", "Psalm 56:3-4",
        "2 Corinthians 5:7", "Mark 11:22-24", "Jeremiah 29:11"
    ],
    "Wisdom": [
        "James 1:5", "Proverbs 2:6-7", "Proverbs 4:7", "Colossians 3:16",
        "Proverbs 16:16", "Psalm 111:10", "Proverbs 9:10"
    ],
    "Courage": [
        "Joshua 1:9", "Deuteronomy 31:6", "Isaiah 43:1-2", "Psalm 27:1",
        "2 Timothy 1:7", "Psalm 31:24", "1 Chronicles 28:20"
    ],
    "Family": [
        "Proverbs 22:6", "Colossians 3:13-14", "Deuteronomy 6:6-7",
        "Psalm 127:3-5", "Ephesians 5:25", "1 Corinthians 13:4-7", "Proverbs 17:6"
    ],
    "Peace": [
        "Philippians 4:6-7", "John 14:27", "Isaiah 26:3", "Psalm 46:10",
        "Romans 15:13", "Colossians 3:15", "Matthew 11:28-30"
    ],
    "Purpose": [
        "Romans 8:28", "Ephesians 2:10", "Jeremiah 1:5", "Philippians 1:6",
        "Proverbs 19:21", "Psalm 138:8", "1 Peter 2:9"
    ],
    "Perseverance": [
        "Galatians 6:9", "James 1:2-4", "Romans 5:3-5", "Hebrews 12:1-2",
        "2 Corinthians 4:16-18", "Isaiah 40:31", "Philippians 3:13-14"
    ],
    "Gratitude": [
        "1 Thessalonians 5:18", "Psalm 118:24", "Colossians 3:17",
        "Psalm 107:1", "Philippians 4:11-12", "James 1:17", "Psalm 136:1"
    ],
    "Leadership": [
        "Proverbs 11:14", "Mark 10:43-45", "1 Timothy 4:12",
        "Matthew 20:26-28", "Proverbs 29:2", "Micah 6:8", "Philippians 2:3-4"
    ],
    "Generosity": [
        "2 Corinthians 9:7", "Proverbs 11:25", "Luke 6:38", "Acts 20:35",
        "Malachi 3:10", "Matthew 6:3-4", "1 Timothy 6:18"
    ],
    "Forgiveness": [
        "Colossians 3:13", "Ephesians 4:32", "Matthew 6:14-15", "Luke 6:37",
        "Mark 11:25", "1 John 1:9", "Psalm 103:12"
    ],
    "Hope": [
        "Romans 15:13", "Jeremiah 29:11", "Psalm 42:11", "Romans 8:24-25",
        "Hebrews 6:19", "Lamentations 3:22-24", "1 Peter 1:3"
    ],
}


def get_today_eastern():
    """Get today's date in US Eastern time."""
    et = timezone(timedelta(hours=-4))  # EDT; use -5 for EST
    # Use -5 Nov-Mar, -4 Mar-Nov (simplified)
    now_utc = datetime.now(timezone.utc)
    month = now_utc.month
    if month >= 3 and month < 11:
        et = timezone(timedelta(hours=-4))
    else:
        et = timezone(timedelta(hours=-5))
    return now_utc.astimezone(et).date()


def select_theme_and_verse(today):
    """Select theme and verse based on day-of-year formula."""
    day_of_year = today.timetuple().tm_yday
    theme_index = (day_of_year * 7) % 12
    theme = THEMES[theme_index]

    # Day of week: Monday=0 in Python, we need Monday=1..Sunday=7
    dow = today.isoweekday()  # 1=Monday, 7=Sunday
    verse_ref = VERSES[theme][dow - 1]

    return theme, verse_ref


# ── NLT API ──────────────────────────────────────────────────────────────────

def format_ref_for_api(ref):
    """Convert 'Proverbs 3:5-6' to 'Proverbs.3.5-6' for NLT API."""
    # Handle numbered books: "1 Corinthians" -> "1Corinthians"
    ref_api = re.sub(r'^(\d)\s+', r'\1', ref)
    # Replace spaces and colons with periods
    ref_api = ref_api.replace(' ', '.').replace(':', '.')
    return ref_api


def fetch_nlt_verse(ref):
    """Fetch verse HTML from NLT API."""
    api_key = os.environ.get("NLT_API_KEY", "TEST")
    api_ref = format_ref_for_api(ref)
    url = f"https://api.nlt.to/api/passages?ref={api_ref}&key={api_key}"

    for attempt in range(2):
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200 and resp.text.strip():
                html = resp.text
                # Extract text from bibletext div
                match = re.search(r'<div[^>]*id="bibletext"[^>]*>(.*?)</div>', html, re.DOTALL)
                if match:
                    text = match.group(1).strip()
                else:
                    text = html.strip()

                # Clean up HTML
                text = re.sub(r'</?verse_export[^>]*>', '', text)
                text = re.sub(r'</?section[^>]*>', '', text)
                text = re.sub(r'class="[^"]*"', '', text)
                # Convert small caps for LORD
                text = text.replace('class="sc"', 'style="font-variant:small-caps"')
                text = re.sub(r'<span\s+style="font-variant:small-caps"\s*>', '<span style="font-variant:small-caps">', text)
                # Clean excess whitespace
                text = re.sub(r'\s+', ' ', text).strip()

                if text:
                    return text
        except Exception as e:
            print(f"NLT API attempt {attempt + 1} failed: {e}")

    return None


# ── Anthropic API ────────────────────────────────────────────────────────────

def generate_study_content(theme, verse_ref, verse_html):
    """Use Anthropic API to generate the study lesson."""
    client = Anthropic()

    verse_text = re.sub(r'<[^>]+>', ' ', verse_html).strip()
    verse_text = re.sub(r'\s+', ' ', verse_text)

    prompt = f"""You are writing a daily Bible devotional for the Byrd family — Michael (CRO, former pro baseball player), Lisa (his wife), Carson (21, at Florida State), Gavin (18, committed to play baseball at South Carolina), and Griffin (18, going to Florida State, interested in business law).

Today's theme: {theme}
Today's verse: {verse_ref} (NLT)
Verse text: {verse_text}

Generate exactly five sections in a warm, accessible tone suitable for a family audience ages 18 to adult. Write in a direct, grounded style — not preachy, not generic.

Return ONLY a JSON object with these exact keys (no markdown, no code fences):

{{
  "context": "Historical Context — 2-3 sentences. Author, time period, circumstances. Include Hebrew or Greek word meaning when it adds depth.",
  "takeaway": "Key Takeaway — 2-3 sentences. Core message in modern language. Connect to present-day relevance. Make it actionable.",
  "reflection": "Reflection Question — One thought-provoking, introspective question relevant to real life.",
  "application": "Today's Application — 1-2 sentences. One specific, practical action for today that takes 30 seconds to 5 minutes.",
  "prayer": "Family Prayer — 3-5 sentences. Address God directly. Reference the day's theme. Close with In Jesus' name, Amen."
}}

Important:
- Do NOT use backticks anywhere in the content
- Do NOT use markdown formatting
- Escape any double quotes inside the JSON string values
- Make the content specific to THIS verse and THIS theme — no generic filler"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()

    # Parse JSON response — handle potential code fences
    response_text = re.sub(r'^```json\s*', '', response_text)
    response_text = re.sub(r'\s*```$', '', response_text)

    return json.loads(response_text)


# ── HTML Update ──────────────────────────────────────────────────────────────

def escape_for_template_literal(text):
    """Escape backticks and ${} in text for JS template literals."""
    text = text.replace('\\', '\\\\')
    text = text.replace('`', '\\`')
    text = text.replace('${', '\\${')
    return text


def update_index_html(today_str, theme, verse_ref, verse_html, content):
    """Update index.html with new devotional data."""
    with open("index.html", "r") as f:
        html = f.read()

    start_marker = "/*DATA_START*/"
    end_marker = "/*DATA_END*/"
    start_idx = html.index(start_marker)
    end_idx = html.index(end_marker) + len(end_marker)

    current_data = html[start_idx:end_idx]

    # Extract current today block for archiving
    today_block_start = current_data.index("today: {") + len("today: {")
    # Find the closing brace of the today block
    brace_depth = 1
    i = today_block_start
    while brace_depth > 0 and i < len(current_data):
        if current_data[i] == '{':
            brace_depth += 1
        elif current_data[i] == '}':
            brace_depth -= 1
        i += 1
    today_block_end = i - 1  # position of closing brace
    yesterday_content = current_data[today_block_start:today_block_end].strip()

    # Extract archive entries
    archive_start = current_data.index("archive: [") + len("archive: [")
    archive_end = current_data.rindex("]")
    archive_content = current_data[archive_start:archive_end].strip()

    # Parse archive entries by matching braces
    entries = []
    if archive_content:
        depth = 0
        entry_start = None
        for idx, ch in enumerate(archive_content):
            if ch == '{':
                if depth == 0:
                    entry_start = idx
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and entry_start is not None:
                    entries.append(archive_content[entry_start:idx + 1])
                    entry_start = None

    # Build new archive: yesterday + first 5 existing entries = 6 total
    new_archive_entries = ["        {\n" + yesterday_content + "\n        }"]
    for entry in entries[:5]:
        new_archive_entries.append("        " + entry)

    archive_str = ",\n".join(new_archive_entries)

    # Escape content for JS template literals
    vh = escape_for_template_literal(verse_html)
    ctx = escape_for_template_literal(content["context"])
    tk = escape_for_template_literal(content["takeaway"])
    rf = escape_for_template_literal(content["reflection"])
    ap = escape_for_template_literal(content["application"])
    pr = escape_for_template_literal(content["prayer"])

    new_data = f"""/*DATA_START*/
    const DEVOTIONAL_DATA = {{
      today: {{
        date: "{today_str}",
        theme: "{theme}",
        verse_ref: "{verse_ref}",
        verse_html: `{vh}`,
        context: `{ctx}`,
        takeaway: `{tk}`,
        reflection: `{rf}`,
        application: `{ap}`,
        prayer: `{pr}`
      }},
      archive: [
{archive_str}
      ]
    }};
    /*DATA_END*/"""

    new_html = html[:start_idx] + new_data + html[end_idx:]

    # Verify markers and dates
    assert "/*DATA_START*/" in new_html, "DATA_START marker missing"
    assert "/*DATA_END*/" in new_html, "DATA_END marker missing"
    assert f'"{today_str}"' in new_html, "Today's date missing"

    with open("index.html", "w") as f:
        f.write(new_html)

    # Count entries for verification
    dates = re.findall(r'date: "([^"]+)"', new_html)
    print(f"Dates in data: {dates}")
    print(f"Today: {dates[0]}, Archive count: {len(dates) - 1}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    today = get_today_eastern()
    today_str = today.isoformat()
    print(f"Date: {today_str}")

    # Check if already updated today
    with open("index.html", "r") as f:
        if f'date: "{today_str}"' in f.read():
            print(f"Already updated for {today_str}. Skipping.")
            return

    theme, verse_ref = select_theme_and_verse(today)
    print(f"Theme: {theme}")
    print(f"Verse: {verse_ref}")

    # Fetch NLT verse
    verse_html = fetch_nlt_verse(verse_ref)
    if not verse_html:
        print("NLT API failed. Using Anthropic to provide verse text.")
        # Ask Anthropic for the verse text as fallback
        client = Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": f"Provide the NLT translation of {verse_ref}. Return ONLY the verse text wrapped in <p> tags with verse numbers in <span class=\"vn\"> tags. No other text."}]
        )
        verse_html = msg.content[0].text.strip()
        verse_html = re.sub(r'^```html\s*', '', verse_html)
        verse_html = re.sub(r'\s*```$', '', verse_html)
        print(f"Fallback verse: {verse_html[:100]}...")
    else:
        print(f"NLT verse fetched: {verse_html[:100]}...")

    # Generate study content
    print("Generating study content via Anthropic API...")
    content = generate_study_content(theme, verse_ref, verse_html)
    print("Content generated successfully.")

    # Update HTML
    update_index_html(today_str, theme, verse_ref, verse_html, content)
    print(f"index.html updated for {today_str}")


if __name__ == "__main__":
    main()
