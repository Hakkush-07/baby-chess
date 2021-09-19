from baby import db, login_manager
from flask_login import UserMixin
import string

chars = string.ascii_lowercase + string.digits


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey("game.id"))

    def __repr__(self):
        return f"User({self.username})"


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time_main = db.Column(db.Integer, nullable=False)
    time_increment = db.Column(db.Integer, nullable=False)
    key = db.Column(db.String(8), nullable=False)
    players = db.relationship("User", backref="game", lazy=True)
    # chat = db.JSON()

    def __repr__(self):
        return f"Game({self.id}, {self.key})"

    def is_full(self):
        return self.count_players() >= 4

    def is_empty(self):
        return self.count_players() == 0

    def count_players(self):
        return len(self.players)

    def creator(self):
        if self.count_players():
            return self.players[0]

    def playing(self):
        return ", ".join([i.username for i in self.players])
