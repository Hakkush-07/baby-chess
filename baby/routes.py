from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, current_user, logout_user, login_required
from baby import app, db, bcrypt, sio
from baby.models import User
from baby.game import Game

dummy = Game()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/game")
@login_required
def game():
    return render_template("game.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        if current_user.is_authenticated:
            return redirect(url_for("home"))
        else:
            return render_template("register.html")
    elif request.method == "POST":
        username_valid = request.form["username"].isalnum() and 4 <= len(request.form["username"]) <= 20
        password_valid = request.form["password"].isalnum() and 4 <= len(request.form["password"]) <= 20
        username_unique = User.query.filter_by(username=request.form["username"]).first() is None
        if username_valid and password_valid:
            if username_unique:
                hashed_password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")
                user = User(username=request.form["username"], password=hashed_password)
                db.session.add(user)
                db.session.commit()
                return redirect(url_for("login"))
            else:
                flash("This username is not available")
                return redirect(url_for("register"))
        else:
            flash("Invalid username or password")
            return redirect(url_for("register"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if current_user.is_authenticated:
            return redirect(url_for("home"))
        else:
            return render_template("login.html")
    elif request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and bcrypt.check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect(url_for("home"))
        else:
            flash("Check your username and password")
            return redirect(url_for("login"))

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/@/<string:username>")
def profile(username):
    user = User.query.filter_by(username=username).first()
    if user:
        return render_template("profile.html", user=user, is_admin=username == "admin")
    else:
        return redirect(url_for("home"))

@sio.event
def connect():
    sio.emit("players", dummy.players_dict)
    sio.emit("board")
    sio.emit("table")
    sio.emit("times")
    sio.emit("info", f"{current_user.username} joined")

@sio.event
def disconnect():
    sio.emit("info", f"{current_user.username} left")

@sio.event
def message(msg):
    sio.emit("message", {"author": current_user.username, "message": msg})

@sio.event
def drop(data):
    source = data["source"]
    target = data["target"]
    piece = data["piece"][-1]
    color = data["piece"][0]
    if dummy.move(current_user.username, source, target, piece, color):
        sio.emit("board")
        sio.emit("times")
        sio.emit("game_status")
    return dummy.get_board(current_user.username)

@sio.event
def join(role):
    dummy.update_players(current_user.username, role)
    sio.emit("players", dummy.players_dict)
    sio.emit("board")
    sio.emit("table")
    sio.emit("times")

@sio.event
def get_board(data):
    return dummy.get_board(current_user.username)

@sio.event
def get_times(data):
    return dummy.get_times(current_user.username)

@sio.event
def get_table(data):
    return dummy.get_table(current_user.username)

@sio.event
def get_status(data):
    return dummy.get_status()

@sio.event
def time():
    if dummy.adjust_time():
        sio.emit("game_status")
        sio.emit("game_over")
        dummy.update_result_time()
    if not dummy.ongoing and dummy.result_reset():
        dummy.status = "Waiting for players"
        sio.emit("players", dummy.players_dict)
        sio.emit("board")
        sio.emit("table")
        sio.emit("times")
