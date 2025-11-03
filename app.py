from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
from models import db, User, Post, Message, Mentorship, Job, Event, Badge, Question, Answer
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from index import build_inverted_index, search_inverted_index, rank_results
import os
import uuid

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def award_badges(user_id):
    user = User.query.get(user_id)
    posts_count = Post.query.filter_by(user_id=user_id).count()
    messages_count = Message.query.filter_by(sender_id=user_id).count()
    jobs_count = Job.query.filter_by(user_id=user_id).count()
    events_count = Event.query.filter_by(user_id=user_id).count()

    badges = []

    if posts_count >= 1 and not Badge.query.filter_by(user_id=user_id, badge_type='First Post').first():
        badges.append(Badge(user_id=user_id, badge_type='First Post'))

    if posts_count >= 5 and not Badge.query.filter_by(user_id=user_id, badge_type='Active Poster').first():
        badges.append(Badge(user_id=user_id, badge_type='Active Poster'))

    if messages_count >= 10 and not Badge.query.filter_by(user_id=user_id, badge_type='Social Butterfly').first():
        badges.append(Badge(user_id=user_id, badge_type='Social Butterfly'))

    if jobs_count >= 1 and not Badge.query.filter_by(user_id=user_id, badge_type='Job Creator').first():
        badges.append(Badge(user_id=user_id, badge_type='Job Creator'))

    if events_count >= 1 and not Badge.query.filter_by(user_id=user_id, badge_type='Event Organizer').first():
        badges.append(Badge(user_id=user_id, badge_type='Event Organizer'))

    for badge in badges:
        db.session.add(badge)
    db.session.commit()

def send_job_notification(job):
    """Send email notification to all registered students about new job posting"""
    try:
        # Get all student emails
        students = User.query.filter_by(role='student').all()
        student_emails = [student.email for student in students]

        if not student_emails:
            return

        # Create email message
        msg = Message(
            subject=f'New Job Opportunity: {job.title}',
            recipients=student_emails,
            body=f'''
Dear Student,

A new job opportunity has been posted on the Alumni Platform:

Job Title: {job.title}
Job Type: {job.job_type}
Description: {job.description}

Posted by: {job.user.username}
Posted on: {job.created_at.strftime('%Y-%m-%d %H:%M')}

Visit the Alumni Platform to view more details and apply!

Best regards,
Alumni Platform Team
            '''
        )

        # Send email
        mail.send(msg)
        print(f"Job notification sent to {len(student_emails)} students")

    except Exception as e:
        print(f"Error sending job notification: {e}")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///alumni.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'  # Replace with actual email
app.config['MAIL_PASSWORD'] = 'your-app-password'    # Replace with app password
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@gmail.com'

mail = Mail(app)
db.init_app(app)

# Create database
with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']
        batch_year = request.form.get('batch_year')
        skills = request.form.get('skills')

        # For alumni and faculty, validate ID
        alumni_id = None
        faculty_id = None
        if role == 'alumni':
            alumni_id = request.form.get('alumni_id')
            if not alumni_id:
                flash('Alumni ID is required!')
                return redirect(url_for('register'))
            # Check if alumni_id exists in database
            existing_alumni = User.query.filter_by(alumni_id=alumni_id).first()
            if not existing_alumni:
                flash('Invalid Alumni ID!')
                return redirect(url_for('register'))
            if existing_alumni.password != generate_password_hash('defaultpass'):
                flash('Account already registered!')
                return redirect(url_for('register'))
            # Update existing user
            existing_alumni.username = username
            existing_alumni.email = email
            existing_alumni.password = password
            existing_alumni.batch_year = batch_year
            existing_alumni.skills = skills
            db.session.commit()
            flash('Registration successful!')
            return redirect(url_for('login'))
        elif role == 'faculty':
            faculty_id = request.form.get('faculty_id')
            if not faculty_id:
                flash('Faculty ID is required!')
                return redirect(url_for('register'))
            # Check if faculty_id exists in database
            existing_faculty = User.query.filter_by(faculty_id=faculty_id).first()
            if not existing_faculty:
                flash('Invalid Faculty ID!')
                return redirect(url_for('register'))
            if existing_faculty.password != generate_password_hash('defaultpass'):
                flash('Account already registered!')
                return redirect(url_for('register'))
            # Update existing user
            existing_faculty.username = username
            existing_faculty.email = email
            existing_faculty.password = password
            db.session.commit()
            flash('Registration successful!')
            return redirect(url_for('login'))
        else:
            # For students, create new user
            new_user = User(username=username, email=email, password=password, role=role, batch_year=batch_year, skills=skills)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful!')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier']  # Can be email, alumni_id, or faculty_id
        password = request.form['password']
        user = None
        # Try to find by email
        user = User.query.filter_by(email=identifier).first()
        if not user:
            # Try to find by alumni_id
            user = User.query.filter_by(alumni_id=identifier).first()
        if not user:
            # Try to find by faculty_id
            user = User.query.filter_by(faculty_id=identifier).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    posts = Post.query.filter((Post.audience == user.role) | (Post.audience == 'all')).order_by(Post.timestamp.desc()).limit(10).all()

    # Calculate user stats
    posts_count = Post.query.filter_by(user_id=user.id).count()
    connections_count = Message.query.filter_by(sender_id=user.id).count() + Message.query.filter_by(receiver_id=user.id).count()
    badges_count = Badge.query.filter_by(user_id=user.id).count()

    return render_template('dashboard.html', user=user, posts=posts, posts_count=posts_count, connections_count=connections_count, badges_count=badges_count)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.username = request.form['username']
        user.email = request.form['email']
        user.batch_year = request.form.get('batch_year')
        user.skills = request.form.get('skills')
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user)

@app.route('/create_post', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    content = request.form['content']
    audience = request.form['audience']
    media_type = None
    media_path = None
    if 'media' in request.files:
        file = request.files['media']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = str(uuid.uuid4()) + '_' + filename
            file_path = os.path.join('static', 'uploads', unique_filename)
            file.save(file_path)
            media_path = unique_filename
            ext = filename.rsplit('.', 1)[1].lower()
            if ext in {'png', 'jpg', 'jpeg', 'gif'}:
                media_type = 'image'
            elif ext in {'mp4', 'avi', 'mov'}:
                media_type = 'video'
    post = Post(user_id=user_id, content=content, audience=audience, media_type=media_type, media_path=media_path)
    db.session.add(post)
    db.session.commit()
    award_badges(user_id)
    flash('Post created!')
    return redirect(url_for('dashboard'))

@app.route('/messages')
def messages():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    received_messages = Message.query.filter_by(receiver_id=user_id).order_by(Message.timestamp.desc()).all()
    return render_template('messages.html', messages=received_messages)

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    sender_id = session['user_id']
    receiver_email = request.form['receiver_email']
    content = request.form['content']
    receiver = User.query.filter_by(email=receiver_email).first()
    if receiver:
        message = Message(sender_id=sender_id, receiver_id=receiver.id, content=content)
        db.session.add(message)
        db.session.commit()
        award_badges(sender_id)
        flash('Message sent!')
    else:
        flash('User not found!')
    return redirect(url_for('messages'))

@app.route('/mentorship')
def mentorship():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = User.query.get(user_id)
    if user.role == 'student':
        # Students can request mentorship
        alumni = User.query.filter_by(role='alumni').all()
        return render_template('mentorship.html', alumni=alumni, requests=[])
    else:
        # Alumni can view requests
        requests = Mentorship.query.filter_by(mentor_id=user_id).all()
        return render_template('mentorship.html', alumni=[], requests=requests)

@app.route('/request_mentorship', methods=['POST'])
def request_mentorship():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    mentee_id = session['user_id']
    mentor_id = request.form['mentor_id']
    mentorship = Mentorship(mentor_id=mentor_id, mentee_id=mentee_id)
    db.session.add(mentorship)
    db.session.commit()
    flash('Mentorship request sent!')
    return redirect(url_for('mentorship'))

@app.route('/respond_mentorship/<int:id>', methods=['POST'])
def respond_mentorship(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    mentorship = Mentorship.query.get(id)
    if mentorship.mentor_id == session['user_id']:
        status = request.form['status']
        mentorship.status = status
        db.session.commit()
        flash(f'Request {status}!')
    return redirect(url_for('mentorship'))

@app.route('/jobs', methods=['GET', 'POST'])
def jobs():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        if user.role == 'student':
            flash('Students cannot post jobs!')
            return redirect(url_for('jobs'))
        user_id = session['user_id']
        title = request.form['title']
        description = request.form['description']
        job_type = request.form['job_type']
        job = Job(user_id=user_id, title=title, description=description, job_type=job_type)
        db.session.add(job)
        db.session.commit()
        award_badges(user_id)

        # Send email notification to all students
        send_job_notification(job)

        flash('Job posted! Students have been notified via email.')
        return redirect(url_for('jobs'))
    jobs_list = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('jobs.html', jobs=jobs_list, user=user)

@app.route('/events', methods=['GET', 'POST'])
def events():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        if user.role == 'student':
            flash('Students cannot create events!')
            return redirect(url_for('events'))
        user_id = session['user_id']
        title = request.form['title']
        description = request.form['description']
        date = request.form['date']
        location = request.form.get('location')
        event = Event(user_id=user_id, title=title, description=description, date=date, location=location)
        db.session.add(event)
        db.session.commit()
        award_badges(user_id)
        flash('Event created!')
        return redirect(url_for('events'))
    events_list = Event.query.order_by(Event.date).all()
    return render_template('events.html', events=events_list, user=user)

@app.route('/rsvp/<int:event_id>', methods=['POST'])
def rsvp(event_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    status = request.form['status']
    rsvp = RSVP.query.filter_by(user_id=user_id, event_id=event_id).first()
    if rsvp:
        rsvp.status = status
    else:
        rsvp = RSVP(user_id=user_id, event_id=event_id, status=status)
        db.session.add(rsvp)
    db.session.commit()
    flash('RSVP updated!')
    return redirect(url_for('events'))

@app.route('/badges')
def badges():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_badges = Badge.query.filter_by(user_id=session['user_id']).all()
    return render_template('badges.html', badges=user_badges)

@app.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    users = User.query.all()
    scores = []
    for user in users:
        score = (Post.query.filter_by(user_id=user.id).count() * 10 +
                 Message.query.filter_by(sender_id=user.id).count() * 5 +
                 Job.query.filter_by(user_id=user.id).count() * 20 +
                 Event.query.filter_by(user_id=user.id).count() * 15 +
                 Badge.query.filter_by(user_id=user.id).count() * 25)
        scores.append({'user': user, 'score': score})
    scores.sort(key=lambda x: x['score'], reverse=True)
    return render_template('leaderboard.html', leaderboard=scores)

@app.route('/metrics')
def metrics():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # Simple metrics
    total_users = User.query.count()
    total_posts = Post.query.count()
    total_messages = Message.query.count()
    total_jobs = Job.query.count()
    total_events = Event.query.count()
    total_badges = Badge.query.count()
    mentorship_requests = Mentorship.query.count()
    accepted_mentorships = Mentorship.query.filter_by(status='accepted').count()

    return render_template('metrics.html',
                           total_users=total_users,
                           total_posts=total_posts,
                           total_messages=total_messages,
                           total_jobs=total_jobs,
                           total_events=total_events,
                           total_badges=total_badges,
                           mentorship_requests=mentorship_requests,
                           accepted_mentorships=accepted_mentorships)

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    results = []
    if request.method == 'POST':
        query = request.form['query']
        inverted_index = build_inverted_index()
        user_ids = search_inverted_index(query, inverted_index)
        ranked_ids = rank_results(user_ids, query, inverted_index)
        results = [User.query.get(uid) for uid in ranked_ids]
    return render_template('search.html', results=results)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)