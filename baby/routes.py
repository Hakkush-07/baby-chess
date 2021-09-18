from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from baby import app, db, bcrypt
from baby.models import User, Game


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


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", title="Profile")


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
def data():
    print(request.form)
    host_name = current_user.username if current_user.is_authenticated else "Anonymous"
    new_game = Game(host_name, request.form["time-control"])
    db.session.add(new_game)
    db.session.commit()
    return redirect(url_for("home"))


@app.route("/game/<string:key>")
@login_required
def game(key):
    g = Game.query.filter_by(key=key).first()
    if g is None:
        return redirect(url_for("home"))
    else:
        if g.host == current_user.username:
            pass
        elif g.player_2 is None:
            g.player_2 = current_user.username
        elif g.player_3 is None:
            g.player_3 = current_user.username
        elif g.player_4 is None:
            g.player_4 = current_user.username
        db.session.commit()
        return render_template("game.html", title="Play", game=g)


@app.route("/abort/<string:key>", methods=["POST"])
def abort(key):
    g = Game.query.filter_by(key=key).first()
    if g is None:
        return redirect(url_for("home"))
    else:
        db.session.delete(g)
        db.session.commit()
        return redirect(url_for("home"))


@app.route("/quit/<string:key>", methods=["POST"])
def quit_game(key):
    g = Game.query.filter_by(key=key).first()
    if g.is_in_game(current_user.username):
        if current_user.username == g.player_2:
            g.player_2 = None
        elif current_user.username == g.player_3:
            g.player_3 = None
        elif current_user.username == g.player_4:
            g.player_4 = None
        db.session.commit()
        return redirect(url_for("home"))
    else:
        return redirect(url_for("home"))
