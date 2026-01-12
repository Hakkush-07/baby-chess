import chess

from baby.constants import ROOM_ID, SEATS
from baby.babychess import *

def register_socket_handlers(sio):
    @sio.event
    async def connect(sid, environ, auth):
        client_id = None
        if isinstance(auth, dict):
            client_id = auth.get("client_id")
        if not client_id:
            client_id = sid
        await sio.save_session(sid, {"client_id": client_id})
        state.connected_clients[client_id] = state.connected_clients.get(client_id, 0) + 1
        await sio.enter_room(sid, ROOM_ID)
        state.spectators.add(sid)
        await broadcast_state()

    @sio.event
    async def disconnect(sid):
        session = await sio.get_session(sid)
        client_id = session.get("client_id")
        if client_id:
            current = state.connected_clients.get(client_id, 0)
            if current <= 1:
                state.connected_clients.pop(client_id, None)
            else:
                state.connected_clients[client_id] = current - 1
        state.spectators.discard(sid)
        ensure_abandon_timer()
        await broadcast_state()

    @sio.event
    async def seat_request(sid, data):
        board_id = int(data.get("board", 0))
        if board_id not in state.games:
            return
        game = state.games[board_id]
        seat = data.get("seat")
        if seat not in SEATS:
            return
        session = await sio.get_session(sid)
        client_id = session.get("client_id")
        if not client_id:
            return
        current_owner = game.seats.get(seat)
        if current_owner is not None and current_owner != client_id:
            if state.connected_clients.get(current_owner, 0) > 0:
                return
            game.seats[seat] = None
            game.seat_names[seat] = None
        if game.seats[seat] is None:
            username = data.get("username", "").strip()
            if not is_valid_username(username):
                return
            old_seat = seat_for_client(game, client_id)
            if old_seat:
                old_name = game.seat_names.get(old_seat)
                game.seats[old_seat] = None
                game.seat_names[old_seat] = None
                if old_name:
                    await sio.emit(
                        "feed",
                        {
                            "kind": "left",
                            "board": board_id,
                            "username": old_name,
                            "team": team_for(board_id, old_seat),
                            "seat": old_seat,
                        },
                        room=ROOM_ID,
                    )
            game.seats[seat] = client_id
            game.seat_names[seat] = username
            if seat not in game.promotion_choice:
                game.promotion_choice[seat] = "q"
            await sio.emit(
                "feed",
                {
                    "kind": "seat",
                    "board": board_id,
                    "username": username,
                    "team": team_for(board_id, seat),
                    "seat": seat,
                },
                room=ROOM_ID,
            )
        elif game.seats[seat] == client_id:
            username = data.get("username", "").strip()
            if username and is_valid_username(username):
                game.seat_names[seat] = username
        ensure_abandon_timer()
        await broadcast_state()

    @sio.event
    async def leave_seat(sid, data):
        session = await sio.get_session(sid)
        client_id = session.get("client_id")
        board_id = int(data.get("board", 0))
        if board_id not in state.games:
            return
        game = state.games[board_id]
        seat = seat_for_client(game, client_id)
        if seat and game.seats.get(seat) == client_id:
            username = game.seat_names.get(seat)
            game.seats[seat] = None
            game.seat_names[seat] = None
            game.promotion_choice[seat] = "q"
            if username:
                await sio.emit(
                    "feed",
                    {
                        "kind": "left",
                        "board": board_id,
                        "username": username,
                        "team": team_for(board_id, seat),
                        "seat": seat,
                    },
                    room=ROOM_ID,
                )
        ensure_abandon_timer()
        await broadcast_state()

    @sio.event
    async def promotion_select(sid, data):
        session = await sio.get_session(sid)
        client_id = session.get("client_id")
        board_id = int(data.get("board", 0))
        if board_id not in state.games:
            return
        game = state.games[board_id]
        seat = seat_for_client(game, client_id)
        if seat not in SEATS:
            return
        choice = data.get("choice", "").lower()
        if choice not in ("q", "r", "b", "n"):
            return
        state.games[board_id].promotion_choice[seat] = choice
        await broadcast_state()

    @sio.event
    async def move(sid, data):
        session = await sio.get_session(sid)
        client_id = session.get("client_id")
        board_id = int(data.get("board", 0))
        if board_id not in state.games:
            return
        game = state.games[board_id]
        seat = seat_for_client(game, client_id)
        if seat not in SEATS or game.game_over:
            return
        if not game.running:
            if seat != "white":
                return
            if not game.active_turn:
                game.active_turn = "white"
            if not state.game_started:
                state.game_started = True
                for other_game in state.games.values():
                    other_game.running = True
                    if not other_game.active_turn:
                        other_game.active_turn = "white"
                await sio.emit("game_start", {}, room=ROOM_ID)
                await sio.emit(
                    "feed",
                    {"kind": "start", "message": "Game has started."},
                    room=ROOM_ID,
                )
            else:
                game.running = True
        if seat != game.active_turn:
            return
        if seat == "white" and game.board.turn != chess.WHITE:
            return
        if seat == "black" and game.board.turn != chess.BLACK:
            return

        from_pos = data.get("from")
        to_pos = data.get("to")
        drop = data.get("drop")
        if not to_pos:
            return

        tr = to_pos.get("row")
        tc = to_pos.get("col")
        if None in (tr, tc):
            return
        if not all(0 <= v < 8 for v in (tr, tc)):
            return

        to_square = chess.square(tc, 7 - tr)

        if drop:
            piece_letter = drop.get("piece", "").upper()
            if piece_letter not in ["P", "N", "B", "R", "Q"]:
                return
            if game.board.piece_at(to_square):
                return
            if piece_letter == "P" and chess.square_rank(to_square) in (0, 7):
                return
            if game.captured[seat].get(piece_letter, 0) <= 0:
                return
            color = chess.WHITE if seat == "white" else chess.BLACK
            piece_type_map = {
                "P": chess.PAWN,
                "N": chess.KNIGHT,
                "B": chess.BISHOP,
                "R": chess.ROOK,
                "Q": chess.QUEEN,
            }
            test_board = game.board.copy()
            test_board.set_piece_at(
                to_square, chess.Piece(piece_type_map[piece_letter], color)
            )
            if test_board.is_check():
                return
            if not take_from_pool(board_id, seat, piece_letter):
                return
            game.board.set_piece_at(
                to_square, chess.Piece(piece_type_map[piece_letter], color)
            )
            if game.board.turn == chess.BLACK:
                game.board.fullmove_number += 1
            game.board.turn = not game.board.turn
            game.last_move = {
                "from": {"row": tr, "col": tc},
                "to": {"row": tr, "col": tc},
            }
            increment = int(state.time_control.get("increment", 0))
            game.timers[seat] += increment
            game.active_turn = "white" if game.board.turn == chess.WHITE else "black"
            await sio.emit(
                "move",
                {
                    "board": board_id,
                    "from": {"row": tr, "col": tc},
                    "to": {"row": tr, "col": tc},
                    "capture": False,
                    "drop": piece_letter,
                    "check": game.board.is_check(),
                    "promotion": False,
                    "castle": False,
                },
                room=ROOM_ID,
            )
            username = game.seat_names.get(seat) or seat.title()
            suffix = ""
            if game.board.is_checkmate():
                suffix = "#"
            elif game.board.is_check():
                suffix = "+"
            await sio.emit(
                "feed",
                {
                    "kind": "move",
                    "board": board_id,
                    "username": username,
                    "team": team_for(board_id, seat),
                    "move": f"{piece_letter}@{chess.square_name(to_square)}{suffix}",
                },
                room=ROOM_ID,
            )
            if game.board.is_checkmate():
                defender_seat = "white" if game.board.turn == chess.WHITE else "black"
                if not has_legal_drop(game, defender_seat):
                    await end_game(board_id, "Checkmate", team_for(board_id, seat))
                    return
            if game.board.is_stalemate():
                await end_game(board_id, "Stalemate", None)
                return
            if game.board.is_insufficient_material():
                await end_game(board_id, "Draw by insufficient material", None)
                return
            if game.board.can_claim_threefold_repetition():
                await end_game(board_id, "Draw by repetition", None)
                return
            await broadcast_state()
            return

        if not from_pos:
            return

        fr = from_pos.get("row")
        fc = from_pos.get("col")
        if None in (fr, fc):
            return
        if not all(0 <= v < 8 for v in (fr, fc)):
            return
        from_square = chess.square(fc, 7 - fr)
        piece = game.board.piece_at(from_square)
        if not piece:
            return
        capture_move = chess.Move(from_square, to_square)
        captured_piece = None
        captured_promoted = False
        capture_square = None
        if game.board.is_capture(capture_move):
            if game.board.is_en_passant(capture_move):
                capture_square = chess.square(
                    chess.square_file(to_square), chess.square_rank(from_square)
                )
                captured_piece = game.board.piece_at(capture_square)
            else:
                capture_square = to_square
                captured_piece = game.board.piece_at(to_square)
            if capture_square is not None:
                captured_promoted = bool(game.board.promoted & chess.BB_SQUARES[capture_square])
        move = chess.Move(from_square, to_square)
        if piece.piece_type == chess.PAWN and chess.square_rank(to_square) in (0, 7):
            promo = game.promotion_choice.get(seat, "q")
            promo_map = {"q": chess.QUEEN, "r": chess.ROOK, "b": chess.BISHOP, "n": chess.KNIGHT}
            move = chess.Move(from_square, to_square, promotion=promo_map.get(promo, chess.QUEEN))
        if move not in game.board.legal_moves:
            return
        san = game.board.san(move)
        game.board.push(move)
        game.last_move = {"from": {"row": fr, "col": fc}, "to": {"row": tr, "col": tc}}
        if captured_piece:
            if captured_promoted:
                piece_letter = "P"
            else:
                piece_letter = captured_piece.symbol().upper()
            pool_board_id, pool_seat = team_pool_target(board_id, seat)
            add_to_pool(pool_board_id, pool_seat, piece_letter)
        increment = int(state.time_control.get("increment", 0))
        game.timers[seat] += increment
        game.active_turn = "white" if game.board.turn == chess.WHITE else "black"
        await sio.emit(
            "move",
            {
                "board": board_id,
                "from": {"row": fr, "col": fc},
                "to": {"row": tr, "col": tc},
                "capture": bool(captured_piece),
                "castle": game.board.is_castling(move),
                "promotion": bool(move.promotion),
                "check": game.board.is_check(),
            },
            room=ROOM_ID,
        )
        username = game.seat_names.get(seat) or seat.title()
        await sio.emit(
            "feed",
            {
                "kind": "move",
                "board": board_id,
                "username": username,
                "team": team_for(board_id, seat),
                "move": san,
            },
            room=ROOM_ID,
        )
        if game.board.is_checkmate():
            defender_seat = "white" if game.board.turn == chess.WHITE else "black"
            if not has_legal_drop(game, defender_seat):
                await end_game(board_id, "Checkmate", team_for(board_id, seat))
                return
        if game.board.is_stalemate():
            await end_game(board_id, "Stalemate", None)
            return
        if game.board.is_insufficient_material():
            await end_game(board_id, "Draw by insufficient material", None)
            return
        if game.board.can_claim_threefold_repetition():
            await end_game(board_id, "Draw by repetition", None)
            return
        await broadcast_state()

    @sio.event
    async def time_control(sid, data):
        session = await sio.get_session(sid)
        client_id = session.get("client_id")
        if not client_id:
            return
        has_seat = any(
            seat_for_client(game, client_id) in SEATS for game in state.games.values()
        )
        if not has_seat:
            return
        start_time = data.get("start_time")
        increment = data.get("increment")
        try:
            start_time = int(start_time)
            increment = int(increment)
        except (TypeError, ValueError):
            return
        allowed = {(180, 0), (180, 2), (300, 0), (300, 3)}
        if (start_time, increment) not in allowed:
            return
        state.time_control = {"start_time": start_time, "increment": increment}
        player_name = None
        player_team = None
        for game_id, game in state.games.items():
            seat = seat_for_client(game, client_id)
            if seat:
                player_team = team_for(game_id, seat)
                player_name = game.seat_names.get(seat) or seat.title()
                break
        time_label = f"{start_time // 60}+{increment}"
        if not any_game_running():
            for game in state.games.values():
                game.timers = {"white": start_time, "black": start_time}
            await sio.emit(
                "feed",
                {
                    "kind": "time_control",
                    "username": player_name or "Player",
                    "team": player_team,
                    "time_control": time_label,
                    "next_game": False,
                },
                room=ROOM_ID,
            )
        else:
            await sio.emit(
                "feed",
                {
                    "kind": "time_control",
                    "username": player_name or "Player",
                    "team": player_team,
                    "time_control": time_label,
                    "next_game": True,
                },
                room=ROOM_ID,
            )
        await broadcast_state()

    @sio.event
    async def chat_message(sid, data):
        session = await sio.get_session(sid)
        client_id = session.get("client_id")
        if not client_id:
            return
        message = (data.get("message") or "").strip()
        if not message:
            return
        if len(message) > 240:
            return

        active_name = None
        active_team = None
        for board_id, game in state.games.items():
            seat = seat_for_client(game, client_id)
            if seat and game.seat_names.get(seat):
                active_name = game.seat_names.get(seat)
                active_team = team_for(board_id, seat)
                break
        if not active_name:
            return

        await sio.emit(
            "chat",
            {"username": active_name, "message": message, "team": active_team},
            room=ROOM_ID,
        )
