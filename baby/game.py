from unittest import result
import chess
import chess.variant
import time

class Game:
    def __init__(self):
        self.playerXW = None
        self.playerXB = None
        self.playerYW = None
        self.playerYB = None
        self.timeXW = 180
        self.timeXB = 180
        self.timeYW = 180
        self.timeYB = 180
        self.boardX = chess.variant.CrazyhouseBoard()
        self.boardY = chess.variant.CrazyhouseBoard()
        self.ongoing = False
        self.previous_time = time.time()
        self.result_time = time.time()
        self.status = "Waiting for players"
    
    @staticmethod
    def player_string(player, space=False):
        p = player if player else "None"
        if space:
            return " " + p + " "
        else:
            return p
    
    @staticmethod
    def pocket_string(pocket):
        if pocket is None:
            return "[]"
        return f"[{str(pocket).upper()}]"
    
    @property
    def players(self):
        return [self.playerXW, self.playerXB, self.playerYW, self.playerYB]
    
    @property
    def players_dict(self):
        return {
            "xw": Game.player_string(self.playerXW, space=True), 
            "xb": Game.player_string(self.playerXB, space=True), 
            "yw": Game.player_string(self.playerYW, space=True), 
            "yb": Game.player_string(self.playerYB, space=True)
        }
    
    def change_pockets(self):
        pxw = self.boardX.pockets[1].copy()
        pxb = self.boardX.pockets[0].copy()
        pyw = self.boardY.pockets[1].copy()
        pyb = self.boardY.pockets[0].copy()
        self.boardX.pockets[1] = pyb
        self.boardX.pockets[0] = pyw
        self.boardY.pockets[1] = pxb
        self.boardY.pockets[0] = pxw
    
    def move_uci(self, username, uci, change_pockets=True):
        if username in [self.playerXW, self.playerXB]:
            if self.boardX.is_legal(chess.Move.from_uci(uci)):
                if change_pockets:
                    self.change_pockets()
                    self.boardX.push_uci(uci)
                    self.change_pockets()
                else:
                    self.boardX.push_uci(uci)
                self.ongoing = True
                self.status = "Playing"
                if username == self.playerXW:
                    self.timeXW += 2
                else:
                    self.timeXB += 2
                return True
            else:
                return False
        else:
            if self.boardY.is_legal(chess.Move.from_uci(uci)):
                if change_pockets:
                    self.change_pockets()
                    self.boardY.push_uci(uci)
                    self.change_pockets()
                else:
                    self.boardY.push_uci(uci)
                self.ongoing = True
                self.status = "Playing"
                if username == self.playerYW:
                    self.timeYW += 2
                else:
                    self.timeYB += 2
                return True
            else:
                return False
    
    def move(self, username, source, target, piece, color):
        if username not in self.players:
            return False
        if color == "w" and username not in [self.playerXW, self.playerYW]:
            return False
        if color == "b" and username not in [self.playerXB, self.playerYB]:
            return False
        if target != "offboard":
            if source == "spare":
                uci = f"{piece}@{target}"
                return self.move_uci(username, uci, change_pockets=False)
            else:
                uci = f"{source}{target}"
                return self.move_uci(username, uci, change_pockets=True)
        else:
            return False
    
    def update_players(self, username, role):
        if username in self.players:
            if role == "xw":
                if self.playerXW == username:
                    self.playerXW = None
            elif role == "xb":
                if self.playerXB == username:
                    self.playerXB = None
            elif role == "yw":
                if self.playerYW == username:
                    self.playerYW = None
            elif role == "yb":
                if self.playerYB == username:
                    self.playerYB = None
        else:
            if role == "xw":
                if not self.playerXW:
                    self.playerXW = username
            elif role == "xb":
                if not self.playerXB:
                    self.playerXB = username
            elif role == "yw":
                if not self.playerYW:
                    self.playerYW = username
            elif role == "yb":
                if not self.playerYB:
                    self.playerYB = username

    def adjust_time(self):
        t = time.time()
        diff = t - self.previous_time
        self.previous_time = t
        result = False
        if self.ongoing:
            if self.boardX.turn == chess.WHITE:
                self.timeXW -= diff
                if self.timeXW < 0:
                    self.timeXW = 0
                    self.ongoing = False
                    self.status = f"{self.playerXB} and {self.playerYW} win by time out"
                    result = True
                    self.reset()
            elif self.boardX.turn == chess.BLACK:
                self.timeXB -= diff
                if self.timeXB < 0:
                    self.timeXB = 0
                    self.ongoing = False
                    self.status = f"{self.playerXW} and {self.playerYB} win by time out"
                    result = True
                    self.reset()
            if self.boardY.turn == chess.WHITE:
                self.timeYW -= diff
                if self.timeYW < 0:
                    self.timeYW = 0
                    self.ongoing = False
                    self.status = f"{self.playerXW} and {self.playerYB} win by time out"
                    result = True
                    self.reset()
            elif self.boardY.turn == chess.BLACK:
                self.timeYB -= diff
                if self.timeYB < 0:
                    self.timeYB = 0
                    self.ongoing = False
                    self.status = f"{self.playerXB} and {self.playerYW} win by time out"
                    result = True
        return result

    def get_board(self, username):
        fen = "start"  # self.boardX.board_fen()
        fen_mini = "start"  # self.boardY.board_fen()
        orientation = "white"
        orientation_mini = "black"
        pocket_above = None  # self.boardX.pockets[0]
        pocket_below = None  # self.boardX.pockets[1]
        if username == self.playerXW:
            fen = self.boardX.board_fen()
            fen_mini = self.boardY.board_fen()
            orientation = "white"
            orientation_mini = "black"
            pocket_above = self.boardX.pockets[0]
            pocket_below = self.boardX.pockets[1]
        elif username == self.playerXB:
            fen = self.boardX.board_fen()
            fen_mini = self.boardY.board_fen()
            orientation = "black"
            orientation_mini = "white"
            pocket_above = self.boardX.pockets[1]
            pocket_below = self.boardX.pockets[0]
        elif username == self.playerYW:
            fen = self.boardY.board_fen()
            fen_mini = self.boardX.board_fen()
            orientation = "white"
            orientation_mini = "black"
            pocket_above = self.boardY.pockets[0]
            pocket_below = self.boardY.pockets[1]
        elif username == self.playerYB:
            fen = self.boardY.board_fen()
            fen_mini = self.boardX.board_fen()
            orientation = "black"
            orientation_mini = "white"
            pocket_above = self.boardY.pockets[1]
            pocket_below = self.boardY.pockets[0]
        data = {
            "fen": fen,
            "fen_mini": fen_mini,
            "orientation": orientation,
            "orientation_mini": orientation_mini,
            "pocket_above": Game.pocket_string(pocket_above),
            "pocket_below": Game.pocket_string(pocket_below)
        }
        return data
    
    def get_times(self, username):
        time_above = 180  # self.timeXB
        time_below = 180  # self.timeXW
        running_above = False
        running_below = True
        if username == self.playerXW:
            time_above = self.timeXB
            time_below = self.timeXW
            running_above = self.boardX.turn == chess.BLACK
            running_below = self.boardX.turn == chess.WHITE
        elif username == self.playerXB:
            time_above = self.timeXW
            time_below = self.timeXB
            running_above = self.boardX.turn == chess.WHITE
            running_below = self.boardX.turn == chess.BLACK
        elif username == self.playerYW:
            time_above = self.timeYB
            time_below = self.timeYW
            running_above = self.boardY.turn == chess.BLACK
            running_below = self.boardY.turn == chess.WHITE
        elif username == self.playerYB:
            time_above = self.timeYW
            time_below = self.timeYB
            running_above = self.boardY.turn == chess.WHITE
            running_below = self.boardY.turn == chess.BLACK
        data = {
            "time_above": int(time_above),
            "time_below": int(time_below),
            "running_above": running_above,
            "running_below": running_below
        }
        return data
    
    def get_table(self, username):
        player_above = None  # Game.player_string(self.playerXB)
        player_below = None  # Game.player_string(self.playerXW)
        if username == self.playerXW:
            player_above = self.playerXB
            player_below = self.playerXW
        elif username == self.playerXB:
            player_above = self.playerXW
            player_below = self.playerXB
        elif username == self.playerYW:
            player_above = self.playerYB
            player_below = self.playerYW
        elif username == self.playerYB:
            player_above = self.playerYW
            player_below = self.playerYB
        data = {
            "player_above": Game.player_string(player_above), 
            "player_below": Game.player_string(player_below)
        }
        return data
    
    def get_status(self):
        return self.status
    
    def update_result_time(self):
        self.result_time = time.time()
    
    def result_reset(self):
        return time.time() - self.result_time > 3

    def reset(self):
        self.playerXW = None
        self.playerXB = None
        self.playerYW = None
        self.playerYB = None
        self.timeXW = 180
        self.timeXB = 180
        self.timeYW = 180
        self.timeYB = 180
        self.boardX = chess.variant.CrazyhouseBoard()
        self.boardY = chess.variant.CrazyhouseBoard()
        self.ongoing = False
        self.previous_time = time.time()
        # self.status = "Waiting for players"
