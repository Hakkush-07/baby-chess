import asyncio
import re
from datetime import datetime
import chess
from baby.constants import ROOM_ID, SEATS, START_TIME_SEC

class BoardState:
    def __init__(self):
        self.seats = {"white": None, "black": None}
        self.seat_names = {"white": None, "black": None}
        self.board = chess.Board()
        self.promotion_choice = {"white": "q", "black": "q"}
        self.captured = {
            "white": {piece: 0 for piece in ["P", "N", "B", "R", "Q"]},
            "black": {piece: 0 for piece in ["P", "N", "B", "R", "Q"]},
        }
        self.timers = {"white": START_TIME_SEC, "black": START_TIME_SEC}
        self.active_turn = None
        self.running = False
        self.last_move = None
        self.game_over = False

class GameState:
    def __init__(self):
        self.spectators = set()
        self.games = {game_id: BoardState() for game_id in [1, 2]}
        self.abandon_task = None
        self.connected_clients = {}
        self.game_started = False
        self.last_results = []

state = GameState()

sio = None

def set_sio(server):
    global sio
    sio = server

def ensure_sio():
    if sio is None:
        raise RuntimeError("Socket.IO server not configured")

def board_to_matrix(board):
    matrix = [["" for _ in range(8)] for _ in range(8)]
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue
        file_idx = chess.square_file(square)
        rank_idx = chess.square_rank(square)
        row = 7 - rank_idx
        col = file_idx
        color = "w" if piece.color == chess.WHITE else "b"
        matrix[row][col] = f"{color}{piece.symbol().upper()}"
    return matrix

def legal_moves_for_seat(game, seat):
    if game.game_over:
        return []
    if seat == "white" and game.board.turn != chess.WHITE:
        return []
    if seat == "black" and game.board.turn != chess.BLACK:
        return []
    if seat not in SEATS:
        return []
    moves = []
    for move in game.board.legal_moves:
        moves.append(
            {
                "from": {
                    "row": 7 - chess.square_rank(move.from_square),
                    "col": chess.square_file(move.from_square),
                },
                "to": {
                    "row": 7 - chess.square_rank(move.to_square),
                    "col": chess.square_file(move.to_square),
                },
            }
        )
    return moves

def legal_drops_for_seat(game, seat):
    if game.game_over:
        return {}
    if seat not in SEATS:
        return {}
    if seat == "white" and game.board.turn != chess.WHITE:
        return {}
    if seat == "black" and game.board.turn != chess.BLACK:
        return {}
    if seat != game.active_turn:
        return {}
    color = chess.WHITE if seat == "white" else chess.BLACK
    piece_map = {
        "P": chess.PAWN,
        "N": chess.KNIGHT,
        "B": chess.BISHOP,
        "R": chess.ROOK,
        "Q": chess.QUEEN,
    }
    drops = {}
    for piece_letter, count in game.captured.get(seat, {}).items():
        if count <= 0 or piece_letter not in piece_map:
            continue
        targets = []
        for square in chess.SQUARES:
            if game.board.piece_at(square):
                continue
            rank = chess.square_rank(square)
            if piece_letter == "P" and rank in (0, 7):
                continue
            test_board = game.board.copy()
            test_board.set_piece_at(square, chess.Piece(piece_map[piece_letter], color))
            if test_board.is_check():
                continue
            targets.append({"row": 7 - rank, "col": chess.square_file(square)})
        drops[piece_letter] = targets
    return drops

def has_legal_drop(game, seat):
    drops = legal_drops_for_seat(game, seat)
    return any(drops.values())

def snapshot_game(board_id, game):
    return {
        "seats": {k: v is not None for k, v in game.seats.items()},
        "seat_names": game.seat_names,
        "seat_teams": {
            "white": team_for(board_id, "white"),
            "black": team_for(board_id, "black"),
        },
        "promotion_choice": game.promotion_choice,
        "captured": game.captured,
        "timers": game.timers,
        "board": board_to_matrix(game.board),
        "active_turn": game.active_turn,
        "running": game.running,
        "last_move": game.last_move,
        "game_over": game.game_over,
    }

def all_seats_empty():
    return all(
        game.seats["white"] is None and game.seats["black"] is None
        for game in state.games.values()
    )

def any_game_running():
    return any(game.running for game in state.games.values())

def seat_for_client(game, client_id):
    if not client_id:
        return None
    for seat, owner in game.seats.items():
        if owner == client_id:
            return seat
    return None

def team_pool_target(board_id, seat):
    if board_id == 1 and seat == "white":
        return 2, "black"
    if board_id == 2 and seat == "black":
        return 1, "white"
    if board_id == 1 and seat == "black":
        return 2, "white"
    return 1, "black"

def team_for(board_id, seat):
    if board_id == 1 and seat == "white":
        return "blue"
    if board_id == 2 and seat == "black":
        return "blue"
    return "red"

def team_label(team):
    return "Blue" if team == "blue" else "Red"

def is_valid_username(username):
    return re.fullmatch(r"[A-Za-z0-9]{1,16}", username) is not None

def bottom_seats_for_client(client_id):
    defaults = {"1": "white", "2": "black"}
    if not client_id:
        return defaults
    user_team = None
    for game_id, game in state.games.items():
        seat = seat_for_client(game, client_id)
        if seat:
            user_team = team_for(game_id, seat)
            break
    if not user_team:
        return defaults
    if user_team == "blue":
        return {"1": "white", "2": "black"}
    return {"1": "black", "2": "white"}

def add_to_pool(board_id, seat, piece_letter):
    if piece_letter not in ["P", "N", "B", "R", "Q"]:
        return
    game = state.games[board_id]
    if seat not in game.captured:
        game.captured[seat] = {piece: 0 for piece in ["P", "N", "B", "R", "Q"]}
    if piece_letter not in game.captured[seat]:
        game.captured[seat][piece_letter] = 0
    game.captured[seat][piece_letter] += 1

def take_from_pool(board_id, seat, piece_letter):
    if piece_letter not in ["P", "N", "B", "R", "Q"]:
        return False
    game = state.games[board_id]
    if seat not in game.captured:
        return False
    if game.captured[seat].get(piece_letter, 0) <= 0:
        return False
    game.captured[seat][piece_letter] -= 1
    return True

async def broadcast_state():
    ensure_sio()
    base = {str(game_id): snapshot_game(game_id, game) for game_id, game in state.games.items()}
    for sid in list(state.spectators):
        session = await sio.get_session(sid)
        client_id = session.get("client_id")
        seats = {
            str(game_id): seat_for_client(game, client_id)
            for game_id, game in state.games.items()
        }
        payload = {
            "games": base,
            "your_seats": seats,
            "bottom_seats": bottom_seats_for_client(client_id),
            "legal_moves": {
                str(game_id): legal_moves_for_seat(game, seats.get(str(game_id)))
                for game_id, game in state.games.items()
            },
            "legal_drops": {
                str(game_id): legal_drops_for_seat(game, seats.get(str(game_id)))
                for game_id, game in state.games.items()
            },
            "last_games": state.last_results,
        }
        await sio.emit("room_state", payload, to=sid)

async def tick_loop():
    while True:
        await asyncio.sleep(1)
        for game_id, game in state.games.items():
            if not game.running or game.active_turn not in SEATS:
                continue
            if game.timers[game.active_turn] > 0:
                game.timers[game.active_turn] -= 1
            if game.timers[game.active_turn] == 0:
                winner_seat = "black" if game.active_turn == "white" else "white"
                await end_game(game_id, "Time out", team_for(game_id, winner_seat))
                continue
        await broadcast_state()

async def on_startup():
    for game in state.games.values():
        game.board = chess.Board()
        game.active_turn = "white"
        game.last_move = None
    asyncio.create_task(tick_loop())

async def reset_all_games():
    if state.abandon_task and not state.abandon_task.done():
        state.abandon_task.cancel()
        state.abandon_task = None
    state.game_started = False
    for game_id, game in state.games.items():
        game.board = chess.Board()
        game.timers = {"white": START_TIME_SEC, "black": START_TIME_SEC}
        game.active_turn = "white"
        game.running = False
        game.last_move = None
        game.game_over = False
        game.seats = {"white": None, "black": None}
        game.seat_names = {"white": None, "black": None}
        game.promotion_choice = {"white": "q", "black": "q"}
        game.captured = {
            "white": {piece: 0 for piece in ["P", "N", "B", "R", "Q"]},
            "black": {piece: 0 for piece in ["P", "N", "B", "R", "Q"]},
        }
        # Seats are keyed by client_id; no per-sid cleanup needed.
    await broadcast_state()

async def end_game(game_id, result_type, winner_team):
    ensure_sio()
    game = state.games[game_id]
    if game.game_over:
        return
    for other_game in state.games.values():
        other_game.game_over = True
        other_game.running = False
    state.game_started = False
    message = None
    if state.abandon_task and not state.abandon_task.done():
        state.abandon_task.cancel()
        state.abandon_task = None
    winner_names = []
    loser_names = []
    loser_team = "red" if winner_team == "blue" else "blue" if winner_team else None
    if winner_team:
        for gid, gstate in state.games.items():
            for seat in SEATS:
                team = team_for(gid, seat)
                if team == winner_team:
                    name = gstate.seat_names.get(seat)
                    if name:
                        winner_names.append(name)
                elif loser_team and team == loser_team:
                    name = gstate.seat_names.get(seat)
                    if name:
                        loser_names.append(name)
    state.last_results.insert(
        0,
        {
            "board": game_id,
            "winner_team": winner_team,
            "winner_names": winner_names,
            "loser_team": loser_team,
            "loser_names": loser_names,
            "date": datetime.now().strftime("%d.%m.%Y"),
        },
    )
    if len(state.last_results) > 5:
        state.last_results = state.last_results[:5]
    await sio.emit(
        "feed",
        {
            "kind": "result",
            "board": game_id,
            "result_type": result_type,
            "team": winner_team,
            "winner_names": winner_names,
            "message": message,
        },
        room=ROOM_ID,
    )
    await broadcast_state()
    await asyncio.sleep(30)
    await reset_all_games()

async def abandon_after_delay():
    ensure_sio()
    await sio.emit(
        "feed",
        {"message": "Everyone left. The game is abandoned and will be reset in 10 seconds."},
        room=ROOM_ID,
    )
    await asyncio.sleep(10)
    if all_seats_empty() and any_game_running():
        await reset_all_games()

def ensure_abandon_timer():
    if not any_game_running():
        if state.abandon_task and not state.abandon_task.done():
            state.abandon_task.cancel()
            state.abandon_task = None
        return
    if all_seats_empty():
        if not state.abandon_task or state.abandon_task.done():
            state.abandon_task = asyncio.create_task(abandon_after_delay())
    elif state.abandon_task and not state.abandon_task.done():
        state.abandon_task.cancel()
        state.abandon_task = None
