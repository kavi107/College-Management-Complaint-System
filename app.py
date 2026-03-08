from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import hashlib
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'college_complaint_secret_2024'

DB_PATH = 'complaint_system.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        department TEXT NOT NULL,
        year INTEGER NOT NULL,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'admin',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id TEXT UNIQUE NOT NULL,
        student_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        subject TEXT NOT NULL,
        description TEXT NOT NULL,
        priority TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'pending',
        admin_response TEXT,
        assigned_to INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students(id),
        FOREIGN KEY (assigned_to) REFERENCES admins(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        user_type TEXT NOT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Insert default admin
    admin_exists = c.execute("SELECT id FROM admins WHERE username='admin'").fetchone()
    if not admin_exists:
        c.execute("INSERT INTO admins (username, name, email, password, role) VALUES (?,?,?,?,?)",
                  ('admin', 'System Administrator', 'admin@college.edu', hash_password('admin123'), 'super_admin'))
        c.execute("INSERT INTO admins (username, name, email, password, role) VALUES (?,?,?,?,?)",
                  ('hodcse', 'Dr. Rajesh Kumar', 'hod.cse@college.edu', hash_password('hod123'), 'hod'))

    # Insert sample students
    student_exists = c.execute("SELECT id FROM students WHERE student_id='CS2021001'").fetchone()
    if not student_exists:
        students = [
            ('CS2021001', 'Arjun Sharma', 'arjun@student.edu', hash_password('student123'), 'Computer Science', 3, '9876543210'),
            ('CS2021002', 'Priya Nair', 'priya@student.edu', hash_password('student123'), 'Computer Science', 3, '9876543211'),
            ('ME2022001', 'Rahul Singh', 'rahul@student.edu', hash_password('student123'), 'Mechanical Engineering', 2, '9876543212'),
        ]
        c.executemany("INSERT INTO students (student_id, name, email, password, department, year, phone) VALUES (?,?,?,?,?,?,?)", students)

    conn.commit()
    conn.close()

# ==================== AUTH ROUTES ====================

@app.route('/')
def index():
    return redirect(url_for('student_login'))

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        data = request.get_json()
        student_id = data.get('student_id')
        password = hash_password(data.get('password'))
        conn = get_db()
        student = conn.execute("SELECT * FROM students WHERE student_id=? AND password=?", (student_id, password)).fetchone()
        conn.close()
        if student:
            session['user_id'] = student['id']
            session['user_type'] = 'student'
            session['user_name'] = student['name']
            return jsonify({'success': True, 'redirect': '/student/dashboard'})
        return jsonify({'success': False, 'message': 'Invalid Student ID or Password'})
    return render_template('student_login.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = hash_password(data.get('password'))
        conn = get_db()
        admin = conn.execute("SELECT * FROM admins WHERE username=? AND password=?", (username, password)).fetchone()
        conn.close()
        if admin:
            session['user_id'] = admin['id']
            session['user_type'] = 'admin'
            session['user_name'] = admin['name']
            session['user_role'] = admin['role']
            return jsonify({'success': True, 'redirect': '/admin/dashboard'})
        return jsonify({'success': False, 'message': 'Invalid username or password'})
    return render_template('admin_login.html')

@app.route('/student/register', methods=['POST'])
def student_register():
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute("INSERT INTO students (student_id, name, email, password, department, year, phone) VALUES (?,?,?,?,?,?,?)",
                     (data['student_id'], data['name'], data['email'], hash_password(data['password']),
                      data['department'], data['year'], data.get('phone', '')))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Registration successful!'})
    except sqlite3.IntegrityError as e:
        conn.close()
        return jsonify({'success': False, 'message': 'Student ID or Email already exists'})

@app.route('/logout')
def logout():
    user_type = session.get('user_type')
    session.clear()
    if user_type == 'admin':
        return redirect(url_for('admin_login'))
    return redirect(url_for('student_login'))

# ==================== STUDENT ROUTES ====================

@app.route('/student/dashboard')
def student_dashboard():
    if session.get('user_type') != 'student':
        return redirect(url_for('student_login'))
    return render_template('student_dashboard.html', user_name=session['user_name'])

@app.route('/api/student/profile')
def get_student_profile():
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    student = conn.execute("SELECT id, student_id, name, email, department, year, phone, created_at FROM students WHERE id=?",
                           (session['user_id'],)).fetchone()
    conn.close()
    return jsonify(dict(student))

@app.route('/api/student/complaints')
def get_student_complaints():
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE student_id=? ORDER BY created_at DESC", (session['user_id'],)
    ).fetchall()
    conn.close()
    return jsonify([dict(c) for c in complaints])

@app.route('/api/student/complaints/stats')
def get_student_stats():
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) as c FROM complaints WHERE student_id=?", (session['user_id'],)).fetchone()['c']
    pending = conn.execute("SELECT COUNT(*) as c FROM complaints WHERE student_id=? AND status='pending'", (session['user_id'],)).fetchone()['c']
    inprogress = conn.execute("SELECT COUNT(*) as c FROM complaints WHERE student_id=? AND status='in_progress'", (session['user_id'],)).fetchone()['c']
    resolved = conn.execute("SELECT COUNT(*) as c FROM complaints WHERE student_id=? AND status='resolved'", (session['user_id'],)).fetchone()['c']
    conn.close()
    return jsonify({'total': total, 'pending': pending, 'in_progress': inprogress, 'resolved': resolved})

@app.route('/api/student/complaint', methods=['POST'])
def submit_complaint():
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    complaint_id = f"CMP{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn = get_db()
    conn.execute(
        "INSERT INTO complaints (complaint_id, student_id, category, subject, description, priority) VALUES (?,?,?,?,?,?)",
        (complaint_id, session['user_id'], data['category'], data['subject'], data['description'], data['priority'])
    )
    # Notify admins
    admins = conn.execute("SELECT id FROM admins").fetchall()
    for admin in admins:
        conn.execute("INSERT INTO notifications (user_id, user_type, message) VALUES (?,?,?)",
                     (admin['id'], 'admin', f"New complaint {complaint_id} submitted by student"))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'complaint_id': complaint_id})

@app.route('/api/student/notifications')
def get_student_notifications():
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    notifs = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND user_type='student' ORDER BY created_at DESC LIMIT 10",
        (session['user_id'],)
    ).fetchall()
    unread = conn.execute(
        "SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND user_type='student' AND is_read=0",
        (session['user_id'],)
    ).fetchone()['c']
    conn.close()
    return jsonify({'notifications': [dict(n) for n in notifs], 'unread': unread})

@app.route('/api/student/notifications/read', methods=['POST'])
def mark_student_notifications_read():
    if session.get('user_type') != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND user_type='student'", (session['user_id'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==================== ADMIN ROUTES ====================

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('user_type') != 'admin':
        return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html', user_name=session['user_name'], user_role=session.get('user_role'))

@app.route('/api/admin/stats')
def get_admin_stats():
    if session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    total_complaints = conn.execute("SELECT COUNT(*) as c FROM complaints").fetchone()['c']
    pending = conn.execute("SELECT COUNT(*) as c FROM complaints WHERE status='pending'").fetchone()['c']
    in_progress = conn.execute("SELECT COUNT(*) as c FROM complaints WHERE status='in_progress'").fetchone()['c']
    resolved = conn.execute("SELECT COUNT(*) as c FROM complaints WHERE status='resolved'").fetchone()['c']
    total_students = conn.execute("SELECT COUNT(*) as c FROM students").fetchone()['c']
    
    by_category = conn.execute(
        "SELECT category, COUNT(*) as count FROM complaints GROUP BY category"
    ).fetchall()
    
    recent = conn.execute(
        """SELECT c.*, s.name as student_name, s.department 
           FROM complaints c JOIN students s ON c.student_id=s.id 
           ORDER BY c.created_at DESC LIMIT 5"""
    ).fetchall()
    
    conn.close()
    return jsonify({
        'total_complaints': total_complaints,
        'pending': pending,
        'in_progress': in_progress,
        'resolved': resolved,
        'total_students': total_students,
        'by_category': [dict(r) for r in by_category],
        'recent_complaints': [dict(r) for r in recent]
    })

@app.route('/api/admin/complaints')
def get_admin_complaints():
    if session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    status_filter = request.args.get('status', 'all')
    category_filter = request.args.get('category', 'all')
    
    query = """SELECT c.*, s.name as student_name, s.student_id as sid, s.department 
               FROM complaints c JOIN students s ON c.student_id=s.id WHERE 1=1"""
    params = []
    
    if status_filter != 'all':
        query += " AND c.status=?"
        params.append(status_filter)
    if category_filter != 'all':
        query += " AND c.category=?"
        params.append(category_filter)
    
    query += " ORDER BY c.created_at DESC"
    
    conn = get_db()
    complaints = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(c) for c in complaints])

@app.route('/api/admin/complaint/<int:complaint_id>', methods=['PUT'])
def update_complaint(complaint_id):
    if session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    conn = get_db()
    
    complaint = conn.execute("SELECT * FROM complaints WHERE id=?", (complaint_id,)).fetchone()
    if not complaint:
        conn.close()
        return jsonify({'error': 'Complaint not found'}), 404
    
    resolved_at = None
    if data.get('status') == 'resolved':
        resolved_at = datetime.now().isoformat()
    
    conn.execute(
        "UPDATE complaints SET status=?, admin_response=?, assigned_to=?, updated_at=?, resolved_at=? WHERE id=?",
        (data.get('status', complaint['status']),
         data.get('admin_response', complaint['admin_response']),
         session['user_id'],
         datetime.now().isoformat(),
         resolved_at,
         complaint_id)
    )
    
    # Notify student
    msg = f"Your complaint {complaint['complaint_id']} status updated to {data.get('status', complaint['status'])}"
    conn.execute("INSERT INTO notifications (user_id, user_type, message) VALUES (?,?,?)",
                 (complaint['student_id'], 'student', msg))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/admin/students')
def get_students():
    if session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    students = conn.execute(
        """SELECT s.*, COUNT(c.id) as complaint_count 
           FROM students s LEFT JOIN complaints c ON s.id=c.student_id 
           GROUP BY s.id ORDER BY s.created_at DESC"""
    ).fetchall()
    conn.close()
    return jsonify([dict(s) for s in students])

@app.route('/api/admin/notifications')
def get_admin_notifications():
    if session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    notifs = conn.execute(
        "SELECT * FROM notifications WHERE user_id=? AND user_type='admin' ORDER BY created_at DESC LIMIT 15",
        (session['user_id'],)
    ).fetchall()
    unread = conn.execute(
        "SELECT COUNT(*) as c FROM notifications WHERE user_id=? AND user_type='admin' AND is_read=0",
        (session['user_id'],)
    ).fetchone()['c']
    conn.close()
    return jsonify({'notifications': [dict(n) for n in notifs], 'unread': unread})

@app.route('/api/admin/notifications/read', methods=['POST'])
def mark_admin_notifications_read():
    if session.get('user_type') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=? AND user_type='admin'", (session['user_id'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)