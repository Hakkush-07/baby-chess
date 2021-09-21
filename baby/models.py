from baby import db, login_manager
from flask_login import UserMixin
import string
import chess

chars = string.ascii_lowercase + string.digits
starting_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR[] w KQkq - 0 1"


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
    fen_1 = db.Column(db.String(50), nullable=False, default=starting_fen)
    fen_2 = db.Column(db.String(50), nullable=False, default=starting_fen)
    pocket_w1 = db.Column(db.String(50), nullable=False, default="")
    pocket_b1 = db.Column(db.String(50), nullable=False, default="")
    pocket_w2 = db.Column(db.String(50), nullable=False, default="")
    pocket_b2 = db.Column(db.String(50), nullable=False, default="")

    def __repr__(self):
        return f"Game({self.id}, {self.key})"

    def is_full(self):
        return self.count_players() >= 4

    def is_empty(self):
        return self.count_players() == 0

    def count_players(self):
        return len(self.players)

    def playing(self):
        return ", ".join([i.username for i in self.players])

    def fen2list(self, board_number):
        fen = self.fen_1 if board_number == 1 else self.fen_2
        board, rest = fen.split("[")
        pockets = rest.split("]")[0]
        for c in range(1, 10):
            board = board.replace(str(c), "e" * c)
        names = ["pawn", "knight", "bishop", "rook", "queen", "king"]
        white = ["P", "N", "B", "R", "Q", "K"]
        black = ["p", "n", "b", "r", "q", "k"]
        board = list(map(list, board.split("/")))
        pieces = []
        for i in range(8):
            for j in range(8):
                piece_symbol = board[i][j]
                if piece_symbol in white:
                    piece_name = names[white.index(piece_symbol)]
                    pieces.append(["white " + piece_name, [j + 1, 8 - i]])
                elif piece_symbol in black:
                    piece_name = names[black.index(piece_symbol)]
                    pieces.append(["black " + piece_name, [j + 1, 8 - i]])
        names_wo_king = names[:-1]
        pocket_pieces = {
            "white": [["white", n, pockets.count(white[names_wo_king.index(n)])] for n in names_wo_king],
            "black": [["black", n, pockets.count(black[names_wo_king.index(n)])] for n in names_wo_king]
        }
        return pieces, pocket_pieces
