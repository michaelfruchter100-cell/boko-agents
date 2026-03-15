import os.path
import datetime
import json
from zoneinfo import ZoneInfo
import streamlit as st

ISRAEL_TZ = ZoneInfo('Asia/Jerusalem')
import extra_streamlit_components as stx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',
]

# --- שם: מייל ---
FRIENDS = {
    "מיכאל": "michaelfruchter100@gmail.com",
    "בן": "benprash94@gmail.com",
    "עובדיה": "ovadiadaniel205@gmail.com",
}

# ---- הגדרות ----
ACTIVITY_MIN_PEOPLE = {
    "פוקר": 6, "poker": 6,
    "כדורגל": 8, "football": 8,
}
ACTIVITY_DURATIONS = {
    "פוקר": 4, "poker": 4,
    "כדורגל": 2, "football": 2,
    "כדורסל": 1.5, "basketball": 1.5,
    "טניס": 1.5,
    "בירה": 2, "בר": 2,
    "אוכל": 1.5, "ארוחה": 1.5, "ארוחת ערב": 1.5, "ארוחת צהריים": 1.5,
    "ארוחת בוקר": 1,
    "קפה": 1,
    "סרט": 2.5,
    "גיבוש": 3,
    "פגישה": 1,
    "טיול": 4,
    "מסיבה": 3,
    "גיימינג": 3, "משחק": 3,
}
MILUIM_SHIFTS = [(6, 10), (10, 14), (14, 18), (18, 22), (22, 2), (2, 6)]
AFTER_SHIFT_BUFFER = datetime.timedelta(minutes=30)
BEFORE_SHIFT_BUFFER = datetime.timedelta(hours=1)

ACTIVITY_ICONS = {
    "כדורגל": "⚽", "פוקר": "✈️", "בירה": "🍺", "אוכל": "🍽️",
    "ארוחה": "🍽️", "ארוחת ערב": "🍽️", "ארוחת צהריים": "🍽️",
    "ארוחת בוקר": "🍳", "גיבוש": "🤝", "פגישה": "💼", "קפה": "☕",
    "סרט": "🎬", "ים": "🏖️", "טיול": "🥾", "ספורט": "🏃",
    "כדורסל": "🏀", "טניס": "🎾", "יום הולדת": "🎂", "מסיבה": "🎉",
    "בר": "🍻", "גיימינג": "🎮", "משחק": "🎮",
}

# ---- פונקציות עזר ----

def get_credentials():
    import json
    creds = None

    # Streamlit Cloud: קרא מ-secrets
    if 'GOOGLE_TOKEN' in st.secrets:
        creds = Credentials.from_authorized_user_info(
            json.loads(st.secrets['GOOGLE_TOKEN']), SCOPES
        )
    elif os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if os.path.exists('token.json'):
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
        else:
            st.error("לא נמצא token.json תקין. הרץ python app.py פעם אחת לאימות.")
            st.stop()
    return creds

def get_oauth_client_info():
    if 'WEB_CLIENT_ID' in st.secrets:
        return st.secrets['WEB_CLIENT_ID'], st.secrets['WEB_CLIENT_SECRET']
    if 'GOOGLE_TOKEN' in st.secrets:
        token_data = json.loads(st.secrets['GOOGLE_TOKEN'])
        return token_data['client_id'], token_data['client_secret']
    if os.path.exists('token.json'):
        with open('token.json') as f:
            token_data = json.load(f)
        return token_data['client_id'], token_data['client_secret']
    raise Exception("לא נמצא GOOGLE_TOKEN")

def get_google_auth_url():
    import urllib.parse
    client_id, _ = get_oauth_client_info()
    redirect_uri = st.secrets.get('REDIRECT_URI', 'http://localhost:8501')
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': ' '.join(SCOPES),
        'access_type': 'offline',
        'prompt': 'select_account consent',
    }
    return 'https://accounts.google.com/o/oauth2/auth?' + urllib.parse.urlencode(params)

def exchange_code_for_creds(code):
    import requests as req_lib, json
    client_id, client_secret = get_oauth_client_info()
    redirect_uri = st.secrets.get('REDIRECT_URI', 'http://localhost:8501')
    resp = req_lib.post('https://oauth2.googleapis.com/token', data={
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    })
    resp.raise_for_status()
    token = resp.json()
    creds = Credentials(
        token=token['access_token'],
        refresh_token=token.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    return creds

def get_user_email(creds):
    import requests as req_lib
    resp = req_lib.get('https://www.googleapis.com/oauth2/v2/userinfo',
                       headers={'Authorization': f'Bearer {creds.token}'})
    return resp.json().get('email', '') if resp.ok else ''

def get_cookie_manager():
    return stx.CookieManager(key="boko_cookies")

def save_creds_to_cookie(cookie_manager, creds, email):
    client_id, client_secret = get_oauth_client_info()
    data = json.dumps({
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'client_id': client_id,
        'client_secret': client_secret,
        'email': email,
    })
    cookie_manager.set('boko_user', data, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))

def load_creds_from_cookie(cookie_manager):
    raw = cookie_manager.get('boko_user')
    if not raw:
        return None, None
    try:
        data = json.loads(raw)
        creds = Credentials(
            token=data['token'],
            refresh_token=data['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=data['client_id'],
            client_secret=data['client_secret'],
            scopes=SCOPES,
        )
        return creds, data.get('email', '')
    except Exception:
        return None, None

def round_up_to_half_hour(dt):
    minutes = dt.minute
    if minutes == 0:
        return dt.replace(second=0, microsecond=0)
    elif minutes <= 30:
        return dt.replace(minute=30, second=0, microsecond=0)
    else:
        return (dt + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

def get_duration(mission):
    mission_lower = mission.lower()
    for keyword, hours in ACTIVITY_DURATIONS.items():
        if keyword in mission_lower:
            return hours
    return 2.0  # ברירת מחדל: 2 שעות

def get_min_people(mission):
    mission_lower = mission.lower()
    for keyword, min_p in ACTIVITY_MIN_PEOPLE.items():
        if keyword in mission_lower:
            return min_p
    return 3

def get_activity_icon(mission):
    mission_lower = mission.lower()
    for keyword, icon in ACTIVITY_ICONS.items():
        if keyword in mission_lower:
            return icon
    return "📌"

def is_miluim_shift(slot_start, slot_end):
    local_start = slot_start.astimezone(ISRAEL_TZ)
    local_end = slot_end.astimezone(ISRAEL_TZ)
    for s_start, s_end in MILUIM_SHIFTS:
        # בדוק אם האירוע מתחיל בשעת משמרת ומסתיים בשעת סיום המשמרת (עם סבילות שעה)
        if local_start.hour == s_start:
            expected_end = s_end if s_end != 0 else 24
            actual_end = local_end.hour if local_end.hour != 0 else 24
            if abs(actual_end - expected_end) <= 1:
                return True
    return False

def get_unavailability_reason(busy_slots, event_start, event_end):
    """מחזיר את סיבת אי-הזמינות, או None אם פנוי."""
    miluim = [(s, e) for s, e in busy_slots if is_miluim_shift(s, e)]
    regular = [(s, e) for s, e in busy_slots if not is_miluim_shift(s, e)]

    for bs, be in regular:
        if max(event_start, bs) < min(event_end, be):
            return f"אירוע אחר ({bs.astimezone(ISRAEL_TZ).strftime('%H:%M')}–{be.astimezone(ISRAEL_TZ).strftime('%H:%M')})"

    for rs, re in miluim:
        if max(event_start, rs) < min(event_end, re):
            return f"במשמרת מילואים ({rs.astimezone(ISRAEL_TZ).strftime('%H:%M')}–{re.astimezone(ISRAEL_TZ).strftime('%H:%M')})"
        if re <= event_start and event_start < re + AFTER_SHIFT_BUFFER:
            return f"סיים משמרת ב-{re.astimezone(ISRAEL_TZ).strftime('%H:%M')}, צריך 45 דק׳ מנוחה"
        if rs >= event_end and event_end > rs - BEFORE_SHIFT_BUFFER:
            return f"משמרת מתחילה ב-{rs.astimezone(ISRAEL_TZ).strftime('%H:%M')}, צריך לצאת שעה לפני"

    return None

def parse_time_range(when_text):
    """מפרסר טקסט חופשי לטווח זמן חיפוש."""
    import re
    now = datetime.datetime.now(datetime.timezone.utc)
    local_now = now.astimezone(ISRAEL_TZ)
    t = when_text.strip()

    def local_to_utc(dt):
        return dt.astimezone(datetime.timezone.utc)

    if "שבוע הבא" in t:
        days_until_sunday = (6 - local_now.weekday()) % 7 + 1
        start = (local_now + datetime.timedelta(days=days_until_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=7)
        return local_to_utc(start), local_to_utc(end)

    if "שבועיים" in t:
        start = local_now + datetime.timedelta(days=14)
        end = start + datetime.timedelta(days=7)
        return local_to_utc(start), local_to_utc(end)

    if "סוף השבוע" in t or "שישי" in t or "שבת" in t:
        days_until_fri = (4 - local_now.weekday()) % 7
        if days_until_fri == 0 and local_now.hour >= 18:
            days_until_fri = 7
        start = (local_now + datetime.timedelta(days=days_until_fri)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=2)
        return local_to_utc(start), local_to_utc(end)

    if "מחר" in t:
        start = (local_now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=1)
        return local_to_utc(start), local_to_utc(end)

    if "חודש" in t:
        start = local_now + datetime.timedelta(days=30)
        end = start + datetime.timedelta(days=14)
        return local_to_utc(start), local_to_utc(end)

    # "בעוד X שבועות"
    m = re.search(r'(?:בעוד|לעוד|עוד)\s+(\d+)\s+שבועות', t)
    if m:
        weeks = int(m.group(1))
        start = local_now + datetime.timedelta(weeks=weeks)
        end = start + datetime.timedelta(days=7)
        return local_to_utc(start), local_to_utc(end)

    # "בעוד X ימים"
    m = re.search(r'(?:בעוד|לעוד|עוד)\s+(\d+)\s+ימים', t)
    if m:
        days = int(m.group(1))
        start = local_now + datetime.timedelta(days=days)
        end = start + datetime.timedelta(days=3)
        return local_to_utc(start), local_to_utc(end)

    # ברירת מחדל: 3 ימים קרובים
    return now, now + datetime.timedelta(days=3)


def parse_query(query):
    """מחלץ פעילות וטווח זמן מטקסט חופשי כמו 'בירה לעוד שבועיים'."""
    query_lower = query.lower().strip()
    # כל מילות המפתח לפעילויות, ממויינות מהארוכה לקצרה למניעת התאמה חלקית
    all_keywords = sorted(
        list(ACTIVITY_DURATIONS.keys()) + list(ACTIVITY_ICONS.keys()),
        key=lambda x: -len(x)
    )
    mission = None
    when_text = query_lower
    for kw in all_keywords:
        if kw in query_lower:
            mission = kw
            when_text = query_lower.replace(kw, '').strip(' ,.-לב')
            break
    if mission is None:
        mission = query.strip()
        when_text = ""
    return mission, when_text

def create_calendar_event(service, mission, start_time, end_time, attendee_emails):
    """יוצר אירוע ב-Google Calendar ושולח זימון לכל המשתתפים."""
    icon = get_activity_icon(mission)
    event = {
        'summary': f"{icon} {mission}",
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'Asia/Jerusalem'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'Asia/Jerusalem'},
        'attendees': [{'email': email} for email in attendee_emails],
        'reminders': {'useDefault': True},
        'guestsCanSeeOtherGuests': True,
    }
    return service.events().insert(
        calendarId='primary',
        body=event,
        sendUpdates='all'
    ).execute()

EVENING_ONLY = ["בירה", "בר", "פוקר", "poker", "מסעדה", "ארוחת ערב", "אוכל", "ארוחה", "מסיבה"]

def build_shift_prompt(today):
    return f"""זוהי הודעת וואטסאפ עם סידור משמרות מילואים. כל המשמרות בהודעה הן עבורי.
השנה הנוכחית היא {today.year}.

פורמט ההודעה:
- כל משמרת מסומנת בכוכביות *...*
- תאריך: "ביום [שם יום] DD.MM" או "בלילה שבין יום [יום] DD.MM ליום [יום] DD.MM"
- שעות: "נתחיל ב-HH:MM, נסיים ב-HH:MM" (גם ללא מקף כמו "נתחיל ב2:00")
- סוג: "גיחה כבדה" = משמרת רגילה, "טיסה בכוננות X'" = כוננות
- עבור לילה שבין תאריכים - תאריך ההתחלה הוא הראשון מהשניים

החזר JSON בלבד ללא טקסט נוסף:
{{"shifts": [{{"date": "DD/MM/YYYY", "start_time": "HH:MM", "end_time": "HH:MM", "description": "תיאור"}}]}}
אם אין משמרות, החזר: {{"shifts": []}}"""

def parse_shifts_from_gemini(text):
    import json
    text = text.strip()
    if '```' in text:
        text = text.split('```')[1]
        if text.startswith('json'):
            text = text[4:]
    return json.loads(text.strip())

def _gemini_post(url, body):
    import requests, time
    for attempt in range(3):
        resp = requests.post(url, json=body)
        if resp.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp

def analyze_shift_image(image_bytes, image_type):
    import base64
    api_key = st.secrets.get('GEMINI_API_KEY', '')
    if not api_key:
        raise Exception("GEMINI_API_KEY לא הוגדר ב-Secrets")
    today = datetime.datetime.now()
    prompt = build_shift_prompt(today)
    image_b64 = base64.b64encode(image_bytes).decode()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    body = {"contents": [{"parts": [
        {"inline_data": {"mime_type": image_type, "data": image_b64}},
        {"text": prompt}
    ]}]}
    resp = _gemini_post(url, body)
    return parse_shifts_from_gemini(resp.json()['candidates'][0]['content']['parts'][0]['text'])

def parse_shifts_from_text_regex(message_text):
    """פרסר ישיר לפורמט הודעות וואטסאפ של סידור משמרות, ללא Gemini."""
    import re
    year = datetime.datetime.now().year
    shifts = []

    # חלץ כל בלוק משמרת (שורה שמוקפת בכוכביות + שורות תיאור אחריה)
    blocks = re.split(r'\n(?=\*)', message_text.strip())

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue

        header = lines[0].strip().strip('*')

        # חלץ שעות
        start_match = re.search(r'נתחיל ב[-]?(\d{1,2}:\d{2}|\d{1,2})', header)
        end_match = re.search(r'נסיים ב[-]?(\d{1,2}:\d{2}|\d{1,2})', header)
        if not start_match or not end_match:
            continue

        start_time = start_match.group(1)
        end_time = end_match.group(1)
        if ':' not in start_time:
            start_time += ':00'
        if ':' not in end_time:
            end_time += ':00'

        # תאריך לילה: "בלילה שבין יום X DD.MM ליום Y DD.MM"
        night_match = re.search(r'בלילה שבין יום \S+ (\d{1,2})\.(\d{1,2})', header)
        # תאריך רגיל: "ביום X DD.MM"
        day_match = re.search(r'ביום \S+ (\d{1,2})\.(\d{1,2})', header)

        if night_match:
            day, month = night_match.group(1), night_match.group(2)
        elif day_match:
            day, month = day_match.group(1), day_match.group(2)
        else:
            continue

        date_str = f"{int(day):02d}/{int(month):02d}/{year}"

        # תיאור: השורה הראשונה אחרי הכותרת שאינה "מפקד" / "הערה"
        description = "משמרת מילואים"
        for line in lines[1:]:
            l = line.strip()
            if l and not l.startswith('מפקד') and not l.startswith('הערה') and not l.startswith('נא ל'):
                description = l
                break

        shifts.append({
            "date": date_str,
            "start_time": start_time,
            "end_time": end_time,
            "description": description,
        })

    return {"shifts": shifts}

def analyze_shift_text(message_text):
    # נסה קודם פרסר ישיר
    result = parse_shifts_from_text_regex(message_text)
    if result.get('shifts'):
        return result

    # אם לא הצליח, נסה Gemini
    api_key = st.secrets.get('GEMINI_API_KEY', '')
    if not api_key:
        raise Exception("לא זוהו משמרות בטקסט")
    today = datetime.datetime.now()
    prompt = build_shift_prompt(today) + f"\n\nהטקסט:\n{message_text}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = _gemini_post(url, body)
    return parse_shifts_from_gemini(resp.json()['candidates'][0]['content']['parts'][0]['text'])

def find_free_slots(service, duration, mission, search_start, search_end, max_results=21):
    """מוצא עד max_results חלונות פנויים."""
    is_poker = "פוקר" in mission.lower() or "poker" in mission.lower()
    is_evening_only = any(kw in mission.lower() for kw in EVENING_ONLY)
    min_people = get_min_people(mission)
    all_people = list(FRIENDS.values()) + ["primary"]
    email_to_name = {v: k for k, v in FRIENDS.items()}
    email_to_name["primary"] = "אני"

    body = {
        "timeMin": search_start.isoformat(),
        "timeMax": search_end.isoformat(),
        "items": [{"id": p} for p in all_people]
    }

    fb_result = service.freebusy().query(body=body).execute()
    calendars = fb_result.get('calendars', {})

    busy_per_person = {}
    for person in all_people:
        slots = []
        for slot in calendars.get(person, {}).get('busy', []):
            start = datetime.datetime.fromisoformat(slot['start'].replace('Z', '+00:00'))
            end = datetime.datetime.fromisoformat(slot['end'].replace('Z', '+00:00'))
            slots.append((start, end))
        busy_per_person[person] = sorted(slots)

    change_points = set()
    change_points.add(round_up_to_half_hour(search_start))
    for slots in busy_per_person.values():
        for s, e in slots:
            change_points.add(round_up_to_half_hour(s))
            change_points.add(round_up_to_half_hour(e))
            if is_miluim_shift(s, e):
                change_points.add(round_up_to_half_hour(e + AFTER_SHIFT_BUFFER))
                change_points.add(round_up_to_half_hour(s - BEFORE_SHIFT_BUFFER))

    results = []
    possible_start = round_up_to_half_hour(search_start)

    while possible_start + datetime.timedelta(hours=duration) <= search_end and len(results) < max_results:
        local_start = possible_start.astimezone(ISRAEL_TZ)

        # פעילויות ערב רק אחרי 18:00
        if is_evening_only and local_start.hour < 18:
            next_evening = local_start.replace(hour=18, minute=0, second=0, microsecond=0)
            if next_evening <= local_start:
                next_evening += datetime.timedelta(days=1)
            possible_start = next_evening.astimezone(datetime.timezone.utc)
            continue

        # אין אירועים בין 01:00 ל-08:00
        if 1 <= local_start.hour < 8:
            next_day = local_start.replace(hour=8, minute=0, second=0, microsecond=0)
            possible_start = next_day.astimezone(datetime.timezone.utc)
            continue

        potential_end = possible_start + datetime.timedelta(hours=duration)

        # אירוע לא יכול להסתיים אחרי 01:00 בלילה
        local_end = potential_end.astimezone(ISRAEL_TZ)
        if 1 <= local_end.hour < 8:
            next_day = (local_start + datetime.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
            possible_start = next_day.astimezone(datetime.timezone.utc)
            continue

        if is_poker:
            max_start = local_start.replace(hour=20, minute=30, second=0, microsecond=0)
            if local_start > max_start:
                next_day = (local_start + datetime.timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
                possible_start = round_up_to_half_hour(next_day.astimezone(datetime.timezone.utc))
                continue

        unavailable = {}
        free_count = 0
        for person in all_people:
            reason = get_unavailability_reason(busy_per_person[person], possible_start, potential_end)
            # Fallback: miluim after-buffer check for "primary" (in case is_miluim_shift missed it)
            if reason is None and person == "primary":
                for rs, re_t in busy_per_person.get("primary", []):
                    if is_miluim_shift(rs, re_t) and re_t <= possible_start < re_t + AFTER_SHIFT_BUFFER:
                        reason = f"סיים משמרת ב-{re_t.astimezone(ISRAEL_TZ).strftime('%H:%M')}, זמין מ-{(re_t + AFTER_SHIFT_BUFFER).astimezone(ISRAEL_TZ).strftime('%H:%M')}"
                        break
            if reason is None:
                free_count += 1
            else:
                unavailable[email_to_name[person]] = reason

        if free_count >= min_people and "אני" not in unavailable:
            results.append((possible_start, potential_end, free_count, unavailable))
            # קפוץ לאחרי האירוע למצוא אופציה נוספת באותו יום
            possible_start = round_up_to_half_hour(potential_end)
            continue

        next_points = sorted(p for p in change_points if p > possible_start)
        if next_points:
            possible_start = next_points[0]
        else:
            possible_start += datetime.timedelta(minutes=30)

    return results

# ---- UI ----

st.set_page_config(page_title="Boko Agent", page_icon="✈️", layout="centered")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Heebo', sans-serif;
        direction: rtl;
    }

    .stApp {
        background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
        min-height: 100vh;
    }

    .hero {
        text-align: center;
        padding: 3rem 1rem 2rem;
    }
    .hero h1 {
        font-size: 3.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #4fc3f7, #7c4dff, #e040fb);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem;
    }
    .hero p {
        color: #8892a4;
        font-size: 1.1rem;
        font-weight: 300;
    }

    .result-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(76, 195, 247, 0.25);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-right: 4px solid #4fc3f7;
    }
    .result-card h3 {
        color: #4fc3f7;
        font-size: 1.1rem;
        margin-bottom: 0.5rem;
    }
    .result-time {
        font-size: 1.6rem;
        font-weight: 700;
        color: #ffffff;
    }
    .result-count {
        font-size: 0.95rem;
        color: #8892a4;
        margin-top: 0.3rem;
    }
    .unavail-item {
        background: rgba(255,80,80,0.08);
        border-radius: 8px;
        padding: 0.4rem 0.8rem;
        margin: 0.3rem 0;
        color: #ff6b6b;
        font-size: 0.9rem;
    }
    .avail-badge {
        background: rgba(0,200,100,0.12);
        border-radius: 8px;
        padding: 0.4rem 0.8rem;
        color: #00c864;
        font-size: 0.9rem;
        display: inline-block;
    }

    /* שדות קלט */
    .stTextInput input {
        background: rgba(255,255,255,0.07) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 12px !important;
        color: #111111 !important;
        font-family: 'Heebo', sans-serif !important;
        font-size: 1rem !important;
        padding: 0.7rem 1rem !important;
        direction: rtl !important;
    }
    .stTextInput input:focus {
        border-color: #4fc3f7 !important;
        box-shadow: 0 0 0 2px rgba(79,195,247,0.2) !important;
    }
    .stTextInput [data-testid="InputInstructions"] {
        display: none !important;
    }
    .stTextInput label {
        color: #b0bec5 !important;
        font-family: 'Heebo', sans-serif !important;
        font-size: 0.95rem !important;
    }

    /* כפתורים */
    .stButton > button {
        border-radius: 12px !important;
        font-family: 'Heebo', sans-serif !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4fc3f7, #7c4dff) !important;
        border: none !important;
        color: white !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(79,195,247,0.35) !important;
    }
    .stButton > button:not([kind="primary"]) {
        background: rgba(79,195,247,0.1) !important;
        border: 1px solid rgba(79,195,247,0.4) !important;
        color: #4fc3f7 !important;
    }

    /* כפתור חיפוש ירוק */
    .stFormSubmitButton > button[kind="primary"] {
        background: #00c864 !important;
        border-color: #00c864 !important;
        color: white !important;
    }
    .stFormSubmitButton > button[kind="primary"]:hover {
        background: #00a050 !important;
        border-color: #00a050 !important;
    }

    /* הסתר מרכיבי Streamlit מיותרים */
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 0 !important; max-width: 720px;}

    /* expander */
    .streamlit-expanderHeader {
        background: rgba(255,255,255,0.04) !important;
        border-radius: 12px !important;
        color: #e0e0e0 !important;
        font-family: 'Heebo', sans-serif !important;
    }
</style>
""", unsafe_allow_html=True)

# Hero
st.markdown("""
<div class="hero">
    <h1>✈️ Boko Agent</h1>
    <p>מזהה חלונות זמן פנויים תוך התחשבות במשמרות מילואים</p>
</div>
""", unsafe_allow_html=True)

# כרטיס חיפוש
_, col, _ = st.columns([1, 10, 1])
with col:
    with st.form("search_form"):
        query = st.text_input("", placeholder="למשל: בירה לעוד שבועיים, פוקר שבוע הבא, כדורגל סוף השבוע...", label_visibility="collapsed")
        search_btn = st.form_submit_button("🔍  מצא זמן פנוי", type="primary", use_container_width=True)

if search_btn:
    with st.spinner("סורק יומנים..."):
        try:
            mission, when_text = parse_query(query)
            duration = get_duration(mission)
            search_start, search_end = parse_time_range(when_text or "")
            creds = get_credentials()
            service = build('calendar', 'v3', credentials=creds)
            slots = find_free_slots(service, duration, mission, search_start, search_end)
            st.session_state['results'] = slots
            st.session_state['mission'] = mission
        except Exception as e:
            st.error(f"שגיאה: {e}")
            st.session_state['results'] = []

if 'results' in st.session_state and st.session_state['results'] is not None:
    slots = st.session_state['results']
    mission = st.session_state.get('mission', '')
    icon = get_activity_icon(mission)
    total = len(FRIENDS) + 1
    min_p = get_min_people(mission)

    HEB_DAYS = {0: "שני", 1: "שלישי", 2: "רביעי", 3: "חמישי", 4: "שישי", 5: "שבת", 6: "ראשון"}

    if slots:
        st.markdown(f"<p style='color:#4fc3f7; font-size:1.1rem; font-weight:600; text-align:center;'>✅ מצאתי חלונות רלוונטיים</p>", unsafe_allow_html=True)

        # קבץ לפי יום
        from collections import defaultdict
        days_dict = defaultdict(list)
        slot_index = {}
        for i, slot in enumerate(slots, 1):
            day_key = slot[0].astimezone(ISRAEL_TZ).strftime('%Y-%m-%d')
            days_dict[day_key].append(slot)
            slot_index[id(slot)] = i

        for day_key, day_slots in days_dict.items():
            local_start = day_slots[0][0].astimezone(ISRAEL_TZ)
            day_name = HEB_DAYS[local_start.weekday()]
            date_str = local_start.strftime('%d/%m')

            st.markdown(f"""
            <div style='background:rgba(79,195,247,0.08); border-right:3px solid #4fc3f7;
                        padding:0.5rem 1rem; margin:0.8rem 0 0.3rem 0; border-radius:8px; direction:rtl;'>
                <span style='color:#4fc3f7; font-weight:700; font-size:1rem;'>יום {day_name} &nbsp;·&nbsp; {date_str}</span>
            </div>
            """, unsafe_allow_html=True)

            for slot in day_slots:
                start_time, end_time, free_count, unavailable = slot
                i = slot_index[id(slot)]
                time_str = f"{start_time.astimezone(ISRAEL_TZ).strftime('%H:%M')}–{end_time.astimezone(ISRAEL_TZ).strftime('%H:%M')}"
                available_names = [name for name in FRIENDS if name not in unavailable]
                if "אני" not in unavailable:
                    available_names.append("אני")
                names_str = "כולם" if len(unavailable) == 0 else ", ".join(available_names)

                col1, col2, col3 = st.columns([1.5, 2.5, 1.5])
                with col1:
                    st.markdown(f"<div style='color:#4fc3f7; font-size:1.1rem; font-weight:600; padding-top:6px;'>{time_str}</div>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"<div style='color:#00c864; padding-top:6px;'>✅ {names_str}</div>", unsafe_allow_html=True)
                with col3:
                    available_emails = [email for name, email in FRIENDS.items() if name not in unavailable]
                    if st.button(f"📨 זמן", key=f"invite_{i}"):
                        try:
                            creds = st.session_state.get('user_creds') or get_credentials()
                            service = build('calendar', 'v3', credentials=creds)
                            event = create_calendar_event(service, mission, start_time, end_time, available_emails)
                            st.success(f"✅ זימון נשלח ל-{len(available_emails)} אנשים!")
                            st.markdown(f"[פתח ב-Google Calendar]({event.get('htmlLink')})")
                            st.session_state['results'] = None
                        except Exception as e:
                            st.error(f"שגיאה: {e}")
    elif slots == []:
        st.markdown("<p style='color:#ff6b6b; text-align:center; font-size:1.1rem;'>❌ אין חלונות זמן רלוונטיים</p>", unsafe_allow_html=True)

# ---- טיפול ב-OAuth callback ----
PENDING_AUTH_FILE = '.pending_auth.json'

params = st.query_params
if 'code' in params and not st.session_state.get('_oauth_done'):
    st.session_state['_oauth_done'] = True
    code = params['code']
    st.query_params.clear()
    try:
        creds = exchange_code_for_creds(code)
        email = get_user_email(creds)
        client_id, client_secret = get_oauth_client_info()
        # שמור לקובץ זמני — עמיד בפני איפוס session
        with open(PENDING_AUTH_FILE, 'w') as f:
            json.dump({'token': creds.token, 'refresh_token': creds.refresh_token,
                       'client_id': client_id, 'client_secret': client_secret, 'email': email}, f)
        st.session_state['user_creds'] = creds
        st.session_state['user_email'] = email
    except Exception as e:
        st.session_state.pop('_oauth_done', None)
        st.session_state['_auth_error'] = str(e)

# טעינה מקובץ זמני (אם session התאפס אחרי OAuth)
if 'user_creds' not in st.session_state and not st.session_state.get('_logged_out') and os.path.exists(PENDING_AUTH_FILE):
    try:
        with open(PENDING_AUTH_FILE) as f:
            data = json.load(f)
        creds = Credentials(
            token=data['token'], refresh_token=data['refresh_token'],
            token_uri='https://oauth2.googleapis.com/token',
            client_id=data['client_id'], client_secret=data['client_secret'], scopes=SCOPES,
        )
        st.session_state['user_creds'] = creds
        st.session_state['user_email'] = data.get('email', '')
    except Exception:
        pass

# טעינה אוטומטית מ-token.json (למשתמש המקומי)
if 'user_creds' not in st.session_state and not st.session_state.get('_logged_out') and os.path.exists('token.json'):
    try:
        auto_creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        if auto_creds and auto_creds.expired and auto_creds.refresh_token:
            auto_creds.refresh(Request())
        if auto_creds and auto_creds.valid:
            email_resp = __import__('requests').get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {auto_creds.token}'}
            )
            auto_email = email_resp.json().get('email', '') if email_resp.ok else ''
            st.session_state['user_creds'] = auto_creds
            st.session_state['user_email'] = auto_email
    except Exception:
        pass

# Cookie manager (לצורך persistent login לחברים)
cookie_manager = get_cookie_manager()

# ---- סעיף העלאת סידור מילואים ----
st.markdown("<hr style='border-color:rgba(255,255,255,0.1); margin:2rem 0;'>", unsafe_allow_html=True)
st.markdown("""
<div style='text-align:center; padding:0.5rem 0 1rem 0;'>
    <span style='color:#7c4dff; font-size:1.2rem; font-weight:700;'>🪖 ייבא משמרות מילואים</span><br>
    <span style='color:#8892a4; font-size:0.9rem;'>הדבק את הטקסט מהוואטסאפ</span>
</div>
""", unsafe_allow_html=True)

if '_auth_error' in st.session_state:
    st.error(f"שגיאת התחברות: {st.session_state['_auth_error']}")

if 'user_creds' not in st.session_state:
    auth_url = get_google_auth_url()
    st.markdown(f"""
    <div style='text-align:center; padding:0.3rem 0 0.8rem 0;'>
        <div style='color:#8892a4; font-size:0.85rem; margin-bottom:0.5rem;'>
            ⚠️ התחבר כדי שהמשמרות יתווספו ליומן שלך
        </div>
        <a href="{auth_url}" target="_top"
           style='background:linear-gradient(135deg,#4fc3f7,#7c4dff); color:white;
                  padding:0.6rem 1.5rem; border-radius:12px; font-weight:600;
                  font-size:1rem; text-decoration:none; font-family:Heebo,sans-serif;'>
            🔐 התחבר עם Google
        </a>
    </div>
    """, unsafe_allow_html=True)

# ---- הזנת משמרות בטקסט ----
with st.form("shift_text_form"):
    msg_text = st.text_area("הדבק את הודעת הוואטסאפ כאן", height=200, placeholder="היי פרוכטר,\nיש מספר כוכביות:\n*ביום שלישי 17.03...*", key="shift_text")
    analyze_text_btn = st.form_submit_button("🔍 נתח טקסט", type="primary", use_container_width=True)
if analyze_text_btn and msg_text:
    with st.spinner("מנתח את הסידור..."):
        try:
            result = analyze_shift_text(msg_text)
            st.session_state['detected_shifts'] = result.get('shifts', [])
        except Exception as e:
            st.error(f"שגיאה בניתוח: {e}")

if 'detected_shifts' in st.session_state and st.session_state['detected_shifts']:
    shifts = st.session_state['detected_shifts']
    st.markdown(f"<p style='color:#7c4dff; font-weight:600; text-align:center;'>✅ זיהיתי {len(shifts)} משמרות</p>", unsafe_allow_html=True)

    HEB_DAYS2 = {0: "שני", 1: "שלישי", 2: "רביעי", 3: "חמישי", 4: "שישי", 5: "שבת", 6: "ראשון"}
    for shift in shifts:
        try:
            d, m, y = shift['date'].split('/')
            dt = datetime.datetime(int(y), int(m), int(d))
            day_name = HEB_DAYS2[dt.weekday()]
        except:
            day_name = ""
        st.markdown(f"""
        <div style='background:rgba(124,77,255,0.08); border-right:3px solid #7c4dff;
                    padding:0.5rem 1rem; margin:0.4rem 0; border-radius:8px; direction:rtl;'>
            <span style='color:#7c4dff; font-weight:700;'>יום {day_name} {shift['date']}</span>
            &nbsp;·&nbsp;
            <span style='color:#fff;'>{shift['start_time']}–{shift['end_time']}</span>
            &nbsp;·&nbsp;
            <span style='color:#8892a4;'>{shift.get('description','משמרת מילואים')}</span>
        </div>
        """, unsafe_allow_html=True)

    if st.button("📅 הוסף את כל המשמרות ללוז", type="primary", use_container_width=True, key="add_shifts_btn"):
        with st.spinner("מוסיף משמרות..."):
            try:
                creds = st.session_state.get('user_creds') or get_credentials()
                service = build('calendar', 'v3', credentials=creds)
                added = 0
                for shift in shifts:
                    d, m, y = shift['date'].split('/')
                    start_dt = datetime.datetime(int(y), int(m), int(d),
                                                  int(shift['start_time'].split(':')[0]),
                                                  int(shift['start_time'].split(':')[1]),
                                                  tzinfo=datetime.timezone(datetime.timedelta(hours=2)))
                    end_dt = datetime.datetime(int(y), int(m), int(d),
                                                int(shift['end_time'].split(':')[0]),
                                                int(shift['end_time'].split(':')[1]),
                                                tzinfo=datetime.timezone(datetime.timedelta(hours=2)))
                    if end_dt <= start_dt:
                        end_dt += datetime.timedelta(days=1)
                    desc = shift.get('description', '')
                    is_standby = 'כוננות' in desc or 'כוננות' in shift.get('start_time', '')
                    title = "🪖 מילואים כוננות" if is_standby else "🪖 מילואים"
                    event = {
                        'summary': title,
                        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Jerusalem'},
                        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Jerusalem'},
                    }
                    service.events().insert(calendarId='primary', body=event).execute()
                    added += 1
                st.success(f"✅ {added} משמרות נוספו ללוז!")
                st.session_state['detected_shifts'] = []
            except Exception as e:
                st.error(f"שגיאה: {e}")

# ---- פס מחובר תחתון ----
if 'user_creds' in st.session_state:
    email = st.session_state.get('user_email', '')
    st.markdown(f"""
    <style>
    .bottom-bar {{
        position: fixed;
        bottom: 0; left: 0; right: 0;
        background: rgba(18,18,28,0.95);
        border-top: 1px solid rgba(0,200,100,0.3);
        padding: 0.5rem 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        z-index: 9999;
        direction: rtl;
    }}
    .bottom-bar-logout {{
        background: transparent;
        border: 1px solid rgba(255,100,100,0.4);
        color: #ff6b6b;
        border-radius: 8px;
        padding: 0.3rem 0.9rem;
        cursor: pointer;
        font-family: Heebo, sans-serif;
        font-size: 0.85rem;
    }}
    .bottom-bar-logout:hover {{ background: rgba(255,100,100,0.1); }}
    </style>
    <div class="bottom-bar">
        <span style="color:white; font-family:Heebo,sans-serif;">✅ {"מחובר כ: " + email.strip() if email.strip() else "מחובר"}</span>
        <form action="" method="get">
            <button class="bottom-bar-logout" name="_logout" value="1" type="submit">התנתק</button>
        </form>
    </div>
    """, unsafe_allow_html=True)

    if st.query_params.get("_logout") == "1":
        del st.session_state['user_creds']
        del st.session_state['user_email']
        st.session_state.pop('detected_shifts', None)
        st.session_state['_logged_out'] = True
        if os.path.exists(PENDING_AUTH_FILE):
            os.remove(PENDING_AUTH_FILE)
        try:
            cookie_manager.delete('boko_user')
        except Exception:
            pass
        st.query_params.clear()
        st.rerun()
