import os.path
import datetime
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
]

# --- שם: מייל ---
FRIENDS = {
    "חבר 1": "friend1@gmail.com",
    "חבר 2": "friend2@gmail.com",
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
AFTER_SHIFT_BUFFER = datetime.timedelta(minutes=45)
BEFORE_SHIFT_BUFFER = datetime.timedelta(hours=1)

ACTIVITY_ICONS = {
    "כדורגל": "⚽", "פוקר": "🃏", "בירה": "🍺", "אוכל": "🍽️",
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
    duration_h = (slot_end - slot_start).total_seconds() / 3600
    if abs(duration_h - 4) > 0.25:
        return False
    local_start = slot_start.astimezone()
    return local_start.hour in [s for s, _ in MILUIM_SHIFTS]

def get_unavailability_reason(busy_slots, event_start, event_end):
    """מחזיר את סיבת אי-הזמינות, או None אם פנוי."""
    miluim = [(s, e) for s, e in busy_slots if is_miluim_shift(s, e)]
    regular = [(s, e) for s, e in busy_slots if not is_miluim_shift(s, e)]

    for bs, be in regular:
        if max(event_start, bs) < min(event_end, be):
            return f"אירוע אחר ({bs.astimezone().strftime('%H:%M')}–{be.astimezone().strftime('%H:%M')})"

    for rs, re in miluim:
        if max(event_start, rs) < min(event_end, re):
            return f"במשמרת מילואים ({rs.astimezone().strftime('%H:%M')}–{re.astimezone().strftime('%H:%M')})"
        if re <= event_start and event_start < re + AFTER_SHIFT_BUFFER:
            return f"סיים משמרת ב-{re.astimezone().strftime('%H:%M')}, צריך 45 דק׳ מנוחה"
        if rs >= event_end and event_end > rs - BEFORE_SHIFT_BUFFER:
            return f"משמרת מתחילה ב-{rs.astimezone().strftime('%H:%M')}, צריך לצאת שעה לפני"

    return None

def parse_time_range(when_text):
    """מפרסר טקסט חופשי לטווח זמן חיפוש."""
    import re
    now = datetime.datetime.now(datetime.timezone.utc)
    local_now = now.astimezone()
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

def find_free_slots(service, duration, mission, search_start, search_end, max_results=3):
    """מוצא עד max_results חלונות פנויים."""
    is_poker = "פוקר" in mission.lower() or "poker" in mission.lower()
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
        local_start = possible_start.astimezone()

        # אין אירועים בין 01:00 ל-08:00
        if 1 <= local_start.hour < 8:
            next_day = local_start.replace(hour=8, minute=0, second=0, microsecond=0)
            possible_start = next_day.astimezone(datetime.timezone.utc)
            continue

        potential_end = possible_start + datetime.timedelta(hours=duration)

        # אירוע לא יכול להסתיים אחרי 01:00 בלילה
        local_end = potential_end.astimezone()
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
            if reason is None:
                free_count += 1
            else:
                unavailable[email_to_name[person]] = reason

        if free_count >= min_people:
            results.append((possible_start, potential_end, free_count, unavailable))
            # קפוץ קדימה כדי למצוא אופציה הבאה שלא חופפת
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
    query = st.text_input("", placeholder="למשל: בירה לעוד שבועיים, פוקר שבוע הבא, כדורגל סוף השבוע...", label_visibility="collapsed")
    search_btn = st.button("🔍  מצא זמן פנוי", type="primary", disabled=not query, use_container_width=True)

if search_btn:
    with st.spinner("סורק יומנים..."):
        try:
            mission, when_text = parse_query(query)
            duration = get_duration(mission)
            search_start, search_end = parse_time_range(when_text or "")
            creds = get_credentials()
            service = build('calendar', 'v3', credentials=creds)
            slots = find_free_slots(service, duration, mission, search_start, search_end)

            icon = get_activity_icon(mission)
            total = len(FRIENDS) + 1
            min_p = get_min_people(mission)

            if slots:
                st.markdown(f"<p style='color:#4fc3f7; font-size:1.1rem; font-weight:600; text-align:center;'>✅ מצאתי חלונות רלוונטיים</p>", unsafe_allow_html=True)
                for i, (start_time, end_time, free_count, unavailable) in enumerate(slots, 1):
                    start_str = start_time.astimezone().strftime('%A %d/%m ב-%H:%M')
                    end_str = end_time.astimezone().strftime('%H:%M')

                    st.markdown(f"""
                    <div class="result-card">
                        <h3>אופציה {i} {icon}</h3>
                        <div class="result-time">{start_str} &nbsp;→&nbsp; {end_str}</div>
                        <div class="result-count">👥 {free_count} מתוך {total} פנויים (מינימום {min_p})</div>
                    </div>
                    """, unsafe_allow_html=True)

                    if unavailable:
                        st.markdown("**מי לא יכול:**")
                        for name, reason in unavailable.items():
                            st.markdown(f'<div class="unavail-item">❌ <b>{name}</b> — {reason}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="avail-badge">✅ כולם פנויים!</div>', unsafe_allow_html=True)

                    available_emails = [
                        email for name, email in FRIENDS.items()
                        if name not in unavailable
                    ]
                    if st.button(f"📨 שלח זימון לאופציה {i}", key=f"invite_{i}"):
                        try:
                            event = create_calendar_event(service, mission, start_time, end_time, available_emails)
                            st.success(f"✅ זימון נשלח ל-{len(available_emails)} אנשים!")
                            st.markdown(f"[פתח את האירוע ב-Google Calendar]({event.get('htmlLink')})")
                        except Exception as e:
                            st.error(f"שגיאה בשליחת הזימון: {e}")

                    st.markdown("<br>", unsafe_allow_html=True)
            else:
                st.markdown("<p style='color:#ff6b6b; text-align:center; font-size:1.1rem;'>❌ אין חלונות זמן רלוונטיים</p>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"שגיאה: {e}")
