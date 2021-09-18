from baby import db, login_manager
from flask_login import UserMixin
import random
import string

chars = string.ascii_lowercase + string.digits


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def __repr__(self):
        return f"User({self.username})"


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    host = db.Column(db.String(20), nullable=False)
    player_2 = db.Column(db.String(20))
    player_3 = db.Column(db.String(20))
    player_4 = db.Column(db.String(20))
    time_main = db.Column(db.Integer, nullable=False)
    time_increment = db.Column(db.Integer, nullable=False)
    key = db.Column(db.String(8), nullable=False)

    def __init__(self, host, time):
        self.host = host
        self.time_main, self.time_increment = map(int, time.split(","))
        self.key = "".join([random.choice(chars) for _ in range(8)])

    def __repr__(self):
        return f"{self.id}"

    def players(self):
        return 1 + sum([0 if i is None else 1 for i in [self.player_2, self.player_3, self.player_4]])

    def is_host(self, name):
        return self.host == name

    def is_in_game(self, name):
        return name in [self.host, self.player_2, self.player_3, self.player_4]
