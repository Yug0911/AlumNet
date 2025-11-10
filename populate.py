import csv
from app import app, db
from models import User, Post, Message, Job, Event
from werkzeug.security import generate_password_hash

def populate_database():
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
            else:
                # Update existing user's password to alumni_id
                existing_user.password = generate_password_hash(alumni_id)
    db.session.commit()

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
                user = User(
                    username=username,
                    email=email,
                    password=generate_password_hash(faculty_id),  # Password set to faculty_id for direct login
                    role='faculty',
                    faculty_id=faculty_id
                )
                db.session.add(user)
            else:
                # Update existing user's password to faculty_id
                existing_user.password = generate_password_hash(faculty_id)
    db.session.commit()

    # Sample posts
    posts = [
        Post(user_id=1, content='Excited to connect!', audience='all'),
        Post(user_id=2, content='Looking for internship opportunities.', audience='alumni'),
    ]
    for post in posts:
        db.session.add(post)
    db.session.commit()

    # Sample jobs
    jobs = [
        Job(user_id=1, title='Software Engineer', description='Develop web apps.', job_type='job'),
        Job(user_id=4, title='Data Analyst Intern', description='Analyze data.', job_type='internship'),
    ]
    for job in jobs:
        db.session.add(job)
    db.session.commit()

    # Sample events
    from datetime import datetime
    events = [
        Event(user_id=1, title='Alumni Meetup', description='Catch up with old friends.', date=datetime(2023, 12, 1, 10, 0), location='Campus'),
    ]
    for event in events:
        db.session.add(event)
    db.session.commit()

    print("Sample data populated!")

if __name__ == '__main__':
    populate_database()