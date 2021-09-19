from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from baby import app, db, bcrypt, chars, sio
from baby.models import User, Game
from random import choice


@app.route("/")
def home():
    return render_template("index.html", title="Online Baby Chess", games=Game.query.all())


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        if current_user.is_authenticated:
            return redirect(url_for("home"))
        else:
            return render_template("register.html", title="Register")
    elif request.method == "POST":
        print(request.form)
        username_valid = request.form["username"].isalnum() and 4 <= len(request.form["username"]) <= 20
        password_valid = request.form["password"].isalnum() and 4 <= len(request.form["password"]) <= 20
        username_unique = User.query.filter_by(username=request.form["username"]).first() is None
        if username_valid and password_valid:
            if username_unique:
                hashed_password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")
                new_user = User(username=request.form["username"], password=hashed_password)
                db.session.add(new_user)
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
            return render_template("login.html", title="Log in")
    elif request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user is not None and bcrypt.check_password_hash(user.password, request.form["password"]):
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
        return render_template("profile.html", title="Profile", user=user)
    else:
        return redirect(url_for("home"))


@app.route("/about")
def about():
    return render_template("about.html", title="About")


@app.route("/search")
def search():
    return render_template("search.html", title="Search")


@app.route("/settings")
def settings():
    return render_template("settings.html", title="Settings")


@app.route("/create", methods=["POST"])
@login_required
def create():
    if current_user.game is None:
        print(request.form)
        time_main, time_increment = map(int, request.form["time-control"].split(","))
        random_key = "".join([choice(chars) for _ in range(8)])
        new_game = Game(time_main=time_main, time_increment=time_increment, key=random_key)
        db.session.add(new_game)
        current_user.game = new_game
        db.session.commit()
        print(current_user.game)
    return redirect(url_for("home"))


@app.route("/game/<string:key>")
@login_required
def game(key):
    g = Game.query.filter_by(key=key).first()
    if g is None or g.is_full() or current_user not in g.players:
        return redirect(url_for("home"))
    else:
        current_user.game_id = g.id
        db.session.commit()
        return render_template("game.html", title="Play", game=g)


@app.route("/quit/<string:key>", methods=["POST"])
@login_required
def quit_game(key):
    g = Game.query.filter_by(key=key).first()
    if g is None or current_user.game_id != g.id:
        return redirect(url_for("home"))
    else:
        current_user.game_id = None
        if g.is_empty():
            db.session.delete(g)
        db.session.commit()
        return redirect(url_for("home"))


@app.route("/clear")
def clear():
    db.session.query(Game).delete()
    db.session.commit()
    return redirect("/")


client_count = 0


@sio.event
def connect():
    global client_count
    client_count += 1
    print("connected")
    sio.emit("client_count", client_count)


@sio.event
def disconnect():
    global client_count
    client_count -= 1
    print("disconnected")
    sio.emit("client_count", client_count)


@sio.event
def message_sent(data):
    sio.emit("message", data)
