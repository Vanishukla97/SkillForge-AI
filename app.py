from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
import sqlite3
import bcrypt
import os
from datetime import datetime, timedelta
import json
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

DATABASE = 'career_path.db'

# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================
# DECORATORS
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# TEMPLATE FILTERS
# ============================================================

@app.template_filter('from_json')
def from_json_filter(value):
    try:
        return json.loads(value) if value else []
    except:
        return []

# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name', '')
        
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return render_template('signup.html')
        
        conn = get_db_connection()
        
        # Check if user exists
        existing = conn.execute('SELECT id FROM users WHERE username=? OR email=?', 
                               (username, email)).fetchone()
        if existing:
            conn.close()
            flash('Username or email already exists', 'error')
            return render_template('signup.html')
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create user
        cursor = conn.execute('''
            INSERT INTO users (username, email, password_hash, full_name) 
            VALUES (?, ?, ?, ?)
        ''', (username, email, password_hash, full_name))
        
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        session['user_id'] = user_id
        session['username'] = username
        session.permanent = True
        
        return redirect(url_for('dashboard'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username=? OR email=?', 
                           (username, username)).fetchone()
        conn.close()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash']):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True
            return redirect(url_for('dashboard'))
        
        flash('Invalid credentials', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ============================================================
# DASHBOARD
# ============================================================

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session.get('username'))

# ============================================================
# MODULE 1: MOCK TEST SYSTEM ROUTES
# ============================================================

@app.route('/mock_test')
@login_required
def mock_test_subjects():
    conn = get_db_connection()
    subjects = conn.execute('SELECT * FROM subjects WHERE is_active=1').fetchall()
    conn.close()
    return render_template('mock_test/subjects.html', subjects=subjects)

@app.route('/mock_test/<int:subject_id>')
@login_required
def mock_test_list(subject_id):
    conn = get_db_connection()
    subject = conn.execute('SELECT * FROM subjects WHERE id=?', (subject_id,)).fetchone()
    tests = conn.execute('''
        SELECT mt.*, COUNT(q.id) as question_count 
        FROM mock_tests mt
        LEFT JOIN questions q ON q.mock_test_id = mt.id
        WHERE mt.subject_id=? AND mt.is_active=1
        GROUP BY mt.id
    ''', (subject_id,)).fetchall()
    conn.close()
    return render_template('mock_test/test_list.html', subject=subject, tests=tests)

@app.route('/mock_test/start/<int:test_id>', methods=['POST'])
@login_required
def start_mock_test(test_id):
    conn = get_db_connection()
    
    # Check for existing in-progress attempt
    existing = conn.execute('''
        SELECT id FROM test_attempts 
        WHERE user_id=? AND mock_test_id=? AND status='in_progress'
    ''', (session['user_id'], test_id)).fetchone()
    
    if existing:
        conn.close()
        return jsonify({'success': False, 'error': 'Test already in progress', 'attempt_id': existing['id']}), 409
    
    # Create new attempt
    attempt_id = str(uuid.uuid4())
    conn.execute('''
        INSERT INTO test_attempts (id, user_id, mock_test_id) 
        VALUES (?, ?, ?)
    ''', (attempt_id, session['user_id'], test_id))
    conn.commit()
    
    # Get questions (WITHOUT correct answers)
    questions = conn.execute('''
        SELECT id, topic, question_text, option_a, option_b, option_c, option_d,
               difficulty, marks, question_order
        FROM questions WHERE mock_test_id=? ORDER BY question_order
    ''', (test_id,)).fetchall()
    
    # Get test metadata
    test = conn.execute('''
        SELECT mt.*, s.name as subject_name 
        FROM mock_tests mt
        JOIN subjects s ON s.id = mt.subject_id
        WHERE mt.id=?
    ''', (test_id,)).fetchone()
    
    conn.close()
    
    return jsonify({
        'success': True,
        'attempt_id': attempt_id,
        'test': dict(test),
        'questions': [dict(q) for q in questions]
    })

@app.route('/mock_test/take/<attempt_id>')
@login_required
def take_mock_test(attempt_id):
    return render_template('mock_test/quiz.html')

@app.route('/mock_test/submit/<attempt_id>', methods=['POST'])
@login_required
def submit_mock_test(attempt_id):
    data = request.get_json()
    answers = data.get('answers', {})
    time_taken = data.get('timeTaken', 0)
    
    conn = get_db_connection()
    
    # Verify attempt
    attempt = conn.execute('''
        SELECT ta.*, mt.subject_id 
        FROM test_attempts ta
        JOIN mock_tests mt ON mt.id = ta.mock_test_id
        WHERE ta.id=? AND ta.user_id=? AND ta.status='in_progress'
    ''', (attempt_id, session['user_id'])).fetchone()
    
    if not attempt:
        conn.close()
        return jsonify({'success': False, 'error': 'Attempt not found'}), 404
    
    subject_id = attempt['subject_id']
    
    # Get correct answers
    questions = conn.execute('''
        SELECT id, topic, correct_option, marks, negative_marks
        FROM questions WHERE mock_test_id=?
    ''', (attempt['mock_test_id'],)).fetchall()
    
    # SCORING LOGIC
    total_score = 0
    total_correct = 0
    total_incorrect = 0
    total_skipped = 0
    topic_stats = {}
    
    for q in questions:
        selected = answers.get(str(q['id']))
        is_correct = None
        marks_gained = 0
        
        if not selected:
            total_skipped += 1
        elif selected == q['correct_option']:
            total_correct += 1
            is_correct = 1
            marks_gained = q['marks']
            total_score += marks_gained
        else:
            total_incorrect += 1
            is_correct = 0
            marks_gained = -q['negative_marks']
            total_score += marks_gained
        
        # Track topic stats
        topic = q['topic']
        if topic not in topic_stats:
            topic_stats[topic] = {'correct': 0, 'total': 0}
        topic_stats[topic]['total'] += 1
        if is_correct:
            topic_stats[topic]['correct'] += 1
        
        # Save answer
        conn.execute('''
            INSERT OR REPLACE INTO attempt_answers 
            (attempt_id, question_id, selected_option, is_correct, marks_obtained)
            VALUES (?, ?, ?, ?, ?)
        ''', (attempt_id, q['id'], selected, is_correct, marks_gained))
    
    percentage = (total_score / len(questions)) * 100 if questions else 0
    
    # Update attempt
    conn.execute('''
        UPDATE test_attempts SET
            status='submitted', total_score=?, total_correct=?,
            total_incorrect=?, total_skipped=?, percentage=?,
            time_taken_secs=?, submitted_at=CURRENT_TIMESTAMP
        WHERE id=?
    ''', (total_score, total_correct, total_incorrect, total_skipped, percentage, time_taken, attempt_id))
    
    # Update topic performance
    for topic, stats in topic_stats.items():
        acc = (stats['correct'] / stats['total']) * 100 if stats['total'] > 0 else 0
        conn.execute('''
            INSERT INTO topic_performance (user_id, subject_id, topic, total_attempted, total_correct, accuracy)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, subject_id, topic) DO UPDATE SET
                total_attempted = total_attempted + ?,
                total_correct = total_correct + ?,
                accuracy = ROUND((total_correct + ?) * 100.0 / (total_attempted + ?), 2),
                last_updated = CURRENT_TIMESTAMP
        ''', (session['user_id'], subject_id, topic, stats['total'], stats['correct'], acc,
              stats['total'], stats['correct'], stats['correct'], stats['total']))
    
    # Detect weak areas
    weak_areas = detect_weak_areas(conn, session['user_id'], subject_id)
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'score': {
            'totalScore': total_score,
            'totalCorrect': total_correct,
            'totalIncorrect': total_incorrect,
            'totalSkipped': total_skipped,
            'percentage': round(percentage, 2)
        },
        'topicStats': topic_stats,
        'weakAreas': weak_areas,
        'attemptId': attempt_id
    })

@app.route('/mock_test/results/<attempt_id>')
@login_required
def mock_test_results(attempt_id):
    conn = get_db_connection()
    
    # Get attempt
    attempt = conn.execute('''
        SELECT * FROM test_attempts WHERE id=? AND user_id=?
    ''', (attempt_id, session['user_id'])).fetchone()
    
    if not attempt:
        conn.close()
        return "Result not found", 404
    
    # Get answers with questions and explanations
    answers = conn.execute('''
        SELECT aa.*, q.question_text, q.topic, q.option_a, q.option_b, q.option_c, q.option_d,
               q.correct_option, q.correct_answer, q.difficulty,
               ae.explanation, ae.concept_summary, ae.memory_tip, ae.common_mistake
        FROM attempt_answers aa
        JOIN questions q ON q.id = aa.question_id
        LEFT JOIN ai_explanations ae ON ae.question_id = q.id
        WHERE aa.attempt_id=?
        ORDER BY q.question_order
    ''', (attempt_id,)).fetchall()
    
    # Get topic performance
    topic_perf = conn.execute('''
        SELECT topic, accuracy, total_attempted, total_correct
        FROM topic_performance
        WHERE user_id=? AND subject_id=(
            SELECT mt.subject_id FROM mock_tests mt
            JOIN test_attempts ta ON ta.mock_test_id = mt.id WHERE ta.id=?
        )
        ORDER BY accuracy ASC
    ''', (session['user_id'], attempt_id)).fetchall()
    
    # Get weak areas
    weak = conn.execute('''
        SELECT * FROM weak_areas WHERE user_id=?
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('mock_test/results.html', 
                         attempt=attempt, 
                         answers=answers, 
                         topic_performance=topic_perf,
                         weak_areas=weak)

# ============================================================
# HELPER FUNCTIONS - MOCK TEST
# ============================================================

def detect_weak_areas(conn, user_id, subject_id):
    """Detect weak topics based on performance"""
    WEAK_THRESHOLD = 50
    CRITICAL_THRESHOLD = 30
    MIN_ATTEMPTS = 3
    
    topics = conn.execute('''
        SELECT topic, accuracy, total_attempted FROM topic_performance
        WHERE user_id=? AND subject_id=? AND total_attempted >= ?
    ''', (user_id, subject_id, MIN_ATTEMPTS)).fetchall()
    
    if not topics:
        return []
    
    avg_accuracy = sum(float(t['accuracy']) for t in topics) / len(topics)
    weak_areas = []
    
    for t in topics:
        acc = float(t['accuracy'])
        priority = None
        
        if acc < CRITICAL_THRESHOLD:
            priority = 'Critical'
        elif acc < WEAK_THRESHOLD:
            priority = 'High'
        elif acc < avg_accuracy - 15:
            priority = 'Medium'
        
        if priority:
            suggestion = get_topic_suggestion(t['topic'], acc)
            weak_areas.append({
                'topic': t['topic'],
                'accuracy': acc,
                'priority': priority,
                'suggestion': suggestion
            })
            
            # Save to DB
            conn.execute('''
                INSERT OR REPLACE INTO weak_areas 
                (user_id, subject_id, topic, accuracy, priority, suggestion)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, subject_id, t['topic'], acc, priority, suggestion))
    
    return sorted(weak_areas, key=lambda x: x['accuracy'])

def get_topic_suggestion(topic, accuracy):
    """Get improvement suggestion for a topic"""
    tips = {
        'Arrays': 'Focus on two-pointer and sliding window. Practice 10 LeetCode Easy problems.',
        'Strings': 'Master KMP algorithm. Practice string manipulation daily.',
        'Linked List': 'Draw pointer diagrams. Practice reversal and cycle detection.',
        'Stack': 'Practice monotonic stack problems and expression evaluation.',
        'Recursion': 'Trace each call on paper. Start with simple factorial/fibonacci.',
        'Dynamic Programming': 'Master 0/1 Knapsack pattern. Practice LCS and LIS.',
        'Trees': 'Practice all traversals. Focus on BST properties.',
        'Graphs': 'Implement BFS/DFS from scratch. Study shortest path algorithms.',
    }
    return tips.get(topic, f'Practice {topic} problems daily. Accuracy: {accuracy:.1f}%')

# ============================================================
# MODULE 2: RESUME TRACKER ROUTES
# ============================================================

@app.route('/resume_tracker')
@login_required
def resume_tracker():
    conn = get_db_connection()
    companies = conn.execute('''
        SELECT c.*, COUNT(r.id) as role_count
        FROM companies c
        LEFT JOIN roles r ON r.company_id = c.id AND r.is_active=1
        WHERE c.is_active=1
        GROUP BY c.id
        ORDER BY c.tier, c.name
    ''').fetchall()
    conn.close()
    return render_template('resume_tracker/companies.html', companies=companies)

@app.route('/resume_tracker/company/<int:company_id>/roles')
@login_required
def company_roles(company_id):
    conn = get_db_connection()
    company = conn.execute('SELECT * FROM companies WHERE id=?', (company_id,)).fetchone()
    roles = conn.execute('''
        SELECT * FROM roles WHERE company_id=? AND is_active=1 ORDER BY title
    ''', (company_id,)).fetchall()
    conn.close()
    return render_template('resume_tracker/roles.html', company=company, roles=roles)

@app.route('/api/resume/upload', methods=['POST'])
@login_required
def upload_resume():
    if 'resume' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    
    file = request.files['resume']
    if file.filename == '' or not file.filename.endswith('.pdf'):
        return jsonify({'success': False, 'error': 'PDF file required'}), 400
    
    # Send to AI service for processing
    import requests
    files = {'file': (file.filename, file.read(), 'application/pdf')}
    
    try:
        response = requests.post('http://localhost:8000/resume/process', files=files, timeout=60)
        data = response.json()
        
        # Save resume
        resume_id = str(uuid.uuid4())
        conn = get_db_connection()
        
        # Mark old resumes inactive
        conn.execute('UPDATE user_resumes SET is_active=0 WHERE user_id=?', (session['user_id'],))
        
        # Insert new resume
        conn.execute('''
            INSERT INTO user_resumes 
            (id, user_id, original_filename, resume_text, extracted_skills, resume_embedding)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (resume_id, session['user_id'], file.filename, 
              data['resume_text'], str(data['extracted_skills']), str(data['embedding'])))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'resumeId': resume_id,
            'extractedSkills': data['extracted_skills'],
            'skillCount': len(data['extracted_skills'].get('technical', []))
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/resume/assess', methods=['POST'])
@login_required
def assess_resume():
    data = request.get_json()
    resume_id = data.get('resumeId')
    role_id = data.get('roleId')
    
    conn = get_db_connection()
    
    # Get resume
    resume = conn.execute('''
        SELECT * FROM user_resumes WHERE id=? AND user_id=? AND is_active=1
    ''', (resume_id, session['user_id'])).fetchone()
    
    if not resume:
        conn.close()
        return jsonify({'success': False, 'error': 'Resume not found'}), 404
    
    # Get role
    role = conn.execute('''
        SELECT r.*, c.name as company_name FROM roles r
        JOIN companies c ON c.id = r.company_id WHERE r.id=?
    ''', (role_id,)).fetchone()
    
    if not role:
        conn.close()
        return jsonify({'success': False, 'error': 'Role not found'}), 404
    
    # Call AI service for scoring
    import requests
    
    try:
        # Parse embeddings and skills
        resume_emb = json.loads(resume['resume_embedding']) if resume['resume_embedding'] else []
        resume_skills = json.loads(resume['extracted_skills']) if resume['extracted_skills'] else {'technical': []}
        
        # Generate JD embedding if not exists
        jd_emb = json.loads(role['jd_embedding']) if role['jd_embedding'] else None
        if not jd_emb:
            emb_resp = requests.post('http://localhost:8000/embed', json={'text': role['jd_text']})
            jd_emb = emb_resp.json()['embedding']
            conn.execute('UPDATE roles SET jd_embedding=? WHERE id=?', (json.dumps(jd_emb), role_id))
            conn.commit()
        
        # Score resume
        score_resp = requests.post('http://localhost:8000/resume/score', json={
            'resume_embedding': resume_emb,
            'jd_embedding': jd_emb,
            'resume_skills': resume_skills.get('technical', []),
            'required_skills': json.loads(role['required_skills']) if role['required_skills'] else [],
            'preferred_skills': json.loads(role['preferred_skills']) if role['preferred_skills'] else [],
            'experience_years': 0
        })
        scores = score_resp.json()
        
        # Generate roadmap
        roadmap_resp = requests.post('http://localhost:8000/resume/roadmap', json={
            'missing_required': scores['missing_required'],
            'missing_preferred': scores['missing_preferred'],
            'target_role': role['title'],
            'target_company': role['company_name'],
            'readiness_score': scores['final_readiness']
        })
        roadmap = roadmap_resp.json()['roadmap']
        
        # Save assessment
        assessment_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO readiness_assessments 
            (id, user_id, resume_id, role_id, cosine_similarity, skill_match_score,
             experience_score, final_readiness, matched_skills, missing_required,
             missing_preferred, roadmap)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (assessment_id, session['user_id'], resume_id, role_id,
              scores['cosine_similarity'], scores['skill_match_score'], scores['experience_score'],
              scores['final_readiness'], json.dumps(scores['matched_required']),
              json.dumps(scores['missing_required']), json.dumps(scores['missing_preferred']),
              json.dumps(roadmap)))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'assessmentId': assessment_id,
            'scores': scores,
            'roadmap': roadmap,
            'role': {'title': role['title'], 'company': role['company_name']}
        })
        
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/resume_tracker/result/<assessment_id>')
@login_required
def assessment_result(assessment_id):
    conn = get_db_connection()
    assessment = conn.execute('''
        SELECT ra.*, r.title as role_title, c.name as company_name, c.tier
        FROM readiness_assessments ra
        JOIN roles r ON r.id = ra.role_id
        JOIN companies c ON c.id = r.company_id
        WHERE ra.id=? AND ra.user_id=?
    ''', (assessment_id, session['user_id'])).fetchone()
    
    if not assessment:
        conn.close()
        return "Assessment not found", 404
    
    conn.close()
    
    # Parse JSON fields
    assessment_dict = dict(assessment)
    assessment_dict['matched_skills'] = json.loads(assessment['matched_skills'])
    assessment_dict['missing_required'] = json.loads(assessment['missing_required'])
    assessment_dict['missing_preferred'] = json.loads(assessment['missing_preferred'])
    assessment_dict['roadmap'] = json.loads(assessment['roadmap'])
    
    return render_template('resume_tracker/result.html', assessment=assessment_dict)

# ============================================================
# RUN SERVER
# ============================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)