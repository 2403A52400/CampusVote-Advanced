from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, abort
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
import sqlite3, secrets, csv, io, os

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'campusvote.db'
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('CAMPUSVOTE_SECRET', 'change-this-secret-key-before-deployment')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


def now_text():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'voter',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS elections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            start_at TEXT NOT NULL,
            end_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            position TEXT NOT NULL DEFAULT '',
            manifesto TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS participation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            election_id INTEGER NOT NULL,
            receipt_code TEXT NOT NULL UNIQUE,
            submitted_at TEXT NOT NULL,
            UNIQUE(user_id, election_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS ballots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            election_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY (election_id) REFERENCES elections(id) ON DELETE CASCADE,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ballots_election ON ballots(election_id);
        CREATE INDEX IF NOT EXISTS idx_candidates_election ON candidates(election_id);
        ''')
        admin = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if not admin:
            db.execute('INSERT INTO users(full_name,username,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',
                       ('CampusVote Administrator', 'admin', 'admin@campusvote.local', generate_password_hash('admin123'), 'admin', now_text()))
        if not db.execute('SELECT id FROM elections LIMIT 1').fetchone():
            start = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
            end = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')
            cur = db.execute('INSERT INTO elections(title,description,start_at,end_at,status,created_at) VALUES(?,?,?,?,?,?)',
                             ('Student Council Election 2026', 'Demo election for the CampusVote project.', start, end, 'open', now_text()))
            eid = cur.lastrowid
            for name, position, manifesto in [
                ('Aarav Sharma', 'President', 'Promote student activities and transparent communication.'),
                ('Diya Reddy', 'President', 'Improve campus facilities and student support.'),
                ('Rahul Varma', 'Vice President', 'Encourage clubs, events, and student participation.')]:
                db.execute('INSERT INTO candidates(election_id,name,position,manifesto,created_at) VALUES(?,?,?,?,?)',
                           (eid, name, position, manifesto, now_text()))
            db.execute('INSERT INTO audit_logs(actor,action,details,created_at) VALUES(?,?,?,?)',
                       ('system', 'DEMO_DATA_CREATED', 'Sample election and candidates created', now_text()))


def log_action(actor, action, details=''):
    with get_db() as db:
        db.execute('INSERT INTO audit_logs(actor,action,details,created_at) VALUES(?,?,?,?)',
                   (actor, action, details, now_text()))


def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(24)
    return session['_csrf']


@app.before_request
def protect_posts():
    if request.method == 'POST':
        sent = request.form.get('_csrf', '')
        if not sent or sent != session.get('_csrf'):
            abort(400, description='Your form session expired. Please go back, refresh the page, and try again.')


@app.context_processor
def inject_globals():
    return {'csrf_token': csrf_token, 'current_year': datetime.now().year}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in as administrator.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


def election_state(election):
    if election['status'] != 'open':
        return election['status']
    current = datetime.now()
    try:
        start = datetime.strptime(election['start_at'], '%Y-%m-%dT%H:%M')
        end = datetime.strptime(election['end_at'], '%Y-%m-%dT%H:%M')
        if current < start:
            return 'scheduled'
        if current > end:
            return 'ended'
    except ValueError:
        return 'draft'
    return 'open'


@app.route('/')
def index():
    with get_db() as db:
        elections = db.execute('SELECT * FROM elections ORDER BY id DESC').fetchall()
        counts = {e['id']: db.execute('SELECT COUNT(*) FROM candidates WHERE election_id=?', (e['id'],)).fetchone()[0] for e in elections}
    return render_template('index.html', elections=elections, counts=counts, election_state=election_state)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if not all([full_name, username, email, password]):
            flash('Please complete all required fields.', 'danger')
        elif len(password) < 8:
            flash('Password must contain at least 8 characters.', 'danger')
        elif password != confirm:
            flash('Passwords do not match.', 'danger')
        else:
            try:
                with get_db() as db:
                    db.execute('INSERT INTO users(full_name,username,email,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',
                               (full_name, username, email, generate_password_hash(password), 'voter', now_text()))
                log_action(username, 'REGISTERED', 'New voter account created')
                flash('Registration successful. You can now log in.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('That username or email is already registered.', 'danger')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        with get_db() as db:
            user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            log_action(username, 'LOGIN', 'Successful login')
            flash(f"Welcome, {user['full_name']}!", 'success')
            return redirect(url_for('admin_dashboard' if user['role'] == 'admin' else 'dashboard'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    actor = session.get('username', 'user')
    log_action(actor, 'LOGOUT', 'User logged out')
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    with get_db() as db:
        elections = db.execute('SELECT * FROM elections ORDER BY id DESC').fetchall()
        participated = {r['election_id']: r for r in db.execute('SELECT election_id,receipt_code,submitted_at FROM participation WHERE user_id=?', (session['user_id'],)).fetchall()}
        candidate_counts = {e['id']: db.execute('SELECT COUNT(*) FROM candidates WHERE election_id=?', (e['id'],)).fetchone()[0] for e in elections}
    return render_template('dashboard.html', elections=elections, participated=participated,
                           candidate_counts=candidate_counts, election_state=election_state)


@app.route('/election/<int:election_id>')
def election_detail(election_id):
    with get_db() as db:
        election = db.execute('SELECT * FROM elections WHERE id=?', (election_id,)).fetchone()
        if not election:
            abort(404)
        candidates = db.execute('SELECT * FROM candidates WHERE election_id=? ORDER BY name', (election_id,)).fetchall()
        already_voted = False
        if session.get('user_id'):
            already_voted = bool(db.execute('SELECT id FROM participation WHERE user_id=? AND election_id=?', (session['user_id'], election_id)).fetchone())
    return render_template('election.html', election=election, candidates=candidates,
                           already_voted=already_voted, election_state=election_state)


@app.route('/vote', methods=['POST'])
@login_required
def cast_vote():
    election_id = request.form.get('election_id', type=int)
    candidate_id = request.form.get('candidate_id', type=int)
    if not election_id or not candidate_id:
        flash('Please select a candidate.', 'danger')
        return redirect(url_for('dashboard'))
    with get_db() as db:
        election = db.execute('SELECT * FROM elections WHERE id=?', (election_id,)).fetchone()
        candidate = db.execute('SELECT * FROM candidates WHERE id=? AND election_id=?', (candidate_id, election_id)).fetchone()
        if not election or not candidate:
            abort(404)
        if election_state(election) != 'open':
            flash('This election is not currently open for voting.', 'warning')
            return redirect(url_for('election_detail', election_id=election_id))
        try:
            receipt = 'CV-' + secrets.token_hex(5).upper()
            db.execute('INSERT INTO participation(user_id,election_id,receipt_code,submitted_at) VALUES(?,?,?,?)',
                       (session['user_id'], election_id, receipt, now_text()))
            db.execute('INSERT INTO ballots(election_id,candidate_id,submitted_at) VALUES(?,?,?)',
                       (election_id, candidate_id, now_text()))
        except sqlite3.IntegrityError:
            flash('Your account has already voted in this election. Only one vote is allowed.', 'warning')
            return redirect(url_for('election_detail', election_id=election_id))
    session['last_receipt'] = receipt
    log_action(session.get('username', 'voter'), 'VOTE_SUBMITTED', f'Election ID {election_id}; receipt {receipt}')
    flash('Your vote has been submitted successfully. Keep your receipt code.', 'success')
    return redirect(url_for('receipt', code=receipt))


@app.route('/receipt/<code>')
@login_required
def receipt(code):
    with get_db() as db:
        record = db.execute('''SELECT p.receipt_code,p.submitted_at,e.title FROM participation p
                               JOIN elections e ON e.id=p.election_id WHERE p.receipt_code=? AND p.user_id=?''',
                            (code, session['user_id'])).fetchone()
    if not record:
        abort(404)
    return render_template('receipt.html', record=record)


@app.route('/results')
def results():
    with get_db() as db:
        elections = db.execute('SELECT * FROM elections ORDER BY id DESC').fetchall()
        selected_id = request.args.get('election_id', type=int)
        selected = next((e for e in elections if e['id'] == selected_id), elections[0] if elections else None)
        rows = []
        total = 0
        if selected:
            rows = db.execute('''SELECT c.id,c.name,c.position,COUNT(b.id) AS votes
                                 FROM candidates c LEFT JOIN ballots b ON b.candidate_id=c.id AND b.election_id=c.election_id
                                 WHERE c.election_id=? GROUP BY c.id ORDER BY votes DESC,c.name''', (selected['id'],)).fetchall()
            total = sum(r['votes'] for r in rows)
    return render_template('results.html', elections=elections, selected=selected, rows=rows, total=total)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        if not full_name or not email:
            flash('Name and email are required.', 'danger')
        else:
            try:
                with get_db() as db:
                    db.execute('UPDATE users SET full_name=?,email=? WHERE id=?', (full_name, email, session['user_id']))
                session['full_name'] = full_name
                log_action(session['username'], 'PROFILE_UPDATED', 'Name or email updated')
                flash('Profile updated successfully.', 'success')
                return redirect(url_for('profile'))
            except sqlite3.IntegrityError:
                flash('That email address is already in use.', 'danger')
    with get_db() as db:
        user = db.execute('SELECT full_name,username,email,created_at FROM users WHERE id=?', (session['user_id'],)).fetchone()
        history = db.execute('''SELECT p.receipt_code,p.submitted_at,e.title FROM participation p
                                JOIN elections e ON e.id=p.election_id WHERE p.user_id=? ORDER BY p.id DESC''',
                             (session['user_id'],)).fetchall()
    return render_template('profile.html', user=user, history=history)


@app.route('/admin')
@admin_required
def admin_dashboard():
    with get_db() as db:
        stats = {
            'voters': db.execute("SELECT COUNT(*) FROM users WHERE role='voter'").fetchone()[0],
            'elections': db.execute('SELECT COUNT(*) FROM elections').fetchone()[0],
            'candidates': db.execute('SELECT COUNT(*) FROM candidates').fetchone()[0],
            'ballots': db.execute('SELECT COUNT(*) FROM ballots').fetchone()[0]
        }
        elections = db.execute('SELECT * FROM elections ORDER BY id DESC').fetchall()
        recent = db.execute('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 8').fetchall()
    return render_template('admin.html', stats=stats, elections=elections, recent=recent, election_state=election_state)


@app.route('/admin/elections/new', methods=['GET', 'POST'])
@admin_required
def new_election():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        start_at = request.form.get('start_at', '').strip()
        end_at = request.form.get('end_at', '').strip()
        if not title or not start_at or not end_at:
            flash('Title, start date, and end date are required.', 'danger')
        else:
            try:
                start = datetime.strptime(start_at, '%Y-%m-%dT%H:%M')
                end = datetime.strptime(end_at, '%Y-%m-%dT%H:%M')
                if end <= start:
                    raise ValueError
                with get_db() as db:
                    cur = db.execute('INSERT INTO elections(title,description,start_at,end_at,status,created_at) VALUES(?,?,?,?,?,?)',
                                     (title, description, start_at, end_at, 'open', now_text()))
                    eid = cur.lastrowid
                log_action(session['username'], 'ELECTION_CREATED', f'{title} (ID {eid})')
                flash('Election created. Add candidates before opening voting.', 'success')
                return redirect(url_for('manage_candidates', election_id=eid))
            except ValueError:
                flash('Please enter valid dates. The end date must be after the start date.', 'danger')
    return render_template('new_election.html')


@app.route('/admin/election/<int:election_id>/status', methods=['POST'])
@admin_required
def change_election_status(election_id):
    status = request.form.get('status')
    if status not in ('draft', 'open', 'closed'):
        abort(400)
    with get_db() as db:
        election = db.execute('SELECT title FROM elections WHERE id=?', (election_id,)).fetchone()
        if not election:
            abort(404)
        db.execute('UPDATE elections SET status=? WHERE id=?', (status, election_id))
    log_action(session['username'], 'ELECTION_STATUS_CHANGED', f'{election["title"]}: {status}')
    flash(f'Election status changed to {status}.', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/election/<int:election_id>/candidates', methods=['GET', 'POST'])
@admin_required
def manage_candidates(election_id):
    with get_db() as db:
        election = db.execute('SELECT * FROM elections WHERE id=?', (election_id,)).fetchone()
        if not election:
            abort(404)
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            position = request.form.get('position', '').strip()
            manifesto = request.form.get('manifesto', '').strip()
            if not name or not position:
                flash('Candidate name and position are required.', 'danger')
            else:
                db.execute('INSERT INTO candidates(election_id,name,position,manifesto,created_at) VALUES(?,?,?,?,?)',
                           (election_id, name, position, manifesto, now_text()))
                log_action(session['username'], 'CANDIDATE_ADDED', f'{name} added to election {election_id}')
                flash('Candidate added successfully.', 'success')
                return redirect(url_for('manage_candidates', election_id=election_id))
        candidates = db.execute('SELECT * FROM candidates WHERE election_id=? ORDER BY name', (election_id,)).fetchall()
    return render_template('manage_candidates.html', election=election, candidates=candidates)


@app.route('/admin/candidate/<int:candidate_id>/delete', methods=['POST'])
@admin_required
def delete_candidate(candidate_id):
    with get_db() as db:
        candidate = db.execute('SELECT * FROM candidates WHERE id=?', (candidate_id,)).fetchone()
        if not candidate:
            abort(404)
        has_votes = db.execute('SELECT COUNT(*) FROM ballots WHERE candidate_id=?', (candidate_id,)).fetchone()[0]
        if has_votes:
            flash('A candidate with recorded votes cannot be deleted.', 'warning')
        else:
            db.execute('DELETE FROM candidates WHERE id=?', (candidate_id,))
            log_action(session['username'], 'CANDIDATE_DELETED', candidate['name'])
            flash('Candidate deleted.', 'success')
        eid = candidate['election_id']
    return redirect(url_for('manage_candidates', election_id=eid))


@app.route('/admin/export/<int:election_id>')
@admin_required
def export_results(election_id):
    with get_db() as db:
        election = db.execute('SELECT * FROM elections WHERE id=?', (election_id,)).fetchone()
        if not election:
            abort(404)
        rows = db.execute('''SELECT c.name,c.position,COUNT(b.id) AS votes FROM candidates c
                             LEFT JOIN ballots b ON b.candidate_id=c.id AND b.election_id=c.election_id
                             WHERE c.election_id=? GROUP BY c.id ORDER BY votes DESC''', (election_id,)).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Election', election['title']])
    writer.writerow(['Candidate', 'Position', 'Votes'])
    for row in rows:
        writer.writerow([row['name'], row['position'], row['votes']])
    log_action(session['username'], 'RESULTS_EXPORTED', f'Election ID {election_id}')
    return Response('\ufeff' + output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=campusvote_election_{election_id}_results.csv'})


@app.route('/admin/audit')
@admin_required
def audit_logs():
    with get_db() as db:
        logs = db.execute('SELECT * FROM audit_logs ORDER BY id DESC LIMIT 200').fetchall()
    return render_template('audit.html', logs=logs)


@app.errorhandler(400)
def bad_request(error):
    return render_template('error.html', code=400, message=getattr(error, 'description', 'Bad request.')), 400


@app.errorhandler(403)
def forbidden(error):
    return render_template('error.html', code=403, message='You do not have permission to view this page.'), 403


@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', code=404, message='The page or record you requested could not be found.'), 404


init_db()

if __name__ == '__main__':
    app.run(debug=True)
