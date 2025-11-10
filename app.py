from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message
from models import db, User, Post, Message, Mentorship, Job, Event, Badge, Question, Answer, Connection, RSVP, JobApplication, Activity, Like, Comment, Notification
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from index import build_inverted_index, search_inverted_index, rank_results
import os
import uuid
from datetime import datetime, timedelta

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'avi', 'mov'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_activity(user_id, activity_type, description, related_id=None):
    activity = Activity(user_id=user_id, activity_type=activity_type, description=description, related_id=related_id)
    db.session.add(activity)
    db.session.commit()

def create_notification(user_id, notification_type, title, message, related_id=None):
    notification = Notification(user_id=user_id, type=notification_type, title=title, message=message, related_id=related_id)
    db.session.add(notification)
    db.session.commit()

def format_datetime_ist(dt):
    """Convert UTC datetime to IST and format it"""
    if dt:
        # IST is UTC+5:30
        ist_time = dt + timedelta(hours=5, minutes=30)
        return ist_time.strftime('%b %d, %I:%M %p')
    return ''

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
    # Email functionality is currently disabled
    # To enable email notifications, uncomment the mail configuration in app.py
    # and set up proper SMTP credentials
    print(f"Job notification would be sent to students for: {job.title}")
    print("Email functionality is currently disabled. Configure MAIL settings to enable.")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///alumni.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail configuration - DISABLED for now (commented out)
# app.config['MAIL_SERVER'] = 'smtp.gmail.com'
# app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USERNAME'] = 'your-email@gmail.com'  # Replace with actual email
# app.config['MAIL_PASSWORD'] = 'your-app-password'    # Replace with app password
# app.config['MAIL_DEFAULT_SENDER'] = 'your-email@gmail.com'

# Initialize mail without configuration (disabled)
mail = Mail(app)

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
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already registered!')
                return redirect(url_for('register'))
            # Check if username already exists
            existing_username = User.query.filter_by(username=username).first()
            if existing_username:
                flash('Username already taken!')
                return redirect(url_for('register'))
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
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))
    posts = Post.query.filter((Post.audience == user.role) | (Post.audience == 'all')).order_by(Post.timestamp.desc()).limit(10).all()

    # Calculate user stats
    posts_count = Post.query.filter_by(user_id=user.id).count()

    # Count actual accepted connections
    connections_count = Connection.query.filter(
        ((Connection.sender_id == user.id) | (Connection.receiver_id == user.id)) &
        (Connection.status == 'accepted')
    ).count()

    badges_count = Badge.query.filter_by(user_id=user.id).count()

    # Get recent activities from connections and general activities
    connection_ids = db.session.query(Connection.sender_id).filter(
        Connection.receiver_id == user.id, Connection.status == 'accepted'
    ).union(
        db.session.query(Connection.receiver_id).filter(
            Connection.sender_id == user.id, Connection.status == 'accepted'
        )
    ).subquery()

    activities = Activity.query.filter(
        db.or_(
            Activity.user_id.in_(connection_ids),
            Activity.user_id == user.id
        )
    ).order_by(Activity.created_at.desc()).limit(20).all()

    # Get recent notifications
    recent_notifications = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(5).all()

    return render_template('dashboard.html', user=user, posts=posts, posts_count=posts_count, connections_count=connections_count, badges_count=badges_count, activities=activities, recent_notifications=recent_notifications, format_datetime_ist=format_datetime_ist)

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

    # Create activity
    create_activity(user_id, 'post_created', f'Created a new post', post.id)

    flash('Post created!')
    return redirect(url_for('dashboard'))

@app.route('/messages')
def messages():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    # Get all unique conversations (users who have messaged with current user)
    sent_to = db.session.query(Message.receiver_id).filter_by(sender_id=user_id).distinct().all()
    received_from = db.session.query(Message.sender_id).filter_by(receiver_id=user_id).distinct().all()

    conversation_user_ids = set()
    for user_tuple in sent_to + received_from:
        conversation_user_ids.add(user_tuple[0])

    conversations = []
    for other_user_id in conversation_user_ids:
        if other_user_id != user_id:
            other_user = User.query.get(other_user_id)
            # Get the latest message in this conversation
            latest_message = Message.query.filter(
                ((Message.sender_id == user_id) & (Message.receiver_id == other_user_id)) |
                ((Message.sender_id == other_user_id) & (Message.receiver_id == user_id))
            ).order_by(Message.timestamp.desc()).first()

            if latest_message:
                conversations.append({
                    'user': other_user,
                    'latest_message': latest_message,
                    'unread_count': Message.query.filter_by(sender_id=other_user_id, receiver_id=user_id).count()
                })

    # Sort conversations by latest message timestamp
    conversations.sort(key=lambda x: x['latest_message'].timestamp, reverse=True)

    return render_template('messages.html', conversations=conversations)

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    sender_id = session['user_id']
    receiver_email = request.form['receiver_email']
    content = request.form.get('content')
    media_type = None
    media_path = None

    # Handle media upload
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

    receiver = User.query.filter_by(email=receiver_email).first()
    if receiver:
        # Require either content or media
        if not content and not media_path:
            flash('Message cannot be empty!')
            return redirect(url_for('messages'))

        message = Message(sender_id=sender_id, receiver_id=receiver.id, content=content, media_type=media_type, media_path=media_path)
        db.session.add(message)
        db.session.commit()
        award_badges(sender_id)
        flash('Message sent!')
    else:
        flash('User not found!')
    return redirect(url_for('messages'))

@app.route('/send_chat_message', methods=['POST'])
def send_chat_message():
    if 'user_id' not in session:
        return {'success': False}, 401

    sender_id = session['user_id']
    receiver_id = int(request.form['receiver_id'])
    content = request.form.get('content')
    media_type = None
    media_path = None

    # Handle media upload
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

    # Verify the receiver exists
    receiver = User.query.get(receiver_id)
    if not receiver:
        return {'success': False, 'error': 'User not found'}, 404

    # Require either content or media
    if not content and not media_path:
        return {'success': False, 'error': 'Message cannot be empty'}, 400

    message = Message(sender_id=sender_id, receiver_id=receiver_id, content=content, media_type=media_type, media_path=media_path)
    db.session.add(message)
    db.session.commit()
    award_badges(sender_id)

    # Create activity
    receiver = User.query.get(receiver_id)
    create_activity(sender_id, 'message_sent', f'Sent a message to {receiver.username}')

    # Create notification for receiver
    sender = User.query.get(sender_id)
    if content:
        notification_message = f"{sender.username} sent you a message: {content[:50]}{'...' if len(content) > 50 else ''}"
    else:
        notification_message = f"{sender.username} sent you a media message"
    create_notification(receiver_id, 'message', 'New Message', notification_message, message.id)

    return {
        'success': True,
        'message': {
            'content': content,
            'media_type': media_type,
            'media_path': media_path,
            'timestamp': message.timestamp.isoformat(),
            'sender_id': sender_id
        }
    }

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

        # Create activity
        create_activity(user_id, 'job_posted', f'Posted a new job: {title}', job.id)

        # Send email notification to all students
        send_job_notification(job)

        flash('Job posted successfully!')
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
        registration_link = request.form.get('registration_link')
        event = Event(user_id=user_id, title=title, description=description, date=date, location=location, registration_link=registration_link)
        db.session.add(event)
        db.session.commit()
        award_badges(user_id)

        # Create activity
        create_activity(user_id, 'event_created', f'Created a new event: {title}', event.id)

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

    # Create notification for event creator if status is 'yes'
    if status == 'yes':
        event = Event.query.get(event_id)
        if event and event.user_id != user_id:  # Don't notify if user is the event creator
            attendee = User.query.get(user_id)
            create_notification(event.user_id, 'event_rsvp', 'New Event RSVP',
                              f'{attendee.username} is attending your event: {event.title}', rsvp.id)

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

    # Remove existing position badges
    db.session.query(Badge).filter(Badge.badge_type.in_(['1st Place', '2nd Place', '3rd Place'])).delete()
    db.session.commit()

    # Assign position badges to top 3
    for i, item in enumerate(scores[:3]):
        badge_type = f"{i+1}st Place" if i == 0 else f"{i+1}nd Place" if i == 1 else f"{i+1}rd Place"
        badge = Badge(user_id=item['user'].id, badge_type=badge_type)
        db.session.add(badge)
    db.session.commit()

    # Add position badge info to scores
    for item in scores:
        position_badges = Badge.query.filter(
            Badge.user_id == item['user'].id,
            Badge.badge_type.in_(['1st Place', '2nd Place', '3rd Place'])
        ).all()
        item['position_badge'] = position_badges[0] if position_badges else None

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
    total_results = 0
    page = int(request.args.get('page', 1))
    per_page = 15

    # Get current user's connections for checking connection status
    current_user_id = session['user_id']
    connections = Connection.query.filter(
        ((Connection.sender_id == current_user_id) | (Connection.receiver_id == current_user_id)) &
        (Connection.status == 'accepted')
    ).all()

    # Get current user's accepted connections for mutual connections calculation
    user_connections = set()
    for conn in connections:
        if conn.sender_id == current_user_id:
            user_connections.add(conn.receiver_id)
        else:
            user_connections.add(conn.sender_id)

    if request.method == 'POST':
        query = request.form['query']
        inverted_index = build_inverted_index()
        user_ids = search_inverted_index(query, inverted_index)
        ranked_ids = rank_results(user_ids, query, inverted_index)
        total_results = len(ranked_ids)

        # Pagination
        start = (page - 1) * per_page
        end = start + per_page
        paginated_ids = ranked_ids[start:end]
        results = [User.query.get(uid) for uid in paginated_ids]

        # Calculate mutual connections for each result
        for user in results:
            if user.id != current_user_id:
                user_connections_set = set()
                user_conns = Connection.query.filter(
                    ((Connection.sender_id == user.id) | (Connection.receiver_id == user.id)) &
                    (Connection.status == 'accepted')
                ).all()
                for conn in user_conns:
                    if conn.sender_id == user.id:
                        user_connections_set.add(conn.receiver_id)
                    else:
                        user_connections_set.add(conn.sender_id)
                mutual_count = len(user_connections & user_connections_set)
                user.mutual_connections = mutual_count
            else:
                user.mutual_connections = 0

        # Store query in session for pagination links
        session['search_query'] = query
    else:
        # Handle pagination for GET requests
        query = session.get('search_query', '')
        if query:
            inverted_index = build_inverted_index()
            user_ids = search_inverted_index(query, inverted_index)
            ranked_ids = rank_results(user_ids, query, inverted_index)
            total_results = len(ranked_ids)

            start = (page - 1) * per_page
            end = start + per_page
            paginated_ids = ranked_ids[start:end]
            results = [User.query.get(uid) for uid in paginated_ids]

            # Calculate mutual connections for each result
            for user in results:
                if user.id != current_user_id:
                    user_connections_set = set()
                    user_conns = Connection.query.filter(
                        ((Connection.sender_id == user.id) | (Connection.receiver_id == user.id)) &
                        (Connection.status == 'accepted')
                    ).all()
                    for conn in user_conns:
                        if conn.sender_id == user.id:
                            user_connections_set.add(conn.receiver_id)
                        else:
                            user_connections_set.add(conn.sender_id)
                    mutual_count = len(user_connections & user_connections_set)
                    user.mutual_connections = mutual_count
                else:
                    user.mutual_connections = 0

    total_pages = (total_results + per_page - 1) // per_page
    return render_template('search.html', results=results, query=query, page=page, total_pages=total_pages, total_results=total_results, connections=connections)

@app.route('/myconnections')
def myconnections():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    # Get connection requests (pending connections where user is receiver)
    connection_requests = Connection.query.filter_by(receiver_id=user_id, status='pending').all()

    # Get accepted connections (where user is sender or receiver)
    connections = Connection.query.filter(
        ((Connection.sender_id == user_id) | (Connection.receiver_id == user_id)) & (Connection.status == 'accepted')
    ).all()

    return render_template('myconnections.html', connection_requests=connection_requests, connections=connections)

@app.route('/send_connection_request', methods=['POST'])
def send_connection_request():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    sender_id = session['user_id']
    receiver_id = request.form['receiver_id']

    # Check if connection already exists
    existing_connection = Connection.query.filter(
        ((Connection.sender_id == sender_id) & (Connection.receiver_id == receiver_id)) |
        ((Connection.sender_id == receiver_id) & (Connection.receiver_id == sender_id))
    ).first()

    if not existing_connection:
        connection = Connection(sender_id=sender_id, receiver_id=receiver_id)
        db.session.add(connection)
        db.session.commit()

        # Create activity
        receiver = User.query.get(receiver_id)
        create_activity(sender_id, 'connection_sent', f'Sent connection request to {receiver.username}')

        # Create notification for receiver
        sender = User.query.get(sender_id)
        create_notification(receiver_id, 'connection_request', 'New Connection Request',
                          f'{sender.username} sent you a connection request', connection.id)

        flash('Connection request sent!')
    else:
        flash('Connection already exists or request already sent!')

    return redirect(url_for('search'))

@app.route('/respond_connection/<int:request_id>', methods=['POST'])
def respond_connection(request_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = Connection.query.get(request_id)
    if connection and connection.receiver_id == session['user_id']:
        action = request.form['action']
        if action == 'accept':
            connection.status = 'accepted'
            flash('Connection request accepted!')

            # Create notification for sender
            receiver = User.query.get(session['user_id'])
            create_notification(connection.sender_id, 'connection_accepted', 'Connection Request Accepted',
                              f'{receiver.username} accepted your connection request', connection.id)

        elif action == 'reject':
            connection.status = 'rejected'
            flash('Connection request rejected!')

            # Create notification for sender
            receiver = User.query.get(session['user_id'])
            create_notification(connection.sender_id, 'connection_rejected', 'Connection Request Declined',
                              f'{receiver.username} declined your connection request', connection.id)

        db.session.commit()

    return redirect(url_for('myconnections'))

@app.route('/view_profile/<int:user_id>')
def view_profile(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user_id = session['user_id']
    user = User.query.get_or_404(user_id)

    # Check if already connected
    connection = Connection.query.filter(
        ((Connection.sender_id == current_user_id) & (Connection.receiver_id == user_id)) |
        ((Connection.sender_id == user_id) & (Connection.receiver_id == current_user_id)) &
        (Connection.status == 'accepted')
    ).first()
    is_connected = connection is not None

    # Calculate mutual connections
    current_user_connections = set()
    user_connections = set()

    # Get current user's connections
    current_conns = Connection.query.filter(
        ((Connection.sender_id == current_user_id) | (Connection.receiver_id == current_user_id)) &
        (Connection.status == 'accepted')
    ).all()
    for conn in current_conns:
        if conn.sender_id == current_user_id:
            current_user_connections.add(conn.receiver_id)
        else:
            current_user_connections.add(conn.sender_id)

    # Get profile user's connections
    profile_conns = Connection.query.filter(
        ((Connection.sender_id == user_id) | (Connection.receiver_id == user_id)) &
        (Connection.status == 'accepted')
    ).all()
    for conn in profile_conns:
        if conn.sender_id == user_id:
            user_connections.add(conn.receiver_id)
        else:
            user_connections.add(conn.sender_id)

    mutual_connections = current_user_connections & user_connections
    mutual_count = len(mutual_connections)

    # Get user's posts
    posts = Post.query.filter_by(user_id=user_id).order_by(Post.timestamp.desc()).all()

    return render_template('view_profile.html', user=user, is_connected=is_connected, posts=posts, mutual_count=mutual_count)

@app.route('/apply_job/<int:job_id>', methods=['POST'])
def apply_job(job_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    job = Job.query.get_or_404(job_id)

    # Check if already applied
    existing_application = JobApplication.query.filter_by(job_id=job_id, applicant_id=user_id).first()
    if existing_application:
        flash('You have already applied for this job!')
        return redirect(url_for('view_job', job_id=job_id))

    application = JobApplication(job_id=job_id, applicant_id=user_id)
    db.session.add(application)
    db.session.commit()

    # Create activity
    create_activity(user_id, 'job_applied', f'Applied for job: {job.title}', job.id)

    # Create notification for job poster
    applicant = User.query.get(user_id)
    create_notification(job.user_id, 'job_application', 'New Job Application',
                      f'{applicant.username} applied for your job: {job.title}', application.id)

    flash('Application submitted successfully!')
    return redirect(url_for('view_job', job_id=job_id))

@app.route('/view_job/<int:job_id>')
def view_job(job_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    job = Job.query.get_or_404(job_id)
    user = User.query.get(session['user_id'])
    is_poster = job.user_id == user.id
    has_applied = JobApplication.query.filter_by(job_id=job_id, applicant_id=user.id).first() is not None
    return render_template('view_job.html', job=job, is_poster=is_poster, has_applied=has_applied)

@app.route('/chat/<int:user_id>')
def chat(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user_id = session['user_id']
    other_user = User.query.get_or_404(user_id)

    # Get all messages between current user and the other user
    messages = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user_id))
    ).order_by(Message.timestamp).all()

    return render_template('chat.html', other_user=other_user, messages=messages)

@app.route('/view_applications/<int:job_id>')
def view_applications(job_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    job = Job.query.get_or_404(job_id)
    if job.user_id != session['user_id']:
        flash('You can only view applications for your own job posts!')
        return redirect(url_for('jobs'))
    applications = JobApplication.query.filter_by(job_id=job_id).all()
    return render_template('view_applications.html', job=job, applications=applications)

@app.route('/send_message_to_applicants/<int:job_id>', methods=['POST'])
def send_message_to_applicants(job_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    job = Job.query.get_or_404(job_id)
    if job.user_id != session['user_id']:
        flash('You can only message applicants for your own job posts!')
        return redirect(url_for('jobs'))

    message_content = request.form['message']
    applications = JobApplication.query.filter_by(job_id=job_id).all()

    for application in applications:
        message = Message(sender_id=session['user_id'], receiver_id=application.applicant_id, content=message_content)
        db.session.add(message)

    db.session.commit()
    flash(f'Message sent to {len(applications)} applicants!')
    return redirect(url_for('view_applications', job_id=job_id))

@app.route('/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return {'success': False}, 401

    user_id = session['user_id']
    existing_like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()

    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        liked = False
    else:
        like = Like(user_id=user_id, post_id=post_id)
        db.session.add(like)
        db.session.commit()
        liked = True

    like_count = Like.query.filter_by(post_id=post_id).count()
    return {'success': True, 'liked': liked, 'like_count': like_count}

@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return {'success': False}, 401

    user_id = session['user_id']
    content = request.form.get('content')

    if not content or not content.strip():
        return {'success': False, 'error': 'Comment cannot be empty'}, 400

    comment = Comment(user_id=user_id, post_id=post_id, content=content.strip())
    db.session.add(comment)
    db.session.commit()

    # Create activity
    post = Post.query.get(post_id)
    create_activity(user_id, 'comment_added', f'Commented on {post.user.username}\'s post')

    return {
        'success': True,
        'comment': {
            'id': comment.id,
            'content': comment.content,
            'username': comment.user.username,
            'created_at': format_datetime_ist(comment.created_at)
        }
    }

@app.route('/get_comments/<int:post_id>')
def get_comments(post_id):
    if 'user_id' not in session:
        return {'success': False}, 401

    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at).all()
    comments_data = [{
        'id': comment.id,
        'content': comment.content,
        'username': comment.user.username,
        'created_at': format_datetime_ist(comment.created_at)
    } for comment in comments]

    return {'success': True, 'comments': comments_data}

@app.route('/remove_connection/<int:connection_id>', methods=['POST'])
def remove_connection(connection_id):
    if 'user_id' not in session:
        return {'success': False}, 401

    connection = Connection.query.get(connection_id)
    if connection and (connection.sender_id == session['user_id'] or connection.receiver_id == session['user_id']):
        db.session.delete(connection)
        db.session.commit()
        return {'success': True}
    return {'success': False}, 400

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_notifications = Notification.query.filter_by(user_id=session['user_id']).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=user_notifications)

@app.route('/mark_notification_read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return {'success': False}, 401

    notification = Notification.query.get(notification_id)
    if notification and notification.user_id == session['user_id']:
        notification.is_read = True
        db.session.commit()
        return {'success': True}
    return {'success': False}, 404

@app.route('/mark_all_notifications_read', methods=['POST'])
def mark_all_notifications_read():
    if 'user_id' not in session:
        return {'success': False}, 401

    Notification.query.filter_by(user_id=session['user_id'], is_read=False).update({'is_read': True})
    db.session.commit()
    return {'success': True}

@app.route('/delete_notification/<int:notification_id>', methods=['POST'])
def delete_notification(notification_id):
    if 'user_id' not in session:
        return {'success': False}, 401

    notification = Notification.query.get(notification_id)
    if notification and notification.user_id == session['user_id']:
        db.session.delete(notification)
        db.session.commit()
        return {'success': True}
    return {'success': False}, 404

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)