import csv
import time
import sqlite3
from app import app, db
from models import User, Post, Message, Job, Event
from werkzeug.security import generate_password_hash

def populate_database():
    def retry_commit(max_retries=5, delay=1):
        for attempt in range(max_retries):
            try:
                db.session.commit()
                return True
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    print(f"Database locked, retrying in {delay} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    raise e
        return False

    with app.app_context():
        # Populate alumni from CSV
        with open('alumni_dataset.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                alumni_id = row['AluminiID']
                name = row['Name']
                email = row['Email']
                skills = row['Skills']
                education = row['Education']
                # Extract batch year from education, e.g., "CSE (Passing Year 2023)" -> 2023
                batch_year = None
                if 'Passing Year' in education:
                    try:
                        batch_year = int(education.split('Passing Year ')[1].split(')')[0])
                    except:
                        pass
                # Check if user already exists
                existing_user = User.query.filter_by(alumni_id=alumni_id).first()
                if not existing_user:
                    # Make username unique by appending alumni_id if needed
                    username = name
                    counter = 1
                    while User.query.filter_by(username=username).first():
                        username = f"{name}_{counter}"
                        counter += 1
                    try:
                        user = User(
                            username=username,
                            email=email,
                            password=generate_password_hash(alumni_id),  # Password set to alumni_id for direct login
                            role='alumni',
                            alumni_id=alumni_id,
                            batch_year=batch_year,
                            skills=skills
                        )
                        db.session.add(user)
                        if not retry_commit():
                            print(f"Failed to commit user {alumni_id} after retries")
                    except KeyboardInterrupt:
                        print("Password hashing interrupted. Skipping user creation.")
                        continue
                else:
                    # Update existing user's password to alumni_id
                    try:
                        existing_user.password = generate_password_hash(alumni_id)
                        if not retry_commit():
                            print(f"Failed to commit password update for user {alumni_id} after retries")
                    except KeyboardInterrupt:
                        print("Password hashing interrupted. Skipping user update.")
                        continue

        # Populate faculty from CSV
        with open('faculty_dataset.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                faculty_id = row['Faculty ID']
                name = row['Faculty Name']
                email = row['Faculty Mail Address']
                # Check if user already exists
                existing_user = User.query.filter_by(faculty_id=faculty_id).first()
                if not existing_user:
                    # Make username unique by appending faculty_id if needed
                    username = name
                    counter = 1
                    while User.query.filter_by(username=username).first():
                        username = f"{name}_{counter}"
                        counter += 1
                    try:
                        user = User(
                            username=username,
                            email=email,
                            password=generate_password_hash(faculty_id),  # Password set to faculty_id for direct login
                            role='faculty',
                            faculty_id=faculty_id
                        )
                    except KeyboardInterrupt:
                        print("Password hashing interrupted. Skipping faculty user creation.")
                        continue
                    db.session.add(user)
                    if not retry_commit():
                        print(f"Failed to commit faculty user {faculty_id} after retries")
                else:
                    # Update existing user's password to faculty_id
                    try:
                        existing_user.password = generate_password_hash(faculty_id)
                        if not retry_commit():
                            print(f"Failed to commit password update for faculty user {faculty_id} after retries")
                    except KeyboardInterrupt:
                        print("Password hashing interrupted. Skipping faculty user update.")
                        continue

        # Sample posts
        posts = [
            Post(user_id=1, content='Excited to connect!', audience='all'),
            Post(user_id=2, content='Looking for internship opportunities.', audience='alumni'),
        ]
        for post in posts:
            db.session.add(post)
        retry_commit()

        # Sample jobs
        jobs = [
            Job(user_id=1, title='Software Engineer', description='Develop web apps.', job_type='job'),
            Job(user_id=4, title='Data Analyst Intern', description='Analyze data.', job_type='internship'),
        ]
        for job in jobs:
            db.session.add(job)
        retry_commit()

        # Sample events
        from datetime import datetime
        events = [
            Event(user_id=1, title='Alumni Meetup', description='Catch up with old friends.', date=datetime(2023, 12, 1, 10, 0), location='Campus', registration_link=None),
        ]
        for event in events:
            db.session.add(event)
        retry_commit()

    print("Sample data populated!")

if __name__ == '__main__':
    try:
        populate_database()
        print("Database population completed successfully!")
    except KeyboardInterrupt:
        print("Database population interrupted. Please try again.")
    except Exception as e:
        print(f"Error during database population: {e}")