import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# --- תעדכן פה את המיילים של החברים שלך ---
FRIENDS_EMAILS = [
    'friend1@gmail.com',
    'friend2@gmail.com'
]

def main():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    print("\n--- Base 44: AI Scheduling Core ---")
    mission = input("מה הפעילות? ")
    duration = float(input(f"כמה שעות ימשך ה-{mission}? "))
    
    # טווח חיפוש: מעכשיו ועד עוד 3 ימים
    now = datetime.datetime.now(datetime.timezone.utc)
    search_end = now + datetime.timedelta(days=3)

    print(f"סורק את היומנים ל-72 השעות הקרובות...")

    body = {
        "timeMin": now.isoformat(),
        "timeMax": search_end.isoformat(),
        "items": [{"id": email} for email in FRIENDS_EMAILS] + [{"id": "primary"}]
    }

    fb_result = service.freebusy().query(body=body).execute()
    calendars = fb_result.get('calendars', {})

    # איחוד כל הזמנים התפוסים של כולם לרשימה אחת
    all_busy_slots = []
    for cal_id in calendars:
        for slot in calendars[cal_id].get('busy', []):
            start = datetime.datetime.fromisoformat(slot['start'].replace('Z', '+00:00'))
            end = datetime.datetime.fromisoformat(slot['end'].replace('Z', '+00:00'))
            all_busy_slots.append((start, end))

    # מיון הזמנים התפוסים לפי שעת התחלה
    all_busy_slots.sort()

    # חיפוש החלון הפנוי הראשון
    possible_start = now
    found_slot = None

    while possible_start + datetime.timedelta(hours=duration) <= search_end:
        potential_end = possible_start + datetime.timedelta(hours=duration)
        overlap = False
        
        for busy_start, busy_end in all_busy_slots:
            # בדיקה אם החלון הפוטנציאלי מתנגש בזמן תפוס כלשהו
            if max(possible_start, busy_start) < min(potential_end, busy_end):
                overlap = True
                possible_start = busy_end # קופץ לסוף הזמן התפוס ומנסה שוב
                break
        
        if not overlap:
            found_slot = (possible_start, potential_end)
            break
        
        if not overlap: possible_start += datetime.timedelta(minutes=15)

    if found_slot:
        start_time = found_slot[0].astimezone().strftime('%d/%m ב-%H:%M')
        end_time = found_slot[1].astimezone().strftime('%H:%M')
        print(f"\n✅ נמצא זמן מושלם ל{mission}!")
        print(f"כולם פנויים ב: {start_time} עד {end_time}")
    else:
        print(f"\n❌ לא נמצא חלון פנוי של {duration} שעות ב-3 הימים הקרובים.")

if __name__ == '__main__':
    main()