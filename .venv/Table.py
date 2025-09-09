from flask import Flask, request, redirect, url_for, flash
from flask import render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, send
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

socketio = SocketIO(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --------------------
# Database Model
# --------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --------------------
# Routes
# --------------------
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            flash("Username already exists")
            return redirect(url_for('register'))
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))

    return render_template_string("""
    <h2>Register</h2>
    <form method="POST">
      <input type="text" name="username" placeholder="Username" required><br>
      <input type="password" name="password" placeholder="Password" required><br>
      <button type="submit">Register</button>
    </form>
    <a href="{{ url_for('login') }}">Already have an account? Login</a>
    """)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('chat'))
        flash("Invalid credentials")

    return render_template_string("""
    <h2>Login</h2>
    <form method="POST">
      <input type="text" name="username" placeholder="Username" required><br>
      <input type="password" name="password" placeholder="Password" required><br>
      <button type="submit">Login</button>
    </form>
    <a href="{{ url_for('register') }}">No account? Register</a>
    """)

@app.route('/chat')
@login_required
def chat():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Chat</title>
        <script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
    </head>
    <body>
    <h2>Welcome, {{ username }}</h2>
    <div id="messages" style="border:1px solid #ccc; height:200px; overflow:auto;"></div>
    <input id="messageInput" type="text" placeholder="Type a message">
    <button onclick="sendMessage()">Send</button>
    <a href="{{ url_for('logout') }}">Logout</a>

    <script>
        var socket = io();
        var messagesDiv = document.getElementById('messages');
        var input = document.getElementById('messageInput');

        socket.on('message', function(data) {
            messagesDiv.innerHTML += "<p><b>" + data.user + ":</b> " + data.msg + "</p>";
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        });

        function sendMessage() {
            if (input.value.trim() !== "") {
                socket.send(input.value);
                input.value = '';
            }
        }

        input.addEventListener("keydown", function(e) {
            if (e.key === "Enter") {
                sendMessage();
            }
        });
    </script>
    </body>
    </html>
    """, username=current_user.username)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --------------------
# Socket.IO Events
# --------------------
@socketio.on('message')
def handle_message(msg):
    send({'user': current_user.username, 'msg': msg}, broadcast=True)

# --------------------
# Run App
# --------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
