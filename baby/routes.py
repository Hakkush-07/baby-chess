from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from flask_socketio import join_room, leave_room
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
        time_main, time_increment = map(int, request.form["time-control"].split(","))
        random_key = "".join([choice(chars) for _ in range(8)])
        new_game = Game(time_main=time_main, time_increment=time_increment, key=random_key)
        db.session.add(new_game)
        current_user.game = new_game
        db.session.commit()
        sio.emit("game_change", "")
    return redirect(url_for("home"))


@app.route("/game/<string:key>")
@login_required
def game(key):
    g = Game.query.filter_by(key=key).first()
    if g is None or g.is_full():
        return redirect(url_for("home"))
    else:
        current_user.game = g
        if current_user.role is None:
            current_user.role = g.get_role()
        db.session.commit()
        sio.emit("game_change", "")
        return render_template("game.html", title="Play", game=g)


@app.route("/quit/<string:key>", methods=["POST"])
@login_required
def quit_game(key):
    g = Game.query.filter_by(key=key).first()
    if g is None or current_user.game_id != g.id:
        return redirect(url_for("home"))
    else:
        current_user.game = None
        current_user.role = None
        if g.is_empty():
            db.session.delete(g)
        db.session.commit()
        sio.emit("game_change", "")
        return redirect(url_for("home"))


@app.route("/clear")
def clear():
    db.session.query(Game).delete()
    db.session.commit()
    return redirect("/")


@sio.event
def connect():
    room = current_user.game.key
    join_room(room)
    sio.emit("information", {"username": current_user.username, "info": "joined"}, to=room)
    sio.emit("player", [current_user.role, current_user.username], to=room)


@sio.event
def disconnect():
    room = current_user.game.key
    leave_room(room)
    sio.emit("information", {"username": current_user.username, "info": "left"}, to=room)
    sio.emit("player", [current_user.role, "...waiting..."], to=room)


@sio.event
def get_board(a):
    pieces_1, pockets_1 = current_user.game.fen2list(1)
    pieces_2, pockets_2 = current_user.game.fen2list(2)
    pieces_main = pieces_1 if current_user.role.endswith("1") else pieces_2
    pieces_side = pieces_2 if current_user.role.endswith("1") else pieces_1
    pockets_main = pockets_1 if current_user.role.endswith("1") else pockets_2
    pockets_side = pockets_2 if current_user.role.endswith("1") else pockets_1
    orientation = 1 if current_user.role.startswith("w") else 0
    board = {
        "orientation": orientation,
        "board_main": {
            "pieces": pieces_main,
            "pockets": pockets_main,
            "last_move": [[3, 4], [5, 6]]
        },
        "board_side": {
            "pieces": pieces_side,
            "pockets": pockets_side,
            "last_move": [[3, 4], [3, 5]]
        }
    }
    return board


@sio.event
def message_sent(data):
    room = current_user.game.key
    if data["message"].startswith("!"):
        try:
            current_user.game.move_control(current_user.role, data["message"][1:])
            sio.emit("move", "", to=room)
        except:
            print("wrong move")
    else:
        sio.emit("message", data, to=room)
