import re
import json
from datetime import datetime, timedelta
from collections import Counter
import math

class AIEngine:
    def __init__(self):
        # Skill database for different roles
        self.role_skills = {
            'Software Development Engineer (SDE)': {
                'required': ['data structures', 'algorithms', 'problem solving', 'coding', 'dsa', 'python', 'java', 'c++'],
                'preferred': ['system design', 'databases', 'git', 'testing', 'debugging', 'object oriented programming'],
                'weight': 1.0
            },
            'Web Developer': {
                'required': ['html', 'css', 'javascript', 'react', 'web development', 'frontend'],
                'preferred': ['backend', 'node.js', 'databases', 'rest api', 'git', 'responsive design'],
                'weight': 0.9
            },
            'Data Scientist': {
                'required': ['python', 'machine learning', 'statistics', 'data analysis', 'ml', 'ai'],
                'preferred': ['tensorflow', 'pandas', 'numpy', 'visualization', 'deep learning', 'sql'],
                'weight': 1.0
            },
            'DevOps Engineer': {
                'required': ['linux', 'docker', 'kubernetes', 'ci/cd', 'automation', 'cloud'],
                'preferred': ['aws', 'azure', 'jenkins', 'monitoring', 'scripting'],
                'weight': 0.85
            },
            'Mobile Developer': {
                'required': ['android', 'ios', 'mobile', 'app development', 'java', 'swift', 'kotlin'],
                'preferred': ['react native', 'flutter', 'ui/ux', 'apis', 'firebase'],
                'weight': 0.9
            }
        }
        
        # HR interview keywords
        self.positive_keywords = [
            'team', 'collaborate', 'leadership', 'problem-solving', 'innovative',
            'dedicated', 'passionate', 'achieved', 'successful', 'improved',
            'learned', 'developed', 'managed', 'created', 'implemented',
            'challenge', 'solution', 'growth', 'responsibility', 'communication'
        ]
        
        self.negative_keywords = [
            'never', 'cannot', 'unable', 'failed', 'quit', 'difficult',
            'impossible', 'hate', 'boring', 'lazy'
        ]
    
    def analyze_resume(self, resume_text):
        """Analyze resume using NLP techniques"""
        resume_lower = resume_text.lower()
        
        # Extract skills
        found_skills = []
        for role, skills_dict in self.role_skills.items():
            all_skills = skills_dict['required'] + skills_dict['preferred']
            for skill in all_skills:
                if skill in resume_lower:
                    found_skills.append(skill)
        
        found_skills = list(set(found_skills))
        
        # Calculate role matches
        role_scores = {}
        for role, skills_dict in self.role_skills.items():
            required = skills_dict['required']
            preferred = skills_dict['preferred']
            
            required_match = sum(1 for s in required if s in found_skills)
            preferred_match = sum(1 for s in preferred if s in found_skills)
            
            required_score = (required_match / len(required)) * 100 if required else 0
            preferred_score = (preferred_match / len(preferred)) * 50 if preferred else 0
            
            total_score = (required_score + preferred_score) * skills_dict['weight']
            role_scores[role] = round(total_score, 2)
        
        # Sort roles by score
        recommended_roles = sorted(role_scores.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'skills_found': found_skills,
            'skill_count': len(found_skills),
            'recommended_roles': recommended_roles[:3],
            'top_role': recommended_roles[0][0] if recommended_roles else 'General Software Developer'
        }
    
    def evaluate_dsa_answer(self, user_answer, correct_answer):
        """Simple DSA answer evaluation"""
        user_clean = user_answer.lower().strip()
        correct_clean = str(correct_answer).lower().strip()
        
        # Exact match
        if user_clean == correct_clean:
            return True, 100
        
        # Partial match for numeric answers
        try:
            user_num = float(user_clean)
            correct_num = float(correct_clean)
            if abs(user_num - correct_num) < 0.01:
                return True, 100
        except:
            pass
        
        return False, 0
    
    def evaluate_interview_answer(self, question, answer):
        """Evaluate interview answer using sentiment and keyword analysis"""
        answer_lower = answer.lower()
        
        # Sentiment score based on keywords
        positive_count = sum(1 for word in self.positive_keywords if word in answer_lower)
        negative_count = sum(1 for word in self.negative_keywords if word in answer_lower)
        
        # Calculate sentiment score (0-100)
        if positive_count + negative_count > 0:
            sentiment_score = (positive_count / (positive_count + negative_count)) * 100
        else:
            sentiment_score = 50
        
        # Keyword relevance score
        keyword_score = min(100, positive_count * 10)
        
        # Length score (penalize too short or too long)
        word_count = len(answer.split())
        if word_count < 20:
            length_score = word_count * 3
        elif word_count > 200:
            length_score = max(0, 100 - (word_count - 200) * 0.5)
        else:
            length_score = 100
        
        # Overall score
        overall_score = (sentiment_score * 0.4 + keyword_score * 0.3 + length_score * 0.3)
        
        # Generate feedback
        feedback = self._generate_interview_feedback(sentiment_score, keyword_score, length_score)
        
        return {
            'sentiment_score': round(sentiment_score, 2),
            'keyword_score': round(keyword_score, 2),
            'length_score': round(length_score, 2),
            'overall_score': round(overall_score, 2),
            'feedback': feedback
        }
    
    def _generate_interview_feedback(self, sentiment, keyword, length):
        """Generate personalized feedback"""
        feedback = []
        
        if sentiment < 40:
            feedback.append("Try to use more positive and confident language.")
        elif sentiment > 80:
            feedback.append("Great positive attitude!")
        
        if keyword < 30:
            feedback.append("Include more relevant professional keywords.")
        elif keyword > 70:
            feedback.append("Excellent use of professional terminology!")
        
        if length < 60:
            feedback.append("Provide more detailed examples and explanations.")
        elif length > 80:
            feedback.append("Good level of detail in your response!")
        
        return " ".join(feedback) if feedback else "Good response overall!"
    
    def calculate_job_readiness(self, current_skills, target_role, target_company=None):
        """Calculate job readiness score and identify gaps"""
        current_skills_lower = [s.lower().strip() for s in current_skills.split(',')]
        
        if target_role not in self.role_skills:
            # Find closest match
            target_role = self._find_closest_role(target_role)
        
        role_data = self.role_skills[target_role]
        required_skills = role_data['required']
        preferred_skills = role_data['preferred']
        
        # Calculate matches
        required_match = [s for s in required_skills if any(cs in s or s in cs for cs in current_skills_lower)]
        preferred_match = [s for s in preferred_skills if any(cs in s or s in cs for cs in current_skills_lower)]
        
        # Calculate readiness score
        required_score = (len(required_match) / len(required_skills)) * 70
        preferred_score = (len(preferred_match) / len(preferred_skills)) * 30
        readiness_score = required_score + preferred_score
        
        # Identify gaps
        missing_required = [s for s in required_skills if s not in required_match]
        missing_preferred = [s for s in preferred_skills if s not in preferred_match]
        
        return {
            'readiness_score': round(readiness_score, 2),
            'required_match': required_match,
            'preferred_match': preferred_match,
            'missing_required': missing_required,
            'missing_preferred': missing_preferred,
            'status': self._get_readiness_status(readiness_score)
        }
    
    def _get_readiness_status(self, score):
        """Get readiness status message"""
        if score >= 80:
            return "Excellent! You're highly ready for this role."
        elif score >= 60:
            return "Good! You're moderately ready. Focus on filling the gaps."
        elif score >= 40:
            return "Fair. You need to work on several key skills."
        else:
            return "Needs Improvement. Focus on building foundational skills first."
    
    def _find_closest_role(self, target_role):
        """Find closest matching role"""
        target_lower = target_role.lower()
        for role in self.role_skills.keys():
            if any(word in role.lower() for word in target_lower.split()):
                return role
        return 'Software Development Engineer (SDE)'
    
    def generate_roadmap(self, missing_required, missing_preferred, readiness_score, weeks=12):
        """Generate a flexible learning roadmap"""
        roadmap = {
            'total_weeks': weeks,
            'phases': []
        }
        
        all_skills = missing_required + missing_preferred[:3]  # Prioritize top 3 preferred
        
        if not all_skills:
            return {
                'total_weeks': 0,
                'phases': [{
                    'phase': 1,
                    'title': 'Maintenance & Practice',
                    'skills': ['Continue practicing', 'Build projects', 'Stay updated'],
                    'duration_weeks': 4
                }]
            }
        
        skills_per_phase = max(2, len(all_skills) // 3)
        
        for i in range(0, len(all_skills), skills_per_phase):
            phase_skills = all_skills[i:i+skills_per_phase]
            phase_num = (i // skills_per_phase) + 1
            phase_weeks = weeks // 3
            
            roadmap['phases'].append({
                'phase': phase_num,
                'title': f'Phase {phase_num}: {", ".join(phase_skills[:2])}',
                'skills': phase_skills,
                'duration_weeks': phase_weeks,
                'resources': self._get_learning_resources(phase_skills)
            })
        
        return roadmap
    
    def _get_learning_resources(self, skills):
        """Get learning resources for skills"""
        resources = []
        for skill in skills:
            if 'algorithm' in skill or 'dsa' in skill:
                resources.append(f"LeetCode, HackerRank for {skill}")
            elif 'web' in skill or 'javascript' in skill or 'react' in skill:
                resources.append(f"FreeCodeCamp, MDN Docs for {skill}")
            elif 'python' in skill or 'java' in skill:
                resources.append(f"Official {skill} documentation, Codecademy")
            elif 'machine learning' in skill or 'ai' in skill:
                resources.append(f"Coursera ML course, Kaggle for {skill}")
            else:
                resources.append(f"YouTube tutorials, Udemy courses for {skill}")
        
        return resources
    
    def generate_study_schedule(self, roadmap, hours_per_day=2, study_days_per_week=5):
        """Generate daily study schedule based on roadmap"""
        schedule = {
            'daily_hours': hours_per_day,
            'days_per_week': study_days_per_week,
            'weekly_schedule': []
        }
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        study_days = days[:study_days_per_week]
        
        current_phase = 0
        phases = roadmap['phases']
        
        if not phases:
            return schedule
        
        # Distribute skills across study days
        for day in study_days:
            if current_phase < len(phases):
                phase = phases[current_phase]
                skills = phase['skills']
                
                day_schedule = {
                    'day': day,
                    'focus_skills': skills[:2],  # Max 2 skills per day
                    'activities': [
                        f"Study {skills[0]} - {hours_per_day * 0.6:.1f} hours",
                        f"Practice {skills[1] if len(skills) > 1 else skills[0]} - {hours_per_day * 0.4:.1f} hours"
                    ],
                    'revision': current_phase > 0
                }
                
                schedule['weekly_schedule'].append(day_schedule)
                
                # Rotate through phases
                current_phase = (current_phase + 1) % len(phases)
        
        # Add weekend revision
        schedule['weekend_revision'] = {
            'Saturday': 'Review all skills from the week',
            'Sunday': 'Practice problems and build mini-project'
        }
        
        return schedule
    
    def generate_revision_timetable(self, learned_skills, days=7):
        """Generate revision timetable using spaced repetition"""
        revision_schedule = []
        
        for i, skill in enumerate(learned_skills):
            # Spaced repetition: Day 1, Day 3, Day 7
            revision_days = [1, 3, 7]
            
            for day in revision_days:
                if day <= days:
                    revision_schedule.append({
                        'day': day,
                        'skill': skill,
                        'activity': f'Revise {skill}',
                        'duration': '30 minutes'
                    })
        
        # Sort by day
        revision_schedule.sort(key=lambda x: x['day'])
        
        return revision_schedule
    
    def calculate_weekly_progress_score(self, dsa_completed, interviews_practiced, 
                                       study_hours, target_dsa=5, target_interviews=3, 
                                       target_hours=10):
        """Calculate weekly progress score"""
        dsa_score = min(100, (dsa_completed / target_dsa) * 100)
        interview_score = min(100, (interviews_practiced / target_interviews) * 100)
        hours_score = min(100, (study_hours / target_hours) * 100)
        
        overall_score = (dsa_score * 0.4 + interview_score * 0.3 + hours_score * 0.3)
        
        return {
            'dsa_score': round(dsa_score, 2),
            'interview_score': round(interview_score, 2),
            'hours_score': round(hours_score, 2),
            'overall_score': round(overall_score, 2),
            'grade': self._get_grade(overall_score)
        }
    
    def _get_grade(self, score):
        """Convert score to grade"""
        if score >= 90:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 70:
            return 'B+'
        elif score >= 60:
            return 'B'
        elif score >= 50:
            return 'C'
        else:
            return 'D'