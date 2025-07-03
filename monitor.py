from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'devpanel-secret'  # Change this in production

# Direct path to your working DB
db_path = r"E:\CodingProjects\APP\.venv\jobconnect.db"
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)



# Import your models (or redefine if simple)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))
    # add other fields if needed

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer)
    provider_id = db.Column(db.Integer)
    worker_id = db.Column(db.Integer)
    status = db.Column(db.String(20))

class WorkerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_code = db.Column(db.String(20))
    user_id = db.Column(db.Integer)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    qualification = db.Column(db.String(100))
    experience = db.Column(db.String(100))
    about = db.Column(db.String(500))
    state = db.Column(db.String(100))
    zipcode = db.Column(db.String(20))
    phone = db.Column(db.String(20))
# Add other models as needed: Job, WorkerProfile, Rating, etc.

@app.route('/')
def home():
    return '''
    <h1>Developer Panel</h1>
    <ul>
        <li><a href="/users">View Users</a></li>
        <li><a href="/bookings">View Bookings</a></li>
        <li><a href="/jobs">View Jobs</a></li>
        <li><a href="/worker_profiles">View Worker Profiles</a></li>
    </ul>
    '''

@app.route('/worker_profiles')
def view_worker_profiles():
    profiles = WorkerProfile.query.all()
    table = """
    <h2>Worker Profiles</h2>
    <table border=1>
    <tr>
        <th>ID</th>
        <th>Worker Code</th>
        <th>User ID</th>
        <th>Age</th>
        <th>Gender</th>
        <th>Qualification</th>
        <th>Experience</th>
    </tr>
    """
    for p in profiles:
        table += f"<tr><td>{p.id}</td><td>{p.worker_code}</td><td>{p.user_id}</td><td>{p.age}</td><td>{p.gender}</td><td>{p.qualification}</td><td>{p.experience}</td></tr>"
    table += "</table><a href='/'>Back</a>"
    return table

@app.route('/users')
def view_users():
    users = User.query.all()
    table = "<h2>Users</h2><table border=1><tr><th>ID</th><th>Name</th><th>Email</th></tr>"
    for u in users:
        table += f"<tr><td>{u.id}</td><td>{u.name}</td><td>{u.email}</td></tr>"
    table += "</table><a href='/'>Back</a>"
    return table

@app.route('/bookings')
def view_bookings():
    bookings = Booking.query.all()
    table = "<h2>Bookings</h2><table border=1><tr><th>ID</th><th>Job ID</th><th>Provider ID</th><th>Worker ID</th><th>Status</th></tr>"
    for b in bookings:
        table += f"<tr><td>{b.id}</td><td>{b.job_id}</td><td>{b.provider_id}</td><td>{b.worker_id}</td><td>{b.status}</td></tr>"
    table += "</table><a href='/'>Back</a>"
    return table

# Add similar routes for jobs, worker profiles, ratings...

if __name__ == '__main__':
    app.run(port=5001, debug=True)

