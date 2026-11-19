from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
import sqlite3
import hashlib
import secrets
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

DATABASE = 'database/scheduler.db'


@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    traceback.print_exc()
    return jsonify({'error': str(e)}), 500

# Email config - set these via environment variables
SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_EMAIL")
SMTP_PASS = os.getenv("SMTP_PASSWORD")


def get_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            priority INTEGER DEFAULT 1,
            is_deadline BOOLEAN DEFAULT 0,
            color TEXT DEFAULT '#3b82f6',
            attendee_email TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day_of_week INTEGER NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # --- NEW: Activity log table ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # --- NEW: Preferences table ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            email_reminders BOOLEAN DEFAULT 1,
            reminder_minutes INTEGER DEFAULT 10,
            auto_optimize BOOLEAN DEFAULT 0,
            work_start TIME DEFAULT '09:00',
            work_end TIME DEFAULT '18:00',
            timezone TEXT DEFAULT 'Asia/Kolkata',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # --- NEW: Email reminder tracking ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_reminders_sent (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id)
        )
    ''')

    conn.commit()
    conn.close()
    migrate_db()


def migrate_db():
    """Safely add any missing columns to existing databases (handles upgrades)."""
    conn = get_db()
    cursor = conn.cursor()

    # Get existing columns in events table
    cursor.execute("PRAGMA table_info(events)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    migrations = [
        ("events", "attendee_email", "TEXT DEFAULT ''"),
    ]

    for table, col, col_def in migrations:
        if col not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                print(f"[MIGRATE] Added column '{col}' to '{table}'")
            except Exception as e:
                print(f"[MIGRATE] Skipped {table}.{col}: {e}")

    conn.commit()
    conn.close()


def log_activity(user_id, action, details=None):
    """Log user activity"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)',
        (user_id, action, json.dumps(details) if details else None)
    )
    conn.commit()
    conn.close()


def send_email(to_email, subject, html_body):
    """Send an email via SMTP"""
    if not SMTP_USER or not SMTP_PASS:
        print(f"[EMAIL MOCK] To: {to_email} | Subject: {subject}")
        return True
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


def get_user_email(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT email FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['email'] if row else None


def get_user_prefs(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM preferences WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        'email_reminders': 1,
        'reminder_minutes': 10,
        'auto_optimize': 0,
        'work_start': '09:00',
        'work_end': '18:00',
        'timezone': 'Asia/Kolkata'
    }


# ──────────────────────────────────────────────
# Background reminder thread
# ──────────────────────────────────────────────

def reminder_worker():
    """Background thread: check every 60s for upcoming events and send reminders"""
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            now = datetime.utcnow()

            # Get all users with email reminders enabled
            cursor.execute('''
                SELECT u.id as user_id, u.email, p.reminder_minutes
                FROM users u
                LEFT JOIN preferences p ON p.user_id = u.id
                WHERE p.email_reminders = 1 OR p.email_reminders IS NULL
            ''')
            users = cursor.fetchall()

            for user in users:
                reminder_mins = user['reminder_minutes'] if user['reminder_minutes'] else 10
                window_start = now + timedelta(minutes=reminder_mins - 1)
                window_end = now + timedelta(minutes=reminder_mins + 1)

                cursor.execute('''
                    SELECT e.* FROM events e
                    WHERE e.user_id = ?
                      AND e.start_time BETWEEN ? AND ?
                      AND e.id NOT IN (SELECT event_id FROM email_reminders_sent)
                ''', (user['user_id'], window_start.isoformat(), window_end.isoformat()))
                events = cursor.fetchall()

                for event in events:
                    subject = f"⏰ Reminder: {event['title']} starting soon"
                    html_body = f"""
                    <div style="font-family:'Segoe UI',sans-serif;max-width:520px;margin:auto;background:#0f1117;color:#e2e8f0;border-radius:12px;overflow:hidden;">
                      <div style="background:linear-gradient(135deg,#1e40af,#7c3aed);padding:24px 32px;">
                        <h2 style="margin:0;font-size:22px;letter-spacing:-0.5px;">ChronoSync Reminder</h2>
                        <p style="margin:6px 0 0;opacity:.8;font-size:14px;">Your event is starting in {reminder_mins} minutes</p>
                      </div>
                      <div style="padding:28px 32px;">
                        <h3 style="margin:0 0 8px;font-size:20px;color:#93c5fd;">{event['title']}</h3>
                        <p style="margin:0 0 16px;color:#94a3b8;font-size:14px;">{event['description'] or 'No description'}</p>
                        <div style="background:#1e293b;border-radius:8px;padding:16px;margin-bottom:16px;">
                          <div style="display:flex;justify-content:space-between;font-size:14px;">
                            <span style="color:#64748b;">Starts</span>
                            <span style="color:#e2e8f0;font-weight:600;">{event['start_time']}</span>
                          </div>
                          <div style="display:flex;justify-content:space-between;font-size:14px;margin-top:8px;">
                            <span style="color:#64748b;">Ends</span>
                            <span style="color:#e2e8f0;font-weight:600;">{event['end_time']}</span>
                          </div>
                        </div>
                        <p style="font-size:12px;color:#475569;margin:0;">Sent by ChronoSync • Intelligent Schedule Assistant</p>
                      </div>
                    </div>
                    """
                    if send_email(user['email'], subject, html_body):
                        cursor.execute(
                            'INSERT INTO email_reminders_sent (event_id) VALUES (?)',
                            (event['id'],)
                        )
                        conn.commit()

            conn.close()
        except Exception as e:
            print(f"[REMINDER WORKER ERROR] {e}")
        time.sleep(60)


# Start reminder thread
reminder_thread = threading.Thread(target=reminder_worker, daemon=True)
reminder_thread.start()


# ──────────────────────────────────────────────
# Schedule Optimizer
# ──────────────────────────────────────────────

class ScheduleOptimizer:
    def __init__(self, events, availability):
        self.events = events
        self.availability = availability

    def parse_dt(self, dt_str):
        dt_str = dt_str.replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(dt_str)
        except Exception:
            return datetime.fromisoformat(dt_str.split('+')[0])

    def check_overlap(self, event1, event2):
        s1, e1 = self.parse_dt(event1['start']), self.parse_dt(event1['end'])
        s2, e2 = self.parse_dt(event2['start']), self.parse_dt(event2['end'])
        return s1 < e2 and s2 < e1

    def find_conflicts(self):
        conflicts = []
        for i, e1 in enumerate(self.events):
            for j, e2 in enumerate(self.events[i + 1:], i + 1):
                if self.check_overlap(e1, e2):
                    conflicts.append((i, j, e1, e2))
        return conflicts

    def resolve_conflicts(self):
        conflicts = self.find_conflicts()
        rescheduled = []
        modified = {}
        for i, j, e1, e2 in conflicts:
            if i in modified or j in modified:
                continue
            p1, p2 = e1.get('priority', 1), e2.get('priority', 1)
            if p1 >= p2:
                move_idx, move_evt, stay_evt = j, self.events[j], e1
            else:
                move_idx, move_evt, stay_evt = i, self.events[i], e2
            new_time = self.find_next_available_slot(move_evt, modified)
            if new_time:
                old_s, old_e = move_evt['start'], move_evt['end']
                move_evt['start'], move_evt['end'] = new_time['start'], new_time['end']
                modified[move_idx] = True
                rescheduled.append({
                    'event': move_evt,
                    'old_start': old_s,
                    'old_end': old_e,
                    'reason': f"Conflict with higher-priority event: {stay_evt['title']}"
                })
        return rescheduled

    def find_next_available_slot(self, event, modified=None):
        if modified is None:
            modified = {}
        start = self.parse_dt(event['start'])
        end = self.parse_dt(event['end'])
        duration = end - start
        for day in range(14):
            for hour in range(24):
                cs = start + timedelta(days=day, hours=hour)
                ce = cs + duration
                conflict = False
                for other in self.events:
                    if other['id'] == event['id']:
                        continue
                    os_ = self.parse_dt(other['start'])
                    oe = self.parse_dt(other['end'])
                    if cs < oe and os_ < ce:
                        conflict = True
                        break
                if not conflict:
                    return {'start': cs.isoformat(), 'end': ce.isoformat()}
        return None

    def calculate_gap_at_position(self, schedule, event, position):
        es = datetime.fromisoformat(event['start'].replace('Z', '+00:00'))
        ee = datetime.fromisoformat(event['end'].replace('Z', '+00:00'))
        gb = ga = 0
        if position > 0:
            pe = datetime.fromisoformat(schedule[position - 1]['end'].replace('Z', '+00:00'))
            gb = max(0, (es - pe).total_seconds() / 60)
        if position < len(schedule):
            ns = datetime.fromisoformat(schedule[position]['start'].replace('Z', '+00:00'))
            ga = max(0, (ns - ee).total_seconds() / 60)
        return gb + ga


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username, password, email = data.get('username'), data.get('password'), data.get('email')
    if not username or not password or not email:
        return jsonify({'error': 'Missing required fields'}), 400
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)',
                       (username, pw_hash, email))
        conn.commit()
        uid = cursor.lastrowid
        conn.close()
        session['user_id'] = uid
        session['username'] = username
        log_activity(uid, 'register', {'username': username})
        return jsonify({'success': True, 'user_id': uid})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 400


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username, password = data.get('username'), data.get('password')
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username FROM users WHERE username = ? AND password_hash = ?',
                   (username, pw_hash))
    user = cursor.fetchone()
    conn.close()
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        log_activity(user['id'], 'login')
        return jsonify({'success': True, 'username': user['username']})
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    if 'user_id' in session:
        log_activity(session['user_id'], 'logout')
    session.clear()
    return jsonify({'success': True})


# ── Events ──

@app.route('/api/events', methods=['GET', 'POST'])
def events():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    uid = session['user_id']

    if request.method == 'GET':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM events WHERE user_id = ? ORDER BY start_time', (uid,))
        rows = cursor.fetchall()
        conn.close()
        result = []
        for e in rows:
            row_dict = dict(e)
            result.append({
                'id': row_dict['id'], 'title': row_dict['title'],
                'description': row_dict.get('description', ''),
                'start': row_dict['start_time'], 'end': row_dict['end_time'],
                'priority': row_dict['priority'], 'is_deadline': bool(row_dict['is_deadline']),
                'color': row_dict.get('color', '#3b82f6'),
                'attendee_email': row_dict.get('attendee_email') or ''
            })
        return jsonify(result)

    data = request.json

    def safe_parse_dt(s):
        """Parse datetime-local string robustly."""
        if not s:
            raise ValueError("Empty datetime string")
        s = s.strip()
        # Remove timezone suffix for naive comparison
        for suffix in ('+00:00', 'Z'):
            if s.endswith(suffix):
                s = s[:-len(suffix)]
        # Handle both 'T' separator and space
        s = s.replace(' ', 'T')
        # Trim seconds if not present
        if len(s) == 16:  # YYYY-MM-DDTHH:MM
            s += ':00'
        return datetime.fromisoformat(s)

    # ── Conflict detection before saving ──
    check_only = data.get('check_conflicts_only', False)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE user_id = ? ORDER BY start_time', (uid,))
    existing = cursor.fetchall()
    conn.close()

    new_start = safe_parse_dt(data['start'])
    new_end = safe_parse_dt(data['end'])
    conflicts = []
    for e in existing:
        try:
            es = safe_parse_dt(e['start_time'])
            ee = safe_parse_dt(e['end_time'])
        except Exception:
            continue
        if new_start < ee and es < new_end:
            # skip same event on edit
            if data.get('edit_id') and str(e['id']) == str(data['edit_id']):
                continue
            conflicts.append({'id': e['id'], 'title': e['title'],
                               'start': e['start_time'], 'end': e['end_time'],
                               'priority': e['priority']})

    if check_only:
        return jsonify({'conflicts': conflicts})

    if conflicts and not data.get('force_save'):
        return jsonify({'error': 'conflict', 'conflicts': conflicts}), 409

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO events (user_id, title, description, start_time, end_time, priority, is_deadline, color, attendee_email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (uid, data['title'], data.get('description', ''), data['start'], data['end'],
          data.get('priority', 1), 1 if data.get('is_deadline') else 0,
          data.get('color', '#3b82f6'), data.get('attendee_email', '')))
    conn.commit()
    eid = cursor.lastrowid
    conn.close()

    log_activity(uid, 'event_created', {'title': data['title'], 'start': data['start']})

    # Send confirmation email to self
    prefs = get_user_prefs(uid)
    if prefs['email_reminders']:
        user_email = get_user_email(uid)
        if user_email:
            threading.Thread(target=send_email, args=(
                user_email,
                f"📅 Event Scheduled: {data['title']}",
                f"""<div style="font-family:'Segoe UI',sans-serif;max-width:520px;margin:auto;background:#0f1117;color:#e2e8f0;border-radius:12px;overflow:hidden;">
                  <div style="background:linear-gradient(135deg,#065f46,#1e40af);padding:24px 32px;">
                    <h2 style="margin:0;font-size:22px;">Event Confirmed</h2>
                    <p style="margin:6px 0 0;opacity:.8;font-size:14px;">ChronoSync has scheduled your event</p>
                  </div>
                  <div style="padding:28px 32px;">
                    <h3 style="margin:0 0 8px;font-size:20px;color:#6ee7b7;">{data['title']}</h3>
                    <p style="color:#94a3b8;font-size:14px;">{data.get('description','')}</p>
                    <div style="background:#1e293b;border-radius:8px;padding:16px;">
                      <div style="display:flex;justify-content:space-between;font-size:14px;">
                        <span style="color:#64748b;">Start</span><span style="font-weight:600;">{data['start']}</span>
                      </div>
                      <div style="display:flex;justify-content:space-between;font-size:14px;margin-top:8px;">
                        <span style="color:#64748b;">End</span><span style="font-weight:600;">{data['end']}</span>
                      </div>
                    </div>
                    <p style="font-size:12px;color:#475569;margin-top:16px;">You'll receive a reminder {prefs['reminder_minutes']} min before.</p>
                  </div>
                </div>"""
            ), daemon=True).start()

    return jsonify({'success': True, 'id': eid})


@app.route('/api/events/<int:event_id>', methods=['PUT', 'DELETE'])
def event_detail(event_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    uid = session['user_id']

    if request.method == 'PUT':
        data = request.json
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE events SET title=?, description=?, start_time=?, end_time=?,
                priority=?, is_deadline=?, color=?, attendee_email=?
                WHERE id=? AND user_id=?
            ''', (data['title'], data.get('description', ''), data['start'], data['end'],
                  data.get('priority', 1), 1 if data.get('is_deadline') else 0,
                  data.get('color', '#3b82f6'), data.get('attendee_email', ''),
                  event_id, uid))
        except sqlite3.OperationalError:
            # Fallback if attendee_email column missing (shouldn't happen after migrate_db)
            cursor.execute('''
                UPDATE events SET title=?, description=?, start_time=?, end_time=?,
                priority=?, is_deadline=?, color=?
                WHERE id=? AND user_id=?
            ''', (data['title'], data.get('description', ''), data['start'], data['end'],
                  data.get('priority', 1), 1 if data.get('is_deadline') else 0,
                  data.get('color', '#3b82f6'),
                  event_id, uid))
        conn.commit()
        conn.close()
        log_activity(uid, 'event_updated', {'id': event_id, 'title': data['title']})
        return jsonify({'success': True})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT title FROM events WHERE id=? AND user_id=?', (event_id, uid))
    row = cursor.fetchone()
    cursor.execute('DELETE FROM events WHERE id=? AND user_id=?', (event_id, uid))
    conn.commit()
    conn.close()
    if row:
        log_activity(uid, 'event_deleted', {'id': event_id, 'title': row['title']})
    return jsonify({'success': True})


# ── Optimize ──

@app.route('/api/optimize', methods=['POST'])
def optimize():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    uid = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE user_id=? ORDER BY start_time', (uid,))
    rows = cursor.fetchall()
    if len(rows) < 2:
        conn.close()
        return jsonify({'success': True, 'rescheduled': [], 'message': 'Need at least 2 events to optimize.'})

    event_list = [{'id': e['id'], 'title': e['title'], 'description': e['description'],
                   'start': e['start_time'], 'end': e['end_time'],
                   'priority': e['priority'], 'is_deadline': bool(e['is_deadline']),
                   'color': e['color']} for e in rows]

    optimizer = ScheduleOptimizer(event_list, [])
    rescheduled = optimizer.resolve_conflicts()

    for item in rescheduled:
        ev = item['event']
        cursor.execute('UPDATE events SET start_time=?, end_time=? WHERE id=? AND user_id=?',
                       (ev['start'], ev['end'], ev['id'], uid))
    conn.commit()
    conn.close()

    log_activity(uid, 'schedule_optimized', {'rescheduled_count': len(rescheduled)})

    resp = [{'id': i['event']['id'], 'title': i['event']['title'],
             'old_start': i['old_start'], 'new_start': i['event']['start'],
             'reason': i['reason']} for i in rescheduled]
    msg = (f'Optimized! Rescheduled {len(rescheduled)} event(s).'
           if rescheduled else 'No conflicts found. Schedule already optimized!')
    return jsonify({'success': True, 'rescheduled': resp, 'message': msg})


# ── Conflict check endpoint ──

@app.route('/api/events/check-conflicts', methods=['POST'])
def check_conflicts():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    uid = session['user_id']
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE user_id=? ORDER BY start_time', (uid,))
    existing = cursor.fetchall()
    conn.close()

    try:
        new_start = datetime.fromisoformat(data['start'].replace('Z', '').split('+')[0])
        new_end = datetime.fromisoformat(data['end'].replace('Z', '').split('+')[0])
    except Exception:
        return jsonify({'conflicts': []})

    conflicts = []
    for e in existing:
        if data.get('exclude_id') and str(e['id']) == str(data['exclude_id']):
            continue
        es = datetime.fromisoformat(e['start_time'].split('+')[0])
        ee = datetime.fromisoformat(e['end_time'].split('+')[0])
        if new_start < ee and es < new_end:
            conflicts.append({'id': e['id'], 'title': e['title'],
                               'start': e['start_time'], 'end': e['end_time'],
                               'priority': e['priority']})
    return jsonify({'conflicts': conflicts})


# ── Delay handling ──

@app.route('/api/events/<int:event_id>/delay', methods=['POST'])
def report_delay(event_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    uid = session['user_id']
    data = request.json
    delay_minutes = int(data.get('delay_minutes', 15))
    tentative_time = data.get('tentative_time', '')
    notify_attendee = data.get('notify_attendee', False)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM events WHERE id=? AND user_id=?', (event_id, uid))
    event = cursor.fetchone()
    if not event:
        conn.close()
        return jsonify({'error': 'Event not found'}), 404

    # Find and bump lower-priority upcoming events
    old_start = datetime.fromisoformat(event['start_time'].split('+')[0])
    new_start = old_start + timedelta(minutes=delay_minutes)
    old_end = datetime.fromisoformat(event['end_time'].split('+')[0])
    duration = old_end - old_start
    new_end = new_start + duration

    cursor.execute('UPDATE events SET start_time=?, end_time=? WHERE id=? AND user_id=?',
                   (new_start.isoformat(), new_end.isoformat(), event_id, uid))

    # Cascade: move lower-priority events that now conflict
    cursor.execute('''SELECT * FROM events WHERE user_id=? AND id!=? AND start_time >= ?
                      ORDER BY start_time''', (uid, event_id, old_start.isoformat()))
    upcoming = cursor.fetchall()
    cascaded = []
    for ev in upcoming:
        ep = ev['priority']
        if ep <= event['priority']:
            es = datetime.fromisoformat(ev['start_time'].split('+')[0])
            ee = datetime.fromisoformat(ev['end_time'].split('+')[0])
            if new_start < ee and es < new_end:
                bump_start = new_end + timedelta(minutes=5)
                bump_end = bump_start + (ee - es)
                cursor.execute('UPDATE events SET start_time=?, end_time=? WHERE id=?',
                               (bump_start.isoformat(), bump_end.isoformat(), ev['id']))
                cascaded.append({'id': ev['id'], 'title': ev['title'],
                                 'new_start': bump_start.isoformat()})

    conn.commit()
    conn.close()

    log_activity(uid, 'delay_reported', {
        'event_id': event_id, 'delay_minutes': delay_minutes,
        'cascaded': len(cascaded)
    })

    # Send delay notification email to attendee
    if notify_attendee and event['attendee_email']:
        subject = f"⚠️ Meeting Delayed: {event['title']}"
        html_body = f"""
        <div style="font-family:'Segoe UI',sans-serif;max-width:520px;margin:auto;background:#0f1117;color:#e2e8f0;border-radius:12px;overflow:hidden;">
          <div style="background:linear-gradient(135deg,#7c2d12,#b45309);padding:24px 32px;">
            <h2 style="margin:0;font-size:22px;">⚠️ Meeting Delay Notice</h2>
            <p style="margin:6px 0 0;opacity:.8;font-size:14px;">The organizer is running late</p>
          </div>
          <div style="padding:28px 32px;">
            <h3 style="margin:0 0 8px;font-size:20px;color:#fcd34d;">{event['title']}</h3>
            <div style="background:#1e293b;border-radius:8px;padding:16px;margin-bottom:16px;">
              <div style="display:flex;justify-content:space-between;font-size:14px;">
                <span style="color:#64748b;">Original Start</span>
                <span style="text-decoration:line-through;color:#ef4444;">{old_start.strftime('%d %b %Y, %H:%M')}</span>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:14px;margin-top:8px;">
                <span style="color:#64748b;">Delayed By</span>
                <span style="color:#fbbf24;font-weight:700;">{delay_minutes} minutes</span>
              </div>
              {'<div style="display:flex;justify-content:space-between;font-size:14px;margin-top:8px;"><span style="color:#64748b;">Tentative New Time</span><span style="color:#6ee7b7;font-weight:600;">' + tentative_time + '</span></div>' if tentative_time else ''}
            </div>
            <p style="font-size:13px;color:#64748b;margin:0;">Please adjust your schedule accordingly. We apologize for the inconvenience.</p>
          </div>
        </div>
        """
        threading.Thread(target=send_email,
                         args=(event['attendee_email'], subject, html_body),
                         daemon=True).start()

    return jsonify({
        'success': True,
        'new_start': new_start.isoformat(),
        'new_end': new_end.isoformat(),
        'cascaded': cascaded,
        'message': f"Event delayed by {delay_minutes} min. {len(cascaded)} conflicting event(s) rescheduled."
    })


# ── Preferences ──

@app.route('/api/preferences', methods=['GET', 'POST'])
def preferences():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    uid = session['user_id']

    if request.method == 'GET':
        return jsonify(get_user_prefs(uid))

    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO preferences (user_id, email_reminders, reminder_minutes, auto_optimize, work_start, work_end, timezone)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
          email_reminders=excluded.email_reminders,
          reminder_minutes=excluded.reminder_minutes,
          auto_optimize=excluded.auto_optimize,
          work_start=excluded.work_start,
          work_end=excluded.work_end,
          timezone=excluded.timezone
    ''', (uid, data.get('email_reminders', 1), data.get('reminder_minutes', 10),
          data.get('auto_optimize', 0), data.get('work_start', '09:00'),
          data.get('work_end', '18:00'), data.get('timezone', 'Asia/Kolkata')))
    conn.commit()
    conn.close()
    log_activity(uid, 'preferences_updated', data)
    return jsonify({'success': True})


# ── Activity log ──

@app.route('/api/logs', methods=['GET'])
def get_logs():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    uid = session['user_id']
    limit = int(request.args.get('limit', 50))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM activity_log WHERE user_id=? ORDER BY timestamp DESC LIMIT ?',
                   (uid, limit))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{
        'id': r['id'], 'action': r['action'],
        'details': json.loads(r['details']) if r['details'] else None,
        'timestamp': r['timestamp']
    } for r in rows])


# ── Availability ──

@app.route('/api/availability', methods=['GET', 'POST'])
def availability():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    uid = session['user_id']
    if request.method == 'GET':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM availability WHERE user_id=?', (uid,))
        avail = cursor.fetchall()
        conn.close()
        return jsonify([{'id': a['id'], 'day_of_week': a['day_of_week'],
                         'start_time': a['start_time'], 'end_time': a['end_time']} for a in avail])
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO availability (user_id, day_of_week, start_time, end_time) VALUES (?, ?, ?, ?)',
                   (uid, data['day_of_week'], data['start_time'], data['end_time']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='127.0.0.5', port=5000,use_reloader=False)
