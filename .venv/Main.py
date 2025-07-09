from flask import Flask, request, redirect, url_for, render_template_string, session, flash,render_template,jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from geopy.distance import geodesic
import os
import random
import secrets
from datetime import datetime,timedelta
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
    tokens = db.Column(db.Integer, default=5000)  # 🪙 Initial balance
    # Define the one-to-one relationship with WorkerProfile
    worker_profile = db.relationship('WorkerProfile', backref='user', uselist=False)


class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rate = db.Column(db.String(100), nullable=False)
    rate_type = db.Column(db.String(50))
    location = db.Column(db.String(100))
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
    token = db.Column(db.String(32), unique=True, nullable=False, default=lambda: secrets.token_hex(16))
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    provider_id = db.Column(db.Integer, db.ForeignKey('user.id'))  # Job giver
    worker_id = db.Column(db.Integer, db.ForeignKey('user.id'))    # Worker
    status = db.Column(db.String(20), default='pending')           # pending / accepted / declined
    rate = db.Column(db.Float)
    rate_type = db.Column(db.String(20))
    quantity = db.Column(db.Float)
    expires_at = db.Column(db.DateTime)
    job = db.relationship('Job', backref='bookings')
    provider = db.relationship('User', foreign_keys=[provider_id])
    worker = db.relationship('User', foreign_keys=[worker_id])



class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    message = db.Column(db.String(255), nullable=False)
    job_id = db.Column(db.Integer, nullable=True)
    action_type = db.Column(db.String(50))  # e.g., booking_request, accepted, rejected
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'))
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
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Job Connect</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
        <style>
            body {
                margin: 0;
                padding: 0;
                min-height: 100vh;
                background: linear-gradient(135deg, #6e8efb, #a777e3);
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: 'Segoe UI', sans-serif;
                animation: fadeIn 1s ease-in;
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .card {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                padding: 40px 30px;
                max-width: 420px;
                width: 100%;
                box-shadow: 0 8px 25px rgba(0,0,0,0.2);
                text-align: center;
            }

            .card h2 {
                font-size: 28px;
                font-weight: bold;
                margin-bottom: 20px;
            }

            .card h2 span {
                color: #6f42c1;
            }

            .btn-lg {
                padding: 12px 20px;
                font-size: 18px;
                border-radius: 10px;
                margin-top: 15px;
            }

            .btn i {
                margin-right: 8px;
            }

            .btn-outline-primary:hover {
                background-color: #6f42c1;
                color: #fff;
                border-color: #6f42c1;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Welcome to <span>Sahayi</span></h2>
            <p class="text-muted mb-4">Find jobs. Offer skills. Build your future.</p>
            <a href="/login" class="btn btn-primary btn-lg w-100">
                <i class="fas fa-sign-in-alt"></i> Login
            </a>
            <a href="/sign_up" class="btn btn-outline-primary btn-lg w-100">
                <i class="fas fa-user-plus"></i> Sign Up
            </a>
        </div>
    </body>
    </html>
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

    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Login - Job Connect</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
        <style>
            body {
                margin: 0;
                padding: 0;
                height: 100vh;
                background: linear-gradient(135deg, #6e8efb, #a777e3);
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: 'Segoe UI', sans-serif;
                animation: fadeIn 1s ease-in;
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .login-box {
                background: rgba(255, 255, 255, 0.95);
                padding: 40px 30px;
                border-radius: 20px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.2);
                width: 100%;
                max-width: 420px;
                text-align: center;
            }

            .login-box h2 {
                font-weight: 700;
                font-size: 26px;
                margin-bottom: 25px;
            }

            .form-label {
                font-weight: 500;
            }

            .form-control {
                padding-left: 40px;
                border-radius: 10px;
            }

            .input-group-text {
                background-color: #e9ecef;
                border-radius: 10px 0 0 10px;
                border: none;
            }

            .btn-primary {
                padding: 12px;
                font-size: 18px;
                border-radius: 10px;
                font-weight: 500;
            }

            .btn-primary:hover {
                background-color: #5936b4;
                border-color: #5936b4;
            }

            .text-muted a {
                color: #6f42c1;
                text-decoration: none;
            }

            .text-muted a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>Login to <span class="text-primary">Sahayi</span></h2>
            <form method="POST">
                <div class="mb-4 input-group">
                    <span class="input-group-text"><i class="fas fa-envelope"></i></span>
                    <input type="email" class="form-control" id="email" name="email" placeholder="Enter email" required>
                </div>
                <button type="submit" class="btn btn-primary w-100">Login</button>
            </form>
            <div class="text-muted mt-4">
                Don't have an account? <a href="/sign_up">Sign Up</a>
            </div>
        </div>
    </body>
    </html>
    '''



@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']

        if User.query.filter_by(email=email).first():
            flash("Account already exists.")
            return redirect(url_for('login'))

        user = User(email=email, name=name, location="Fetching...", state=None, zipcode=None)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for('welcome'))

    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Sign Up - Job Connect</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
        <style>
            body {
                margin: 0;
                padding: 0;
                height: 100vh;
                background: linear-gradient(135deg, #43cea2, #185a9d);
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: 'Segoe UI', sans-serif;
                animation: fadeIn 1s ease-in;
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .signup-box {
                background: rgba(255, 255, 255, 0.95);
                padding: 40px 30px;
                border-radius: 20px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.2);
                width: 100%;
                max-width: 420px;
                text-align: center;
            }

            .signup-box h2 {
                font-weight: 700;
                font-size: 26px;
                margin-bottom: 25px;
            }

            .form-label {
                font-weight: 500;
            }

            .form-control {
                padding-left: 40px;
                border-radius: 10px;
            }

            .input-group-text {
                background-color: #e9ecef;
                border-radius: 10px 0 0 10px;
                border: none;
            }

            .btn-success {
                padding: 12px;
                font-size: 18px;
                border-radius: 10px;
                font-weight: 500;
            }

            .btn-success:hover {
                background-color: #117a65;
                border-color: #117a65;
            }

            .text-muted a {
                color: #1e3799;
                text-decoration: none;
            }

            .text-muted a:hover {
                text-decoration: underline;
            }
        </style>
    </head>
    <body>
        <div class="signup-box">
            <h2>Sign Up for <span class="text-primary">Sahayi</span></h2>
            <form method="POST">
                <div class="mb-4 input-group">
                    <span class="input-group-text"><i class="fas fa-envelope"></i></span>
                    <input type="email" class="form-control" id="email" name="email" placeholder="Email address" required>
                </div>
                <div class="mb-4 input-group">
                    <span class="input-group-text"><i class="fas fa-user"></i></span>
                    <input type="text" class="form-control" id="name" name="name" placeholder="Full Name" required>
                </div>
                <button type="submit" class="btn btn-success w-100">Sign Up</button>
            </form>
            <div class="text-muted mt-4">
                Already have an account? <a href="/login">Login</a>
            </div>
        </div>
    </body>
    </html>
    '''



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


    return render_template("verify_otp.html")



@app.route('/provide_job', methods=['GET', 'POST'])
@login_required
def provide_job():
    if request.method == 'POST':
        job_type = request.form['job_type'].strip().lower()

        user_lat = current_user.latitude
        user_lon = current_user.longitude

        if user_lat is None or user_lon is None:
            return "<p>Error: Please enable location so we can find nearby workers.</p>"

        # Save job
        job = Job(
            title=job_type.title(),
            description=f"You are seeking help for: {job_type.title()}",
            user_id=current_user.id
        )
        db.session.add(job)
        db.session.commit()

        job_keywords = set(job_type.split())
        skills = Skill.query.all()
        matched_workers = {}  # Track first matched skill per worker

        for skill in skills:
            skill_words = set(skill.name.strip().lower().split())
            if job_keywords & skill_words:
                worker_user = User.query.get(skill.user_id)
                if not worker_user or not worker_user.latitude or not worker_user.longitude:
                    continue

                distance_km = geodesic(
                    (user_lat, user_lon),
                    (worker_user.latitude, worker_user.longitude)
                ).km

                if distance_km <= 15 and worker_user.id not in matched_workers:
                    matched_workers[worker_user.id] = {
                        "user": worker_user,
                        "skill_name": skill.name,
                        "rate": skill.rate,
                        "rate_type": skill.rate_type,
                        "distance": round(distance_km, 2)
                    }

        matched_list = ""
        for data in matched_workers.values():
            matched_list += f'''
            <div class="col-12 col-md-6 col-lg-4">
                <div class="card shadow-sm mb-4">
                    <div class="card-body">
                        <h5 class="card-title">{data["user"].name}</h5>
                        <p class="card-text">
                            <b>Skill:</b> {data["skill_name"].title()}<br>
                            <b>Rate:</b> ₹{data["rate"]} / {data["rate_type"]}<br>
                            <b>Distance:</b> {data["distance"]} km
                        </p>
                        <a href="/worker/{data["user"].id}?job_id={job.id}&skill={data["skill_name"]}" class="btn btn-primary">View Profile</a>
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
                <p>🔍 You searched for: <b>{job_type}</b></p>
                <h4 class="mt-4">Matching Workers near your location:</h4>
            </div>
            <div class="row">
                {matched_list}
            </div>
          </div>
        </body>
        </html>
        '''

    # GET method: render form
    skills = Skill.query.all()
    skill_names = [skill.name.strip().lower() for skill in skills]

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <title>Search for Sahayi</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    padding: 20px;
                    margin: 0;
                    background-color: #f2f2f2;
                }
                .form-container {
                    max-width: 600px;
                    margin: auto;
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                    box-shadow: 0 5px 15px rgba(0,0,0,0.1);
                }
                label {
                    font-weight: bold;
                    margin-bottom: 5px;
                    display: block;
                }
                input[type="text"] {
                    width: 100%;
                    padding: 10px;
                    margin-top: 5px;
                    margin-bottom: 20px;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    box-sizing: border-box;
                }
                input[type="submit"] {
                    background-color: #007bff;
                    color: white;
                    padding: 10px 20px;
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    width: 100%;
                }
                input[type="submit"]:hover {
                    background-color: #0056b3;
                }
                @media (max-width: 600px) {
                    input, label {
                        font-size: 16px;
                    }
                }
            </style>
        </head>
        <body>
            <div class="form-container">
                <h2 class="text-center">🔍 Search for Sahayi</h2>
                <form method='POST'>
                    <label for="job_type">What help do you need?</label>
                    <input type='text' name='job_type' id='job_type' list='job-type-list' placeholder="e.g., plumber, electrician" required>

                    <datalist id='job-type-list'>
                        {% for skill in skill_names %}
                            <option value="{{ skill }}">
                        {% endfor %}
                    </datalist>

                    <input type='submit' value='Search Workers Near You'>
                </form>
            </div>
        </body>
        </html>
    ''', skill_names=skill_names)


def generate_unique_token():
    while True:
        token = secrets.token_hex(16)
        if not Booking.query.filter_by(token=token).first():
            return token


@app.route('/confirm_booking/<int:worker_id>', methods=['GET', 'POST'])
@login_required
def confirm_booking(worker_id):
    from datetime import datetime
    worker = User.query.get_or_404(worker_id)
    skills = Skill.query.filter_by(user_id=worker.id).all()

    if request.method == 'POST':
        description = request.form['description']
        skill_name = request.form['skill']
        rate_type = request.form['rate_type']
        quantity = request.form.get('quantity')
        job_id = request.args.get("job_id")

        if not quantity or float(quantity) <= 0:
            return jsonify({"error": "Invalid quantity"}), 400

        skill = Skill.query.filter_by(user_id=worker.id, name=skill_name.lower().strip()).first()

        booking = Booking(
            token=generate_unique_token(),
            worker_id=worker.id,
            provider_id=current_user.id,
            job_id=job_id,
            status='Pending',
            rate=float(skill.rate),  # ✅ save rate
            rate_type=skill.rate_type,  # ✅ save rate_type
            quantity=float(quantity)  # ✅ save quantity
        )

        db.session.add(booking)
        db.session.flush()

        from geopy.distance import geodesic
        try:
            distance_km = round(
                geodesic((current_user.latitude, current_user.longitude),
                         (worker.latitude, worker.longitude)).km,
                2
            )
        except:
            distance_km = "Unknown"

        rate_type_clean = rate_type.lower()
        if "hour" in rate_type_clean:
            quantity_text = f"{quantity} hour(s)"
        elif "job" in rate_type_clean:
            quantity_text = f"{quantity} job(s)"
        elif "kilo" in rate_type_clean:
            quantity_text = f"{quantity} kilo(s)"
        elif "meter" in rate_type_clean:
            quantity_text = f"{quantity} kilometer(s)"
        else:
            quantity_text = f"{quantity} {rate_type}"

        message = f"""
        📢 <b>New booking request</b><br>
        🧰 <b>Skill:</b> {skill_name.title()}<br>
        🕒 <b>Requested:</b> {quantity_text}<br>
        📍 <b>Distance:</b> {distance_km} km<br>
        📝 <b>Job Description:</b> {description[:150]}
        """

        notification = Notification(
            recipient_id=worker.id,
            sender_id=current_user.id,
            message=message,
            action_type='booking_request',
            job_id=job_id,
            booking_id=booking.id
        )
        db.session.add(notification)
        db.session.commit()

        return jsonify({"redirect": "/welcome"})

    return render_template("confirm_booking.html", worker=worker, skills=skills)


@app.route('/worker/<int:worker_id>', methods=['GET', 'POST'])
@login_required
def view_worker(worker_id):
    user = User.query.get_or_404(worker_id)
    worker_profile = user.worker_profile
    searched_skill_name = request.args.get("skill")
    if searched_skill_name:
        skills = Skill.query.filter_by(user_id=user.id, name=searched_skill_name.strip().lower()).all()
    else:
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
            <textarea name="comment" class="form-control" rows="4" placeholder="Write your feedback..." required></textarea><br><br>
            <input type="submit" value="Submit Rating" class="btn btn-success">
        </form>
        """

    rating_display = f"<h3>Average Rating: {avg_rating}</h3><ul>"
    for r in ratings:
        rater_name = r.rater.name if r.rater else "Unknown"
        rating_display += f"<li><b>{r.stars} ★</b> by <i>{rater_name}</i> - {r.comment}</li>"
    rating_display += "</ul>"
    # Skills
    skill_list = "<ul class='list-group'>" + "".join(
        [f"<li class='list-group-item'>{s.name.title()} - ₹{s.rate} / {s.rate_type}</li>" for s in skills]) + "</ul>"

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
                 width: 150px;
                height: 150px;
                border-radius: 50%;
                object-fit: cover;
                object-position: center;
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

    html_notifications = ""
    for n in notes:
        if not n.is_read:
            n.is_read = True  # Mark as read

        html_notifications += f'''
            <div class="card mb-3">
                <div class="card-body">
                    <p class="card-text">{n.message}</p>
        '''

        if n.action_type == 'booking_request':
            html_notifications += f'''
                <div class="d-flex gap-2 mt-2">
                    <button onclick="respondNotification({n.id}, 'Accept')" class="btn btn-success btn-sm">Accept</button>
                    <button onclick="respondNotification({n.id}, 'Reject')" class="btn btn-danger btn-sm">Reject</button>
                </div>
            '''
        elif n.action_type == 'payment_required':
            booking = Booking.query.get(n.booking_id)
            if booking:
                html_notifications += f'''
                    <form action="/pay_token/{booking.token}" method="get" class="d-flex gap-2 mt-2">
                        <button type="submit" class="btn btn-warning btn-sm">💳 Pay Token Now</button>
                    </form>
                '''

        html_notifications += "</div></div>"  # close card-body and card

    db.session.commit()

    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Notifications - JobConnect</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <style>
            body {{
                background-color: #f8f9fa;
                padding: 20px;
            }}
            .card {{
                border-radius: 8px;
                box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
            }}
            .card-text {{
                font-size: 16px;
                line-height: 1.5;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2 class="mb-4 text-center">🔔 Your Notifications</h2>
            {html_notifications if html_notifications else "<p>No notifications yet.</p>"}
        </div>

        <script>
            function respondNotification(noteId, response) {{
                fetch(`/respond_notification/${{noteId}}`, {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/json"
                    }},
                    body: JSON.stringify({{ response: response }})
                }})
                .then(res => res.json())
                .then(data => {{
                    if (data.redirect) {{
                        // Accept: redirect to waiting page
                        window.location.href = data.redirect;
                    }} else if (data.status === 'rejected') {{
                        // Reject: just reload the page
                        location.reload();
                    }} else if (data.error) {{
                        alert("Error: " + data.error);
                    }}
                }})
                .catch(err => {{
                    console.error("Request failed:", err);
                    alert("Something went wrong!");
                }});
            }}
        </script>
    </body>
    </html>
    '''



@app.route('/check_pending_payment')
@login_required
def check_pending_payment():
    from datetime import datetime
    booking = Booking.query.filter_by(
        provider_id=current_user.id,
        status='Accepted'
    ).filter(Booking.expires_at > datetime.utcnow()).first()

    if booking:
        return jsonify({"redirect_url": url_for('pay_token', token=booking.token)})
    return jsonify({"redirect_url": None})






@app.route('/book_worker/<int:worker_id>', methods=['POST'])
@login_required
def book_worker(worker_id):
    job_id = request.form.get('job_id')
    return redirect(url_for('confirm_booking', worker_id=worker_id, job_id=job_id))


@app.route('/booking_timeout/<string:token>')
@login_required
def booking_timeout(token):
    booking = Booking.query.filter_by(token=token).first_or_404()

    # Only provider should access
    if current_user.id != booking.provider_id:
        abort(403)

    if booking.status != 'Token Paid':
        booking.status = 'Cancelled'
        db.session.commit()
        flash("⏱️ Token payment time expired. Booking cancelled.")

    return redirect(url_for('welcome'))


@app.route('/waiting_for_payment/<string:token>')
@login_required
def waiting_for_payment(token):
    booking = Booking.query.filter_by(token=token).first_or_404()

    if current_user.id != booking.worker_id:
        abort(403)

    from datetime import datetime
    remaining = max(0, int((booking.expires_at - datetime.utcnow()).total_seconds()))
    return render_template("waiting_payment.html", booking=booking, remaining=remaining)



@app.route('/respond_notification/<int:notification_id>', methods=['POST'])
@login_required
def respond_notification(notification_id):
    notif = Notification.query.get_or_404(notification_id)
    if notif.recipient_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    response = request.form.get('response', '').capitalize() if not request.is_json else request.json.get('response', '').capitalize()
    if response not in ['Accept', 'Reject']:
        return jsonify({'error': 'Invalid response'}), 400

    booking = Booking.query.get(notif.booking_id)
    if not booking or booking.status != 'Pending':
        return jsonify({'error': 'Invalid or already handled'}), 404

    if response == 'Accept':
        booking.status = 'Accepted'
        booking.expires_at = datetime.utcnow() + timedelta(minutes=10)
        notif.message = f"You accepted {notif.sender.name}'s job request." if notif.sender else "You accepted a job request."
        notif.action_type = 'accepted'
        notif.is_read = True

        if notif.sender_id:
            notify_back = Notification(
                recipient_id=notif.sender_id,
                sender_id=current_user.id,
                job_id=notif.job_id,
                booking_id=booking.id,
                message=f"{current_user.name} has accepted your job request. Please pay the token within 10 minutes.",
                action_type='payment_required'
            )
            db.session.add(notify_back)

        db.session.commit()
        return jsonify({'redirect': url_for('waiting_for_payment', token=booking.token)})

    elif response == 'Reject':
        booking.status = 'Rejected'
        notif.message = f"You rejected {notif.sender.name}'s job request." if notif.sender else "You rejected a job request."
        notif.action_type = 'rejected'
        notif.is_read = True

        if notif.sender_id:
            notify_back = Notification(
                recipient_id=notif.sender_id,
                sender_id=current_user.id,
                job_id=notif.job_id,
                booking_id=booking.id,
                message=f"{current_user.name} has rejected your job request.",
                action_type='rejected'
            )
            db.session.add(notify_back)

        db.session.commit()
        return jsonify({'status': 'rejected'})  # ✅ No redirect

    return jsonify({'error': 'Unhandled case'}), 500



@app.route('/pay_token/<string:token>', methods=['GET', 'POST'])
@login_required
def pay_token(token):
    booking = Booking.query.filter_by(token=token).first_or_404()

    if current_user.id != booking.provider_id:
        return "Unauthorized", 403

    total_amount = round(booking.rate * booking.quantity, 2)

    if request.method == 'POST':
        booking.status = 'Token Paid'
        db.session.commit()
        flash(f"Paid ₹{total_amount} successfully. Token on hold.")
        return redirect(url_for('welcome'))

    from datetime import datetime
    remaining = max(0, int((booking.expires_at - datetime.utcnow()).total_seconds()))
    return render_template("pay_token.html", booking=booking, time_left=remaining, total=total_amount)




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

    photo_url = f"/static/uploads/{profile.photo}" if profile.photo else "/static/default_profile.jpg"
    gender = profile.gender or "Not specified"

    return f'''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>My Worker Profile - JobConnect</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        
        

        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css" rel="stylesheet">

        <style>
            body {{
                font-family: 'Poppins', sans-serif;
                background: linear-gradient(to right, #f0f4f8, #ffffff);
                color: #333;
            }}
            .profile-card {{
                background: #fff;
                border-radius: 12px;
                padding: 30px;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            }}
            .profile-photo {{
                width: 130px;
                height: 130px;
                object-fit: cover;
                border-radius: 50%;
                border: 3px solid #007bff;
            }}
            .info-label {{
                font-weight: 600;
                color: #555;
            }}
            .rating-stars {{
                font-size: 1.2rem;
                color: #f39c12;
            }}
            .showcase-preview img {{
                cursor: pointer;
                width: 150px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            ul {{
                padding-left: 20px;
            }}
            @media (max-width: 768px) {{
                .profile-photo {{
                    width: 100px;
                    height: 100px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container my-5">
            <div class="profile-card">
                <div class="d-flex flex-row flex-wrap align-items-start justify-content-between">
                    <div>
                        <h2 class="mb-2">👤 {user.name}</h2>
                        <p><span class="info-label">Worker ID:</span> {profile.worker_code}</p>
                        <p><span class="info-label">Gender:</span> {gender}</p>
                        <p><span class="info-label">Age:</span> {profile.age}</p>
                        <p><span class="info-label">Phone:</span> {profile.phone}</p>
                        <p><span class="info-label">Qualification:</span> {profile.qualification}</p>
                        <p><span class="info-label">Experience:</span> {profile.experience}</p>
                        <p><span class="info-label">Skills:</span> {skills_str}</p>
                    </div>
                    <div class="ms-auto text-end">
                        <img src="{photo_url}" alt="Profile Photo" class="profile-photo shadow-sm">
                    </div>
                </div>
                <hr>

                <div class="mt-3">
                    <h5>About Me</h5>
                    <p>{profile.about}</p>
                </div>

                <div class="mt-4">
                    <h5>⭐ Ratings</h5>
                    <p class="rating-stars"><b>Average:</b> {avg_rating if isinstance(avg_rating, str) else f"{avg_rating} ★"}</p>
                    {rating_display}
                </div>

                <div class="mt-4">
                    <h5>🎥 Showcase</h5>
                    {photo_modals}
                </div>

                <div class="mt-4 text-end">
                    <a href="/edit_worker_profile"
                       class="btn btn-outline-primary"
                       onclick="event.preventDefault(); window.location.replace('/edit_worker_profile');">
                       ✏️ Edit Profile
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''

def generate_unique_worker_id():
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

        if not WorkerProfile.query.filter_by(worker_code=worker_id_str).first():
            return worker_id_str  # Return as string to match DB type

    # Fallback
    digits += 1
    while True:
        worker_id = random.randint(10**(digits-1), 10**digits - 1)
        worker_id_str = str(worker_id)

        if is_valid(worker_id_str) and not WorkerProfile.query.filter_by(worker_code=worker_id_str).first():
            return worker_id_str


@app.route('/create_worker_profile', methods=['GET', 'POST'])
@login_required
def create_worker_profile():
    profile = WorkerProfile.query.filter_by(user_id=current_user.id).first()

    # ✅ FIX: Redirect with Flask if profile already exists
    if profile:
        return redirect('/seek_job')

    if request.method == 'POST':
        worker_code = generate_unique_worker_id()

        age = int(request.form['age'])
        gender = request.form['gender']
        qualification = request.form['qualification']
        experience = request.form['experience']
        about = request.form['about']
        state = request.form.get('state')
        zipcode = request.form.get('zipcode')
        phone = request.form.get('phone')
        full_location = f"{state}, {zipcode}"

        photo_file = request.files.get('photo')
        photo_filename = None
        if photo_file and photo_file.filename != '':
            filename = secure_filename(photo_file.filename)
            photo_filename = f"{current_user.id}_{filename}"
            photo_path = os.path.join('static/uploads', photo_filename)
            photo_file.save(photo_path)

        new_profile = WorkerProfile(
            user_id=current_user.id,
            worker_code=worker_code,
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

        skills = request.form.getlist('skills[]')
        rates = request.form.getlist('rates[]')
        rate_types = request.form.getlist('rate_types[]')

        for skill_name, rate, rate_type in zip(skills, rates, rate_types):
            if skill_name.strip() == '' or rate.strip() == '':
                continue
            skill = Skill(
                name=skill_name.strip().lower(),
                rate=rate.strip(),
                rate_type=rate_type.strip(),
                location=full_location.strip(),
                user_id=current_user.id
            )
            db.session.add(skill)

        db.session.commit()
        flash("Profile created successfully.")

        # ✅ Replace current URL with /welcome, then push /seek_job
        return '''
        <!DOCTYPE html>
        <html>
        <head>
          <script>
            // Step 1: Replace current URL with /welcome (so create_worker_profile disappears)
            history.replaceState(null, '', '/welcome');

            // Step 2: Go back one step in browser history (to /welcome)
            history.back();
          </script>
        </head>
        </html>
        '''

    # --- HTML Page ---
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Create Worker Profile</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
        <style>
            body { background: #f5f7fa; }
            .profile-container {
                max-width: 800px;
                margin: auto;
                background: #fff;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            }
            .profile-pic {
                width: 140px;
                height: 140px;
                object-fit: cover;
                border-radius: 50%;
                border: 4px solid #0d6efd;
                transition: 0.3s ease;
            }
            .profile-pic:hover {
                opacity: 0.9;
                transform: scale(1.03);
            }
            .skill-row {
                display: flex;
                gap: 10px;
                margin-top: 10px;
                align-items: center;
                flex-wrap: nowrap;
            }
            .skill-row .form-control,
            .skill-row .form-select {
                flex: 1 1 auto;
                min-width: 0;
            }
            .skill-row .remove-btn {
                padding: 6px 10px;
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                white-space: nowrap;
                cursor: pointer;
                height: 38px;
            }
            @media (max-width: 768px) {
                .skill-row { flex-wrap: wrap; }
            }
        </style>
    </head>
    <body>
        <div class="container mt-5">
            <div class="profile-container">
                <h3 class="text-center mb-4 text-primary">🛠️ Create Your Worker Profile</h3>

                <form method="POST" enctype="multipart/form-data">
                    <div class="text-center mb-4">
                        <label for="photo" style="cursor:pointer;">
                            <img id="preview" src="/static/uploads/default.jpg" class="profile-pic" alt="Profile Photo">
                        </label>
                        <input type="file" id="photo" name="photo" accept="image/*" style="display:none;" onchange="loadPreview(event)">
                        <div class="form-text mt-2">Tap the photo to upload your image</div>
                    </div>

                    <div class="row g-3">
                        <div class="col-md-6">
                            <label class="form-label">Age</label>
                            <input type="number" class="form-control" name="age" required>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Gender</label>
                            <select class="form-select" name="gender" required>
                                <option value="" selected disabled>Select</option>
                                <option value="Male">Male</option>
                                <option value="Female">Female</option>
                            </select>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Phone Number</label>
                            <input type="text" class="form-control" name="phone" required>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Qualification</label>
                            <input type="text" class="form-control" name="qualification" required>
                        </div>
                        <div class="col-12">
                            <label class="form-label">Experience</label>
                            <input type="text" class="form-control" name="experience" required>
                        </div>
                        <div class="col-12">
                            <label class="form-label">About Me</label>
                            <textarea class="form-control" name="about" rows="3" required></textarea>
                        </div>
                    </div>

                    <h5 class="mt-4 mb-2 text-primary">🔧 Skills & Rates</h5>
                    <div id="skills-section">
                        <div class="skill-row">
                            <input type="text" class="form-control" name="skills[]" placeholder="Skill (e.g., Electrician)" required>
                            <input type="number" class="form-control" name="rates[]" placeholder="Rate (₹)" required>
                            <select class="form-select" name="rate_types[]" required>
                                <option value="per hour">₹/Hour</option>
                                <option value="per job">₹/Job</option>
                                <option value="per kilo">₹/Kilo</option>
                                <option value="per kilometer">₹/Kilometer</option>
                            </select>
                        </div>
                    </div>
                    <button type="button" class="btn btn-outline-secondary mt-2" onclick="addSkill()">➕ Add Skill</button>

                    <div class="mt-4">
                        <button type="submit" class="btn btn-primary w-100">Create Profile</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
            function addSkill() {
                const container = document.getElementById('skills-section');
                const row = document.createElement('div');
                row.className = 'skill-row';
                row.innerHTML = `
                    <input type="text" class="form-control" name="skills[]" placeholder="Skill" required>
                    <input type="number" class="form-control" name="rates[]" placeholder="Rate (₹)" required>
                    <select class="form-select" name="rate_types[]" required>
                        <option value="per hour">₹/Hour</option>
                        <option value="per job">₹/Job</option>
                        <option value="per kilo">₹/Kilo</option>
                        <option value="per kilometer">₹/Kilometer</option>
                    </select>
                    <button type="button" class="btn btn-danger" onclick="this.parentElement.remove()">Remove</button>
                `;
                container.appendChild(row);
            }

            function loadPreview(event) {
                const preview = document.getElementById('preview');
                preview.src = URL.createObjectURL(event.target.files[0]);
                preview.onload = () => URL.revokeObjectURL(preview.src);
            }
        </script>
    </body>
    </html>
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

        # Handle profile photo upload
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and allowed_file(photo.filename, ALLOWED_IMAGE_EXTENSIONS):
                if profile.photo:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], profile.photo)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                filename = secure_filename(photo.filename)
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                photo.save(photo_path)
                profile.photo = filename

        # Handle profile video upload
        if 'video' in request.files:
            video = request.files['video']
            if video and allowed_file(video.filename, ALLOWED_VIDEO_EXTENSIONS):
                if profile.video:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], profile.video)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                filename = secure_filename(video.filename)
                video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                video.save(video_path)
                profile.video = filename

        # Handle showcase images
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
        rate_types = request.form.getlist('rate_types')

        for skill_name, rate, rate_type in zip(skills, rates, rate_types):
            if skill_name.strip() and rate.strip():
                db.session.add(Skill(
                    name=skill_name.strip().lower(),
                    rate=rate.strip(),
                    rate_type=rate_type.strip(),
                    location=full_location,
                    user_id=current_user.id
                ))

        db.session.commit()
        flash("Profile updated successfully.")
        return '''
        <!DOCTYPE html>
        <html>
        <head>
          <script>
            window.location.replace("/seek_job");
          </script>
        </head>
        <body>
          <p>Redirecting...</p>
        </body>
        </html>
        '''

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

