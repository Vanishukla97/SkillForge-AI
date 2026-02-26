import sqlite3
import hashlib
import json
from datetime import datetime

class Database:
    def __init__(self, db_name='career_path.db'):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        """Initialize all database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User profiles
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                skills TEXT,
                interests TEXT,
                experience_level TEXT,
                resume_text TEXT,
                resume_filename TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # DSA scores
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dsa_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question_id TEXT,
                score INTEGER,
                total_questions INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Interview scores
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS interview_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question TEXT,
                answer TEXT,
                sentiment_score REAL,
                keyword_score REAL,
                overall_score REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Study schedules
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                schedule_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Job readiness assessments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_readiness (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                target_role TEXT,
                target_company TEXT,
                current_skills TEXT,
                readiness_score REAL,
                gaps TEXT,
                roadmap TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Weekly progress reports
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                week_start DATE,
                week_end DATE,
                dsa_completed INTEGER,
                interviews_practiced INTEGER,
                study_hours REAL,
                progress_data TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username, email, password):
        """Create a new user"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            hashed_pw = self.hash_password(password)
            cursor.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, hashed_pw)
            )
            conn.commit()
            user_id = cursor.lastrowid
            
            # Create empty profile
            cursor.execute(
                'INSERT INTO user_profiles (user_id) VALUES (?)',
                (user_id,)
            )
            conn.commit()
            return True, user_id
        except sqlite3.IntegrityError:
            return False, "Username or email already exists"
        finally:
            conn.close()
    
    def verify_user(self, username, password):
        """Verify user credentials"""
        conn = self.get_connection()
        cursor = conn.cursor()
        hashed_pw = self.hash_password(password)
        
        cursor.execute(
            'SELECT id, username, email FROM users WHERE username = ? AND password = ?',
            (username, hashed_pw)
        )
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return True, {'id': user[0], 'username': user[1], 'email': user[2]}
        return False, None
    
    def update_profile(self, user_id, skills, interests, experience_level, resume_text=None, resume_filename=None):
        """Update user profile"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE user_profiles 
            SET skills = ?, interests = ?, experience_level = ?, resume_text = ?, resume_filename = ?
            WHERE user_id = ?
        ''', (skills, interests, experience_level, resume_text, resume_filename, user_id))
        
        conn.commit()
        conn.close()
    
    def get_profile(self, user_id):
        """Get user profile"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM user_profiles WHERE user_id = ?', (user_id,))
        profile = cursor.fetchone()
        conn.close()
        
        if profile:
            return {
                'user_id': profile[1],
                'skills': profile[2],
                'interests': profile[3],
                'experience_level': profile[4],
                'resume_text': profile[5],
                'resume_filename': profile[6]
            }
        return None
    
    def save_dsa_score(self, user_id, question_id, score, total):
        """Save DSA test score"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO dsa_scores (user_id, question_id, score, total_questions) VALUES (?, ?, ?, ?)',
            (user_id, question_id, score, total)
        )
        conn.commit()
        conn.close()
    
    def save_interview_score(self, user_id, question, answer, sentiment, keyword, overall):
        """Save interview practice score"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO interview_scores 
            (user_id, question, answer, sentiment_score, keyword_score, overall_score) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, question, answer, sentiment, keyword, overall))
        
        conn.commit()
        conn.close()
    
    def get_user_progress(self, user_id):
        """Get comprehensive user progress data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get DSA scores
        cursor.execute('''
            SELECT AVG(score * 100.0 / total_questions) as avg_score, 
                   COUNT(*) as total_attempts
            FROM dsa_scores WHERE user_id = ?
        ''', (user_id,))
        dsa_data = cursor.fetchone()
        
        # Get interview scores
        cursor.execute('''
            SELECT AVG(overall_score) as avg_score, COUNT(*) as total_attempts
            FROM interview_scores WHERE user_id = ?
        ''', (user_id,))
        interview_data = cursor.fetchone()
        
        # Get recent activity
        cursor.execute('''
            SELECT DATE(timestamp) as date, COUNT(*) as count
            FROM dsa_scores WHERE user_id = ?
            GROUP BY DATE(timestamp)
            ORDER BY date DESC LIMIT 7
        ''', (user_id,))
        recent_activity = cursor.fetchall()
        
        conn.close()
        
        return {
            'dsa_avg': dsa_data[0] if dsa_data[0] else 0,
            'dsa_count': dsa_data[1] if dsa_data[1] else 0,
            'interview_avg': interview_data[0] if interview_data[0] else 0,
            'interview_count': interview_data[1] if interview_data[1] else 0,
            'recent_activity': recent_activity
        }
    
    def save_study_schedule(self, user_id, schedule_data):
        """Save study schedule"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO study_schedules (user_id, schedule_data) VALUES (?, ?)',
            (user_id, json.dumps(schedule_data))
        )
        conn.commit()
        conn.close()
    
    def get_latest_schedule(self, user_id):
        """Get latest study schedule"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT schedule_data FROM study_schedules 
            WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return json.loads(result[0])
        return None
    
    def save_job_readiness(self, user_id, target_role, target_company, current_skills, 
                          readiness_score, gaps, roadmap):
        """Save job readiness assessment"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO job_readiness 
            (user_id, target_role, target_company, current_skills, readiness_score, gaps, roadmap)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, target_role, target_company, current_skills, readiness_score, gaps, roadmap))
        
        conn.commit()
        conn.close()
    
    def get_latest_readiness(self, user_id):
        """Get latest job readiness assessment"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM job_readiness 
            WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'target_role': result[2],
                'target_company': result[3],
                'current_skills': result[4],
                'readiness_score': result[5],
                'gaps': result[6],
                'roadmap': result[7],
                'timestamp': result[8]
            }
        return None
    
    def update_weekly_progress(self, user_id, week_start, week_end, dsa_count, 
                              interview_count, study_hours, progress_data):
        """Update weekly progress"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO weekly_progress 
            (user_id, week_start, week_end, dsa_completed, interviews_practiced, 
             study_hours, progress_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, week_start, week_end, dsa_count, interview_count, 
              study_hours, json.dumps(progress_data)))
        
        conn.commit()
        conn.close()