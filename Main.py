from flask import Flask, request, redirect, url_for, render_template_string, session, flash,render_template,jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from geopy.distance import geodesic
import os
import random
from datetime import datetime
import requests
from geopy.geocoders import Nominatim
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'AJDB775DA@#$TBhsYT@#&^FVDAD^&2'


basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'jobconnect.db')}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename, allowed_exts):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_exts

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ------------------ Models ------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=True)  # not used here
    location = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(100), default='Not Provided')  # optional
    about = db.Column(db.String(500))
    skills = db.relationship('Skill', backref='user', lazy=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    state = db.Column(db.String(100))
    zipcode = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    # Define the one-to-one relationship with WorkerProfile
    worker_profile = db.relationship('WorkerProfile', backref='user', uselist=False)


class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rate = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100))  # added this
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    description = db.Column(db.String(500))
    location = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', back_populates='jobs')

User.jobs = db.relationship('Job', back_populates='user')

class Rating(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_giver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stars = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    rater = db.relationship('User', foreign_keys=[job_giver_id])



class WorkerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_code = db.Column(db.String(20), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    qualification = db.Column(db.String(100))
    experience = db.Column(db.String(100))
    about = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    state = db.Column(db.String(100))
    zipcode = db.Column(db.String(20))
    photo = db.Column(db.String(200))  # File path to image
    video = db.Column(db.String(200))  # File path to video
    photo = db.Column(db.String(200))   # store filename (e.g., "1_profile.jpg")
    video = db.Column(db.String(200))   # optional, for future use
    phone = db.Column(db.String(20))

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    provider_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Job giver
    worker_id = db.Column(db.Integer, db.ForeignKey('user.id'))    # Worker
    status = db.Column(db.String(20), default='pending')           # pending / accepted / declined

    job = db.relationship('Job', backref='bookings')
    provider = db.relationship('User', foreign_keys=[provider_id])
    worker = db.relationship('User', foreign_keys=[worker_id])


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    message = db.Column(db.String(255), nullable=False)
    job_id = db.Column(db.Integer, nullable=True)
    action_type = db.Column(db.String(50))  # 'booking_request', 'accept', 'reject'
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    recipient = db.relationship('User', foreign_keys=[recipient_id])
    sender = db.relationship('User', foreign_keys=[sender_id])

class ShowcaseImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)



@app.route('/upload_showcase', methods=['POST'])
@login_required
def upload_showcase():
    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join('static/uploads', filename)
        file.save(filepath)

        # Update user profile (assuming photo vs video check by extension)
        profile = WorkerProfile.query.filter_by(user_id=current_user.id).first()
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            profile.photo = filename
        elif filename.lower().endswith('.mp4'):
            profile.video = filename
        db.session.commit()

    return redirect(url_for('seek_job'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ Helper: Reverse Geocoding ------------------
def reverse_geocode(lat, lon):
    try:
        url = f'https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}'
        headers = {'User-Agent': 'JobConnectApp'}
        response = requests.get(url, headers=headers)
        data = response.json()
        return data['address'].get('city') or data['address'].get('town') or data['address'].get('village') or 'Unknown'
    except:
        return 'Unknown'

# ------------------ Routes ------------------

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('welcome'))
    return '''
        <h2>Welcome to Job Connect</h2>
        <a href='/login'>Login</a> | <a href='/sign_up'>Sign Up</a>
    '''


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()

        if user:
            login_user(user)
            return redirect(url_for('welcome'))
        else:
            flash("No account found with this email. Please sign up.")
            return redirect(url_for('sign_up'))

    # Return a plain HTML form for login
    return '''
        <h2>Login</h2>
        <form method='POST'>
            Email: <input type='email' name='email' required><br>
            <input type='submit' value='Login'>
        </form>
        <p>Don't have an account? <a href='/sign_up'>Sign Up</a></p>
    '''

@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']

        if User.query.filter_by(email=email).first():
            flash("Account already exists.")
            return redirect(url_for('login'))

        user = User(email=email, name=name, location="Fetching...",  state=None, zipcode=None, )
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('welcome'))

    return '''
        <form method="POST">
            Email: <input type="email" name="email" required><br>
            Name: <input type="text" name="name" required><br>
            <input type="submit" value="Sign Up">
        </form>
    '''

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_location_details', methods=['POST'])
def get_location_details():
    data = request.get_json()
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    url = f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json"
    headers = {'User-Agent': 'JobConnectApp/1.0'}
    response = requests.get(url, headers=headers).json()

    print(response)  # Debugging the response from OpenStreetMap

    address = response.get('address', {})
    state = address.get('state', 'Unknown')
    zipcode = address.get('postcode', 'Unknown')

    return jsonify({
        'state': state,
        'zipcode': zipcode
    })

@app.route('/update_location', methods=['POST'])
@login_required
def update_location():
    data = request.get_json()
    current_user.state = data.get('state', 'Unknown')
    current_user.zipcode = data.get('zipcode', 'Unknown')
    current_user.latitude = data.get('latitude')
    current_user.longitude = data.get('longitude')
    current_user.location_last_updated = datetime.utcnow()
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/welcome')
@login_required
def welcome():

    unread_count = Notification.query.filter_by(recipient_id=current_user.id, is_read=False).count()
    return render_template('welcome.html', unread_count=unread_count)

@app.route('/provide_job', methods=['GET', 'POST'])
@login_required
def provide_job():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        job_type = request.form['job_type'].strip().lower()

        user_lat = current_user.latitude
        user_lon = current_user.longitude

        if user_lat is None or user_lon is None:
            return "<p>Error: Please enable location so we can find nearby workers.</p>"

        job = Job(title=title, description=description, user_id=current_user.id)
        db.session.add(job)
        db.session.commit()

        job_keywords = set(job_type.split())
        matched_list = ""
        skills = Skill.query.all()

        for skill in skills:
            skill_words = set(skill.name.strip().lower().split())
            if job_keywords & skill_words:
                worker_user = User.query.get(skill.user_id)
                if not worker_user or not worker_user.latitude or not worker_user.longitude:
                    continue

                distance_km = geodesic((user_lat, user_lon), (worker_user.latitude, worker_user.longitude)).km
                if distance_km <= 15:
                    matched_list += f'''
                    <div class="col-12 col-md-6 col-lg-4">
                        <div class="card shadow-sm mb-4">
                            <div class="card-body">
                                <h5 class="card-title">{worker_user.name}</h5>
                                <p class="card-text">
                                    <b>Skill:</b> {skill.name.title()}<br>
                                    <b>Rate:</b> ₹{skill.rate}<br>
                                    <b>Distance:</b> {round(distance_km, 2)} km
                                </p>
                                <a href="/worker/{worker_user.id}?job_id={job.id}" class="btn btn-primary">View Profile</a>
                            </div>
                        </div>
                    </div>
                    '''

        if not matched_list:
            matched_list = "<p>No matching workers found within 15 km radius.</p>"

        return f'''
        <!doctype html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Matching Workers</title>
          <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
          <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f8f9fa;
                padding: 20px;
            }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="mb-4">
                <p>You searched for: <b>{job_type}</b></p>
                <h4 class="mt-4">Matching Workers near your location:</h4>
            </div>
            <div class="row">
                {matched_list}
            </div>
            <a href="/welcome" class="btn btn-secondary mt-4">⬅ Back to Welcome</a>
          </div>
        </body>
        </html>
        '''

    # GET method
    skills = Skill.query.all()
    skill_names = [skill.name.strip().lower() for skill in skills]

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <title>Provide Job</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    padding: 20px;
                    margin: 0;
                }
                .form-container {
                    max-width: 600px;
                    margin: auto;
                }
                input[type="text"],
                textarea {
                    width: 100%;
                    padding: 10px;
                    margin-top: 5px;
                    margin-bottom: 20px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    box-sizing: border-box;
                }
                input[type="submit"] {
                    background-color: #28a745;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                }
                input[type="submit"]:hover {
                    background-color: #218838;
                }
                @media (max-width: 600px) {
                    h2, label, input, textarea {
                        font-size: 16px;
                    }
                }
            </style>
        </head>
        <body>
            <div class="form-container">
                <h2>Provide Job</h2>
                <form method='POST'>
                    <label>Job Title:</label>
                    <input type='text' name='title' required>

                    <label>Job Description:</label>
                    <textarea name='description' required></textarea>

                    <label>Type of Job Needed (e.g., plumber, electrician):</label>
                    <input type='text' name='job_type' id='job_type' list='job-type-list' required>

                    <datalist id='job-type-list'>
                        {% for skill in skill_names %}
                            <option value="{{ skill }}">
                        {% endfor %}
                    </datalist>

                    <input type='submit' value='Post Job & Find Worker'>
                </form>
            </div>
        </body>
        </html>
    ''', skill_names=skill_names)


@app.route('/worker/<int:worker_id>', methods=['GET', 'POST'])
@login_required
def view_worker(worker_id):
    user = User.query.get_or_404(worker_id)
    worker_profile = user.worker_profile
    skills = Skill.query.filter_by(user_id=user.id).all()
    showcase_images = ShowcaseImage.query.filter_by(user_id=user.id).order_by(ShowcaseImage.uploaded_at.desc()).all()
    job_id = request.args.get('job_id')
    profile = WorkerProfile.query.filter_by(user_id=user.id).first()

    message = ""
    book_button = ""
    rating_form = ""

    # Ratings
    ratings = Rating.query.filter_by(worker_id=user.id).order_by(Rating.timestamp.desc()).all()
    avg_rating = round(sum(r.stars for r in ratings) / len(ratings), 1) if ratings else "No ratings yet"

    # Submit new rating
    if request.method == 'POST' and current_user.id != user.id:
        stars = float(request.form.get("stars", 0))
        comment = request.form.get("comment", "")
        new_rating = Rating(worker_id=user.id, job_giver_id=current_user.id, stars=stars, comment=comment)
        db.session.add(new_rating)
        db.session.commit()
        flash("Rating submitted successfully!", "success")
        return redirect(url_for("view_worker", worker_id=user.id, job_id=job_id))

    # Booking logic
    if current_user.id != user.id and job_id:
        book_button = f"""
        <form method="POST" action="/book_worker/{user.id}">
            <input type="hidden" name="job_id" value="{job_id}">
            <button type="submit" class="btn btn-primary mt-2">Book Worker</button>
        </form>
        """
    elif current_user.id == user.id:
        message = "<div class='alert alert-info'>You cannot book your own profile.</div>"

    # Rating form (only for others, not the worker viewing their own profile)
    if current_user.id != user.id:
        rating_form = f"""
        <h3>Leave a Rating</h3>
        <style>
            .star-rating {{
                direction: rtl;
                display: inline-block;
                font-size: 30px;
                unicode-bidi: bidi-override;
            }}
            .star-rating input[type="radio"] {{
                display: none;
            }}
            .star-rating label {{
                color: #ccc;
                float: right;
                padding: 0 5px;
                cursor: pointer;
            }}
            .star-rating label:before {{
                content: "\\2605";
            }}
            .star-rating label.half:before {{
                content: "\\2605";
                position: absolute;
                margin-left: -15px;
                width: 15px;
                overflow: hidden;
            }}
            .star-rating input:checked ~ label,
            .star-rating label:hover,
            .star-rating label:hover ~ label {{
                color: gold;
            }}
        </style>

        <form method="POST">
            <div class="star-rating">
                <input type="radio" id="star5half" name="stars" value="5" /><label for="star5half" class="half" title="5 stars"></label>
                <input type="radio" id="star5" name="stars" value="4.5" /><label for="star5" title="4.5 stars"></label>
                <input type="radio" id="star4half" name="stars" value="4" /><label for="star4half" class="half" title="4 stars"></label>
                <input type="radio" id="star4" name="stars" value="3.5" /><label for="star4" title="3.5 stars"></label>
                <input type="radio" id="star3half" name="stars" value="3" /><label for="star3half" class="half" title="3 stars"></label>
                <input type="radio" id="star3" name="stars" value="2.5" /><label for="star3" title="2.5 stars"></label>
                <input type="radio" id="star2half" name="stars" value="2" /><label for="star2half" class="half" title="2 stars"></label>
                <input type="radio" id="star2" name="stars" value="1.5" /><label for="star2" title="1.5 stars"></label>
                <input type="radio" id="star1half" name="stars" value="1" /><label for="star1half" class="half" title="1 stars"></label>
                <input type="radio" id="star1" name="stars" value=".5" /><label for="star1" title=".5 star"></label>
            </div>
            <br><br>
            <label for="comment">Comment:</label><br>
            <textarea name="comment" rows="4" cols="50" placeholder="Write your feedback..." required></textarea><br><br>
            <input type="submit" value="Submit Rating">
        </form>
        """

    rating_display = f"<h3>Average Rating: {avg_rating}</h3><ul>"
    for r in ratings:
        rater_name = r.rater.name if r.rater else "Unknown"
        rating_display += f"<li><b>{r.stars} ★</b> by <i>{rater_name}</i> - {r.comment}</li>"
    rating_display += "</ul>"
    # Skills
    skill_list = "<ul class='list-group'>" + "".join(
        [f"<li class='list-group-item'>{s.name.title()} - ₹{s.rate}/hr</li>" for s in skills]) + "</ul>"

    # Media showcase (carousel)
    media_items = ""
    media_indicators = ""
    index = 0

    if worker_profile:
        # Handle photo if exists
        if worker_profile.photo:
            media_indicators += f'<button type="button" data-bs-target="#mediaModalCarousel" data-bs-slide-to="{index}" class="active" aria-current="true" aria-label="Photo"></button>'
            media_items += f"""
            <div class="carousel-item active">
                <img src="/static/uploads/{worker_profile.photo}" class="d-block w-100 rounded" alt="Worker Photo">
            </div>
            """
            index += 1
        # Handle video if exists
        if worker_profile.video:
            media_indicators += f'<button type="button" data-bs-target="#mediaModalCarousel" data-bs-slide-to="{index}" aria-label="Video"></button>'
            media_items += f"""
            <div class="carousel-item">
                <video class="d-block w-100 rounded" controls>
                    <source src="/static/uploads/{worker_profile.video}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </div>
            """
            index += 1
    # Profile photo and gender
    photo_url = f"/static/uploads/{profile.photo}" if profile.photo else "/static/default_profile.jpg"
    gender = profile.gender or "Not specified"

    # Showcase
    showcase_items = ShowcaseImage.query.filter_by(user_id=user.id).all()
    video_item = profile.video

    photo_modals = ""
    if showcase_items or video_item:
        thumbnail = showcase_items[0].image_url if showcase_items else 'default.jpg'
        thumbnail_html = f"""
        <div>
            <img src="/static/uploads/{thumbnail}" width="150" class="img-thumbnail" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#carouselModal">
        </div>
        """

        # Carousel items
        carousel_items_html = ""
        slide_index = 0
        for img in showcase_items:
            active = "active" if slide_index == 0 else ""
            carousel_items_html += f"""
            <div class="carousel-item {active}">
                <img src="/static/uploads/{img.image_url}" class="d-block w-100 rounded" alt="Image {slide_index + 1}">
            </div>
            """
            slide_index += 1

        if video_item:
            active = "active" if slide_index == 0 else ""
            carousel_items_html += f"""
            <div class="carousel-item {active}">
                <video class="d-block w-100 rounded" controls>
                    <source src="/static/uploads/{video_item}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </div>
            """

        # Modal with carousel
        photo_modals = f"""
        {thumbnail_html}

        <!-- Modal with Carousel -->
        <div class="modal fade" id="carouselModal" tabindex="-1" aria-labelledby="carouselModalLabel" aria-hidden="true">
          <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content">
              <div class="modal-body">
                <div id="showcaseCarousel" class="carousel slide" data-bs-ride="carousel">
                  <div class="carousel-inner">
                    {carousel_items_html}
                  </div>
                  <button class="carousel-control-prev" type="button" data-bs-target="#showcaseCarousel" data-bs-slide="prev">
                    <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                    <span class="visually-hidden">Previous</span>
                  </button>
                  <button class="carousel-control-next" type="button" data-bs-target="#showcaseCarousel" data-bs-slide="next">
                    <span class="carousel-control-next-icon" aria-hidden="true"></span>
                    <span class="visually-hidden">Next</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        """
    else:
        photo_modals = "<p>No showcase items uploaded yet.</p>"

    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <title>{user.name}'s Profile</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <style>
            body {{
                background-color: #f8f9fa;
            }}
            .profile-photo {{
                max-width: 150px;
                height: auto;
            }}
            .carousel-item img, .carousel-item video {{
                max-height: 500px;
                object-fit: contain;
            }}
        </style>
    </head>
    <body>
        <div class="container-fluid mt-4">
            <div class="row justify-content-center">
                <div class="col-12 col-md-10 col-lg-8">
                    <div class="text-center mb-3">
                        <img src="{photo_url}" class="rounded-circle img-fluid profile-photo" alt="Profile Photo">
                    </div>
                    <div class="card p-3 shadow-sm">
                        <h2 class="text-center mb-3">{user.name}'s Profile</h2>
                        <p><strong>Gender:</strong> {gender}</p>
                        <p><strong>Age:</strong> {worker_profile.age if worker_profile else ''}</p>
                        <p><strong>Location:</strong> {profile.state}, {profile.zipcode}</p>
                        <p><strong>About Me:</strong> {worker_profile.about if worker_profile else user.about}</p>
                        <p><strong>Qualification:</strong> {worker_profile.qualification if worker_profile else ''}</p>
                        <p><strong>Experience:</strong> {worker_profile.experience if worker_profile else ''}</p>

                        <hr>
                        <h4>Skills</h4>
                        {skill_list}

                        <hr>
                        <h4>Showcase</h4>
                        {photo_modals}

                        <hr>
                        {message}
                        {book_button}

                        <hr>
                        {rating_form}

                        <hr>
                        {rating_display}

                        <div class="text-center mt-4">
                            <a href='/welcome' class='btn btn-secondary'>Back to Welcome</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


@app.route('/notifications')
@login_required
def notifications():
    notes = Notification.query.filter_by(recipient_id=current_user.id).order_by(Notification.timestamp.desc()).all()

    html = "<h2>Your Notifications</h2><ul>"
    for n in notes:
        if not n.is_read:
            n.is_read = True  # Mark as read
        html += f"<li>{n.message}<br>"
        if n.action_type == 'booking_request':
            html += f'''
                <form action="/respond_notification/{n.id}" method="post">
                    <input type="submit" name="response" value="Accept">
                    <input type="submit" name="response" value="Reject">
                </form>
            '''
        html += "</li><br>"
    html += "</ul><a href='/welcome'>Back to Dashboard</a>"
    db.session.commit()
    return html


@app.route('/book_worker/<int:worker_id>', methods=['POST'])
@login_required
def book_worker(worker_id):
    # assume a job_id or similar context exists
    job_id = request.form.get('job_id')

    worker = User.query.get_or_404(worker_id)

    notification = Notification(
        recipient_id=worker.id,
        sender_id=current_user.id,
        message=f"{current_user.name} has requested to book you for a job.",
        job_id=job_id,
        action_type='booking_request'
    )
    db.session.add(notification)
    db.session.commit()

    return f'''
        <p>Booking request sent to {worker.name}!</p>
        <a href="/welcome">Back to Dashboard</a>
    '''


@app.route('/respond_notification/<int:notification_id>', methods=['POST'])
@login_required
def respond_notification(notification_id):
    notif = Notification.query.get_or_404(notification_id)

    if notif.recipient_id != current_user.id:
        return "Unauthorized", 403

    response = request.form.get('response')  # 'Accept' or 'Reject'
    response = response.capitalize()

    # ✅ Update the original notification for the job seeker
    if notif.sender:
        notif.message = f"You have {response.lower()}ed {notif.sender.name}'s job request."
    else:
        notif.message = f"You have {response.lower()}ed a job request."

    notif.action_type = response.lower()
    notif.is_read = True

    # ✅ NEW: Notify the original sender (job giver) about the response
    if notif.sender_id:
        response_notif = Notification(
            recipient_id=notif.sender_id,
            sender_id=current_user.id,
            message=f"{current_user.name} has {response.lower()}ed your job request.",
            job_id=notif.job_id,
            action_type=response.lower()
        )
        db.session.add(response_notif)

    db.session.commit()

    return f'''
        <p>You have {response.lower()}ed the request.</p>
        <a href="/notifications">Back to Notifications</a>
    '''

@app.route('/seek_job')
@login_required
def seek_job():
    user = current_user
    profile = WorkerProfile.query.filter_by(user_id=user.id).first()
    if not profile:
        flash("Please create a worker profile first.")
        return redirect(url_for('create_worker_profile'))

    # Ratings
    ratings = Rating.query.filter_by(worker_id=user.id).order_by(Rating.timestamp.desc()).all()
    avg_rating = round(sum(r.stars for r in ratings) / len(ratings), 1) if ratings else "No ratings yet"

    rating_display = f"<h3>Average Rating: {avg_rating}</h3><ul>"
    for r in ratings:
        rater_name = r.rater.name if r.rater else "Unknown"
        rating_display += f"<li><b>{r.stars} ★</b> by <i>{rater_name}</i> - {r.comment}</li>"
    rating_display += "</ul>"

    # Skills
    skill_list = Skill.query.filter_by(user_id=user.id).all()
    skills_str = ", ".join([s.name for s in skill_list]) or "None"

    # Showcase
    showcase_items = ShowcaseImage.query.filter_by(user_id=user.id).all()
    video_item = profile.video

    photo_modals = ""
    if showcase_items or video_item:
        thumbnail = showcase_items[0].image_url if showcase_items else 'default.jpg'
        thumbnail_html = f"""
        <div>
            <img src="/static/uploads/{thumbnail}" width="150" class="img-thumbnail" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#carouselModal">
        </div>
        """

        # Carousel items
        carousel_items_html = ""
        slide_index = 0
        for img in showcase_items:
            active = "active" if slide_index == 0 else ""
            carousel_items_html += f"""
            <div class="carousel-item {active}">
                <img src="/static/uploads/{img.image_url}" class="d-block w-100 rounded" alt="Image {slide_index + 1}">
            </div>
            """
            slide_index += 1

        if video_item:
            active = "active" if slide_index == 0 else ""
            carousel_items_html += f"""
            <div class="carousel-item {active}">
                <video class="d-block w-100 rounded" controls>
                    <source src="/static/uploads/{video_item}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
            </div>
            """

        # Modal with carousel
        photo_modals = f"""
        {thumbnail_html}

        <!-- Modal with Carousel -->
        <div class="modal fade" id="carouselModal" tabindex="-1" aria-labelledby="carouselModalLabel" aria-hidden="true">
          <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content">
              <div class="modal-body">
                <div id="showcaseCarousel" class="carousel slide" data-bs-ride="carousel">
                  <div class="carousel-inner">
                    {carousel_items_html}
                  </div>
                  <button class="carousel-control-prev" type="button" data-bs-target="#showcaseCarousel" data-bs-slide="prev">
                    <span class="carousel-control-prev-icon" aria-hidden="true"></span>
                    <span class="visually-hidden">Previous</span>
                  </button>
                  <button class="carousel-control-next" type="button" data-bs-target="#showcaseCarousel" data-bs-slide="next">
                    <span class="carousel-control-next-icon" aria-hidden="true"></span>
                    <span class="visually-hidden">Next</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        """
    else:
        photo_modals = "<p>No showcase items uploaded yet.</p>"

    # Profile photo and gender
    photo_url = f"/static/uploads/{profile.photo}" if profile.photo else "/static/default_profile.jpg"
    gender = profile.gender or "Not specified"

    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Worker Profile</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <style>
            .profile-photo {{
                width: 120px;
                height: 120px;
                object-fit: cover;
                border-radius: 50%;
            }}
            @media (max-width: 768px) {{
                .profile-photo {{
                    width: 90px;
                    height: 90px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container mt-4">
            <div class="d-flex justify-content-between align-items-start flex-wrap mb-4">
                <div class="flex-grow-1">
                    <h2>Your Worker Profile</h2>
                    <p><b>Worker ID:</b> {profile.worker_code}</p>
                    <p><b>Name:</b> {user.name}</p>
                    <p><b>Gender:</b> {gender}</p>
                    <p><b>Age:</b> {profile.age}</p>
                    <p><b>Contact:</b> {profile.phone}</p>
                    <p><b>State:</b> {profile.state}</p>
                    <p><b>Zipcode:</b> {profile.zipcode}</p>
                    <p><b>Qualification:</b> {profile.qualification}</p>
                    <p><b>Experience:</b> {profile.experience}</p>
                    <p><b>About Me:</b> {profile.about}</p>
                    <p><b>Skills:</b> {skills_str}</p>
                    <p><b>Rating:</b> {avg_rating}</p>
                </div>
                <div class="text-end ms-4">
                    <img src="{photo_url}" alt="Profile Photo" class="profile-photo shadow">
                </div>
            </div>

            <div class="mb-4">
                {rating_display}
            </div>

            <h3>Showcase</h3>
            <div class="d-flex flex-wrap gap-3">
                {photo_modals}
            </div>

            <div class="mt-4">
                <a href="/edit_worker_profile" class="btn btn-success me-2">Edit Profile</a>
                <a href="/welcome" class="btn btn-secondary">Back to Welcome</a>
            </div>
        </div>
    </body>
    </html>
    '''


def generate_unique_worker_id():
    custom_id = WorkerProfile.query.count() + 1

    def is_valid(id_str):
        # Reject if 4 or more repeating digits
        for digit in set(id_str):
            if id_str.count(digit) >= 4:
                return False
        return True

    digits = 8
    max_attempts = 10000

    for _ in range(max_attempts):
        worker_id = random.randint(10**(digits-1), 10**digits - 1)
        worker_id_str = str(worker_id)

        if not is_valid(worker_id_str):
            continue

        if not WorkerProfile.query.filter_by(user_id=worker_id).first():
            return worker_id

    # fallback: increase to 9 digits
    digits += 1
    while True:
        worker_id = random.randint(10**(digits-1), 10**digits - 1)
        worker_id_str = str(worker_id)

        if is_valid(worker_id_str) and not WorkerProfile.query.filter_by(user_id=worker_id).first():
            return worker_id

@app.route('/create_worker_profile', methods=['GET', 'POST'])
@login_required
def create_worker_profile():
    profile = WorkerProfile.query.filter_by(user_id=current_user.id).first()
    if profile:
        flash("Profile already exists. You can edit it instead.")
        return redirect(url_for('edit_worker_profile'))

    if request.method == 'POST':
        # generate custom worker ID
        worker_code = generate_unique_worker_id()

        # all form fields...
        age = int(request.form['age'])
        gender = request.form['gender']
        qualification = request.form['qualification']
        experience = request.form['experience']
        about = request.form['about']
        state = request.form.get('state')
        zipcode = request.form.get('zipcode')
        phone = request.form.get('phone')
        full_location = f"  {state}, {zipcode}"

        photo_file = request.files.get('photo')
        photo_filename = None
        if photo_file and photo_file.filename != '':
            filename = secure_filename(photo_file.filename)
            photo_filename = f"{current_user.id}_{filename}"
            photo_path = os.path.join('static/uploads', photo_filename)
            photo_file.save(photo_path)

        new_profile = WorkerProfile(
            user_id=current_user.id,
            worker_code=worker_code,  # <-- save the generated code
            age=age,
            gender=gender,
            qualification=qualification,
            experience=experience,
            about=about,
            state=state,
            zipcode=zipcode,
            photo=photo_filename,
            phone=phone
        )
        db.session.add(new_profile)

        # save skills
        skills = request.form.getlist('skills')
        rates = request.form.getlist('rates')
        for skill_name, rate in zip(skills, rates):
            if skill_name.strip() == '' or rate.strip() == '':
                continue
            skill = Skill(
                name=skill_name.strip().lower(),
                rate=rate.strip(),
                location=full_location.strip(),
                user_id=current_user.id
            )
            db.session.add(skill)

        db.session.commit()
        flash("Profile created successfully.")
        return redirect(url_for('seek_job'))

    # render form...


    return '''
    <h2>Create Worker Profile</h2>
    <form method="POST" enctype="multipart/form-data">

        <!-- Profile Image Upload -->
        <div style="text-align:center; margin-bottom:20px;">
            <label for="photo" style="cursor:pointer;">
                <img id="preview" src="/static/uploads/default.jpg" 
                     style="width:150px; height:150px; border-radius:50%; object-fit:cover; border:3px solid #ccc;" 
                     alt="Profile Photo">
            </label>
            <input type="file" id="photo" name="photo" accept="image/*" style="display:none;" onchange="loadPreview(event)">
        </div>

        Age: <input type="number" name="age" required><br>
        Gender: 
        <select name="gender" required>
            <option value="Male">Male</option>
            <option value="Female">Female</option>
        </select><br>
        Phone Number: <input type="text" name="phone" required><br>
        Qualification: <input type="text" name="qualification" required><br>
        Experience: <input type="text" name="experience" required><br>
        About Me: <textarea name="about" required></textarea><br>


        <h3>Skills</h3>
        <div id="skills-section">
            <input type="text" name="skills" placeholder="Skill (e.g., plumber)" required>
            <input type="number" name="rates" placeholder="Rate per hour (₹)" required>
        </div>
        <button type="button" onclick="addSkill()">Add Another Skill</button><br><br>

        <input type="submit" value="Create Profile">
    </form>

    <script>
        function addSkill() {
            const container = document.getElementById('skills-section');
            const skillGroup = document.createElement('div');
            skillGroup.className = 'skill-group';
            skillGroup.innerHTML = `
                <input type="text" name="skills" placeholder="Skill (e.g., carpenter)" required>
                <input type="number" name="rates" placeholder="Rate per hour (₹)" required>
                <button type="button" onclick="removeSkill(this)">Remove</button><br>
            `;
            container.appendChild(skillGroup);
        }

        function removeSkill(button) {
            const skillGroup = button.parentNode;
            skillGroup.remove();
        }

        function loadPreview(event) {
            const preview = document.getElementById('preview');
            preview.src = URL.createObjectURL(event.target.files[0]);
            preview.onload = () => URL.revokeObjectURL(preview.src);
        }
    </script>
    '''

@app.route('/edit_worker_profile', methods=['GET', 'POST'])
@login_required
def edit_worker_profile():
    profile = WorkerProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("No profile found. Please create one.")
        return redirect(url_for('create_worker_profile'))

    showcase_images = ShowcaseImage.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        profile.age = request.form['age']
        profile.gender = request.form.get('gender')
        profile.phone = request.form.get('phone')
        profile.qualification = request.form['qualification']
        profile.experience = request.form['experience']
        profile.about = request.form['about']
        profile.locality = request.form.get('locality')
        profile.city = request.form.get('city')
        profile.state = request.form.get('state')
        profile.zipcode = request.form.get('zipcode')
        full_location = f"{profile.locality}, {profile.city}, {profile.state}, {profile.zipcode}"

        # Handle profile photo upload and delete old image
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and allowed_file(photo.filename, ALLOWED_IMAGE_EXTENSIONS):
                # Delete old photo if it exists
                if profile.photo:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], profile.photo)
                    if os.path.exists(old_path):
                        os.remove(old_path)

                # Save new photo
                filename = secure_filename(photo.filename)
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                photo.save(photo_path)
                profile.photo = filename

        # Handle profile video upload and delete old video
        if 'video' in request.files:
            video = request.files['video']
            if video and allowed_file(video.filename, ALLOWED_VIDEO_EXTENSIONS):
                # Delete old video if it exists
                if profile.video:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], profile.video)
                    if os.path.exists(old_path):
                        os.remove(old_path)

                # Save new video
                filename = secure_filename(video.filename)
                video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                video.save(video_path)
                profile.video = filename

        # Handle showcase image uploads
        if 'showcase_images' in request.files:
            showcase_images_list = request.files.getlist('showcase_images')
            for img in showcase_images_list:
                if img and allowed_file(img.filename, ALLOWED_IMAGE_EXTENSIONS):
                    filename = secure_filename(img.filename)
                    img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    img.save(img_path)
                    showcase_image = ShowcaseImage(user_id=current_user.id, image_url=filename)
                    db.session.add(showcase_image)

        # Update skills
        Skill.query.filter_by(user_id=current_user.id).delete()
        skills = request.form.getlist('skills')
        rates = request.form.getlist('rates')

        for skill_name, rate in zip(skills, rates):
            if skill_name.strip() and rate.strip():
                db.session.add(Skill(
                    name=skill_name.strip().lower(),
                    rate=rate.strip(),
                    location=full_location,
                    user_id=current_user.id
                ))

        db.session.commit()
        flash("Profile updated successfully.")
        return redirect(url_for('seek_job'))

    skills = Skill.query.filter_by(user_id=current_user.id).all()
    return render_template('edit_worker_profile.html', profile=profile, skills=skills, showcase_images=showcase_images)



@app.route('/delete_media/<media_type>/<media_id>', methods=['POST'])
@login_required
def delete_media(media_type, media_id):
    # Check if the media type is valid
    if media_type not in ['image', 'video']:
        flash("Invalid media type.", 'error')
        return redirect(url_for('edit_worker_profile'))

    if media_type == 'video':
        profile = WorkerProfile.query.get(media_id)
        if profile and profile.user_id == current_user.id:
            # Remove the video file from the filesystem
            try:
                video_path = os.path.join(app.config['UPLOAD_FOLDER'], profile.video)
                if os.path.exists(video_path):
                    os.remove(video_path)
                    profile.video = None  # Set the video field to None in the database
                    db.session.commit()
                    flash("Video deleted successfully.", 'success')
                else:
                    flash("Video file not found.", 'error')
            except FileNotFoundError:
                flash("Video file not found.", 'error')
        else:
            flash("Video not found or you do not have permission to delete it.", 'error')

    elif media_type == 'image':
        showcase_image = ShowcaseImage.query.get(media_id)
        if showcase_image and showcase_image.user_id == current_user.id:
            # Remove the image file from the filesystem
            try:
                img_path = os.path.join(app.config['UPLOAD_FOLDER'], showcase_image.image_url)
                if os.path.exists(img_path):
                    os.remove(img_path)
                    db.session.delete(showcase_image)
                    db.session.commit()
                    flash("Image deleted successfully.", 'success')
                else:
                    flash("Image file not found.", 'error')
            except FileNotFoundError:
                flash("Image file not found.", 'error')
        else:
            flash("Image not found or you do not have permission to delete it.", 'error')

    # Always redirect back to 'edit_worker_profile' after deleting media
    return redirect(url_for('edit_worker_profile'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# ------------------ Main ------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)

