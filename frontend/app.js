const clientIdKey = "baby_chess_client_id";
let clientId = localStorage.getItem(clientIdKey);
if (!clientId) {
  clientId = crypto.randomUUID();
  localStorage.setItem(clientIdKey, clientId);
}

const socket = io({ path: "/socket.io", auth: { client_id: clientId } });

const log = document.getElementById("log");
const seatButtons = document.querySelectorAll(".seat-btn");
const promoSelects = document.querySelectorAll(".promo-select");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const lastGamesEl = document.getElementById("lastGames");

const moveSound = new Audio("/assets/sounds/move.mp3");
const captureSound = new Audio("/assets/sounds/capture.mp3");
const notifySound = new Audio("/assets/sounds/notify.mp3");
const castleSound = new Audio("/assets/sounds/castle.mp3");
const checkSound = new Audio("/assets/sounds/check.mp3");
const promoteSound = new Audio("/assets/sounds/promote.mp3");
const gameEndSound = new Audio("/assets/sounds/game-end.mp3");
const gameStartSound = new Audio("/assets/sounds/game-start.mp3");
const USERNAME_RE = /^[A-Za-z0-9]{1,16}$/;

let lastGames = {};

const boards = {
  1: initBoardState(1),
  2: initBoardState(2),
};

function initBoardState(boardId) {
  return {
    boardId,
    baseBottomSeat: boardId === 1 ? "white" : "black",
    boardEl: document.getElementById(`board-${boardId}`),
    gameEl: document.querySelector(`.game[data-board="${boardId}"]`),
    nameWhiteEl: document.getElementById(`nameWhite${boardId}`),
    nameBlackEl: document.getElementById(`nameBlack${boardId}`),
    displayWhiteEl: document.getElementById(`displayWhite${boardId}`),
    displayBlackEl: document.getElementById(`displayBlack${boardId}`),
    promoWhiteEl: document.getElementById(`promoWhite${boardId}`),
    promoBlackEl: document.getElementById(`promoBlack${boardId}`),
    promoWrapWhiteEl: document.getElementById(`promoWrapWhite${boardId}`),
    promoWrapBlackEl: document.getElementById(`promoWrapBlack${boardId}`),
    timerWhiteEl: document.getElementById(`timerWhite${boardId}`),
    timerBlackEl: document.getElementById(`timerBlack${boardId}`),
    timerBoxWhiteEl: document.getElementById(`timerBoxWhite${boardId}`),
    timerBoxBlackEl: document.getElementById(`timerBoxBlack${boardId}`),
    capturesTopEl: document.getElementById(`capturesTop${boardId}`),
    capturesBottomEl: document.getElementById(`capturesBottom${boardId}`),
    selected: null,
    selectedDrop: null,
    bottomSeat: boardId === 1 ? "white" : "black",
    lastBottomSeat: boardId === 1 ? "white" : "black",
    lastBoard: "",
    lastMoveKey: "",
    yourSeat: null,
    activeSeat: null,
    currentBoard: null,
    legalMovesMap: {},
    legalDrops: {},
    lastMove: null,
  };
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function renderBoard(boardId, boardState) {
  const state = boards[boardId];
  const boardEl = state.boardEl;
  boardEl.innerHTML = "";
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      const flipped = state.bottomSeat === "black";
      const modelRow = flipped ? 7 - row : row;
      const modelCol = flipped ? 7 - col : col;
      const square = document.createElement("div");
      const dark = (row + col) % 2 ? " dark" : "";
      const lastMoveClass =
        state.lastMove &&
        ((state.lastMove.from.row === modelRow && state.lastMove.from.col === modelCol) ||
          (state.lastMove.to.row === modelRow && state.lastMove.to.col === modelCol))
          ? " last-move"
          : "";
      square.className = `square${dark}${lastMoveClass}`;
      square.dataset.row = row;
      square.dataset.col = col;
      square.dataset.modelRow = modelRow;
      square.dataset.modelCol = modelCol;
      square.addEventListener("click", (event) => onSquareClick(event, boardId));
      const piece = boardState[modelRow][modelCol];
      if (piece) {
        const img = document.createElement("img");
        img.src = `/assets/piece-images/${piece}.png`;
        img.alt = piece;
        img.className = "piece";
        square.appendChild(img);
      }
      boardEl.appendChild(square);
    }
  }

  if (state.selected) {
    const piece = boardState[state.selected.row][state.selected.col];
    if (!piece) {
      clearSelection(boardId);
      return;
    }
    const selector = `.square[data-model-row="${state.selected.row}"][data-model-col="${state.selected.col}"]`;
    const selectedEl = boardEl.querySelector(selector);
    if (selectedEl) selectedEl.classList.add("selected");
    showLegalMoves(boardId, state.selected);
  }

  if (state.selectedDrop && state.yourSeat === state.activeSeat) {
    showDropMoves(boardId);
  }
}

function updateCrossBoardCaptures(games) {
  if (!games["1"] || !games["2"]) return;
  const pool1 = games["1"].captured || { white: {}, black: {} };
  const pool2 = games["2"].captured || { white: {}, black: {} };
  const board1Top = expandPool(pool1.black, "b");
  const board1Bottom = expandPool(pool1.white, "w");
  const board2Top = expandPool(pool2.white, "w");
  const board2Bottom = expandPool(pool2.black, "b");
  renderCaptureRow(boards[1].capturesTopEl, board1Top, 1, "black", boards[1].selectedDrop);
  renderCaptureRow(boards[1].capturesBottomEl, board1Bottom, 1, "white", boards[1].selectedDrop);
  renderCaptureRow(boards[2].capturesTopEl, board2Top, 2, "white", boards[2].selectedDrop);
  renderCaptureRow(boards[2].capturesBottomEl, board2Bottom, 2, "black", boards[2].selectedDrop);
}

function expandPool(pool, color) {
  const order = ["Q", "R", "B", "N", "P"];
  const expanded = [];
  order.forEach((piece) => {
    const count = pool[piece] || 0;
    for (let i = 0; i < count; i += 1) {
      expanded.push(`${color}${piece}`);
    }
  });
  return expanded;
}

function renderCaptureRow(container, pieces, boardId, seat, selectedDrop) {
  container.innerHTML = "";
  pieces.forEach((piece) => {
    const img = document.createElement("img");
    img.src = `/assets/piece-images/${piece}.png`;
    img.alt = piece;
    img.className = "capture-piece";
    img.dataset.board = String(boardId);
    img.dataset.seat = seat;
    img.dataset.piece = piece[1];
    if (selectedDrop === piece[1]) {
      img.classList.add("selected");
    }
    img.addEventListener("click", onCapturePieceClick);
    container.appendChild(img);
  });
}

function addLog(message) {
  const entry = document.createElement("div");
  entry.className = "log-entry";
  entry.textContent = message;
  log.prepend(entry);
}

function addChatMessage(username, message, team) {
  const entry = document.createElement("div");
  entry.className = "chat-entry";
  if (team) {
    const name = document.createElement("span");
    name.className = teamClass(team);
    name.textContent = `${username}: `;
    entry.appendChild(name);
    entry.appendChild(document.createTextNode(message));
  } else {
    entry.appendChild(document.createTextNode(`${username}: ${message}`));
  }
  chatMessages.appendChild(entry);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderLastGames(entries) {
  if (!lastGamesEl) return;
  lastGamesEl.innerHTML = "";
  const items = Array.isArray(entries) ? entries : [];
  items.forEach((item) => {
    if (!item || !item.winner_team || !item.loser_team || !item.date) return;
    const entry = document.createElement("div");
    entry.className = "log-entry";
    const winnerNames = Array.isArray(item.winner_names) ? item.winner_names : [];
    const loserNames = Array.isArray(item.loser_names) ? item.loser_names : [];
    const winnerNamesText = winnerNames.length ? winnerNames.join(", ") : "Unknown";
    const loserNamesText = loserNames.length ? loserNames.join(", ") : "Unknown";
    const winnerSpan = document.createElement("span");
    winnerSpan.className = teamClass(item.winner_team);
    winnerSpan.textContent = winnerNamesText;
    entry.appendChild(winnerSpan);
    entry.appendChild(document.createTextNode(" won against "));
    const loserSpan = document.createElement("span");
    loserSpan.className = teamClass(item.loser_team);
    loserSpan.textContent = loserNamesText;
    entry.appendChild(loserSpan);
    entry.appendChild(document.createTextNode(` [${item.date}]`));
    lastGamesEl.appendChild(entry);
  });
}

function teamFor(boardId, seat) {
  if (boardId === 1 && seat === "white") return "blue";
  if (boardId === 2 && seat === "black") return "blue";
  return "red";
}

function teamLabel(team) {
  return team === "blue" ? "Blue" : "Red";
}

function teamClass(team) {
  return team === "blue" ? "team-blue" : "team-red";
}

function clearSelection(boardId) {
  const state = boards[boardId];
  const selectedEl = state.boardEl.querySelector(".square.selected");
  if (selectedEl) selectedEl.classList.remove("selected");
  clearMoveDots(boardId);
  state.selected = null;
}

function clearMoveDots(boardId) {
  const boardEl = boards[boardId].boardEl;
  boardEl.querySelectorAll(".move-dot").forEach((dot) => dot.remove());
  boardEl.querySelectorAll(".square.legal-dest").forEach((sq) => sq.classList.remove("legal-dest"));
}

function showLegalMoves(boardId, from) {
  clearMoveDots(boardId);
  const state = boards[boardId];
  const key = `${from.row},${from.col}`;
  const destinations = state.legalMovesMap[key] || [];
  destinations.forEach((dest) => {
    const selector = `.square[data-model-row="${dest.row}"][data-model-col="${dest.col}"]`;
    const square = state.boardEl.querySelector(selector);
    if (!square) return;
    square.classList.add("legal-dest");
    const dot = document.createElement("span");
    dot.className = "move-dot";
    square.appendChild(dot);
  });
}

function showDropMoves(boardId) {
  clearMoveDots(boardId);
  const state = boards[boardId];
  if (!state.currentBoard || !state.selectedDrop) return;
  const targets = state.legalDrops[state.selectedDrop] || [];
  targets.forEach((dest) => {
    const selector = `.square[data-model-row="${dest.row}"][data-model-col="${dest.col}"]`;
    const square = state.boardEl.querySelector(selector);
    if (!square) return;
    square.classList.add("legal-dest");
    const dot = document.createElement("span");
    dot.className = "move-dot";
    square.appendChild(dot);
  });
}

function onSquareClick(event, boardId) {
  const state = boards[boardId];
  const square = event.currentTarget;
  const row = Number(square.dataset.modelRow);
  const col = Number(square.dataset.modelCol);
  const piece = state.currentBoard ? state.currentBoard[row][col] : "";
  const isOwnPiece =
    piece &&
    ((state.yourSeat === "white" && piece.startsWith("w")) ||
      (state.yourSeat === "black" && piece.startsWith("b")));

  if (!state.yourSeat || state.yourSeat !== state.activeSeat) {
    return;
  }

  if (state.selectedDrop) {
    if (!piece) {
      const targets = state.legalDrops[state.selectedDrop] || [];
      const isLegal = targets.some((dest) => dest.row === row && dest.col === col);
      if (isLegal) {
        socket.emit("move", { board: boardId, drop: { piece: state.selectedDrop }, to: { row, col } });
      }
      state.selectedDrop = null;
      clearMoveDots(boardId);
    } else if (isOwnPiece) {
      state.selectedDrop = null;
      clearMoveDots(boardId);
    }
    return;
  }

  if (!state.selected) {
    if (!isOwnPiece) return;
    state.selectedDrop = null;
    state.selected = { row, col };
    square.classList.add("selected");
    showLegalMoves(boardId, state.selected);
    return;
  }

  if (state.selected.row === row && state.selected.col === col) {
    clearSelection(boardId);
    return;
  }

  if (isOwnPiece) {
    clearSelection(boardId);
    state.selectedDrop = null;
    state.selected = { row, col };
    square.classList.add("selected");
    showLegalMoves(boardId, state.selected);
    return;
  }

  const from = state.selected;
  const key = `${from.row},${from.col}`;
  const destinations = state.legalMovesMap[key] || [];
  const isLegal = destinations.some((dest) => dest.row === row && dest.col === col);
  if (isLegal) {
    socket.emit("move", { board: boardId, from, to: { row, col } });
  }
  clearSelection(boardId);
}

function onCapturePieceClick(event) {
  const img = event.currentTarget;
  const boardId = Number(img.dataset.board);
  const seat = img.dataset.seat;
  const piece = img.dataset.piece;
  const state = boards[boardId];
  if (!state || state.yourSeat !== seat || state.activeSeat !== seat) {
    return;
  }
  const targets = state.legalDrops[piece] || [];
  if (!targets.length) {
    return;
  }
  if (state.selectedDrop === piece) {
    state.selectedDrop = null;
    clearMoveDots(boardId);
  } else {
    state.selectedDrop = piece;
    clearSelection(boardId);
  }
  updateCrossBoardCaptures(lastGames);
  if (state.selectedDrop) {
    showDropMoves(boardId);
  }
}

socket.on("room_state", (data) => {
  const games = data.games || {};
  const yourSeats = data.your_seats || {};
  const legalMoves = data.legal_moves || {};
  const legalDrops = data.legal_drops || {};
  const bottomSeats = data.bottom_seats || {};
  const lastGamesList = data.last_games || [];
  lastGames = games;

  Object.entries(games).forEach(([boardIdStr, game]) => {
    const boardId = Number(boardIdStr);
    const state = boards[boardId];
    if (!state || !game) return;
    const winnerTeam = Array.isArray(lastGamesList) && lastGamesList.length
      ? lastGamesList[0].winner_team
      : null;

    state.yourSeat = yourSeats[boardIdStr] || null;
    const nextBottomSeat = bottomSeats[boardIdStr] || (boardId === 1 ? "white" : "black");
    const orientationChanged = nextBottomSeat !== state.lastBottomSeat;
    state.bottomSeat = nextBottomSeat;
    state.lastBottomSeat = nextBottomSeat;
    if (state.gameEl) {
      state.gameEl.classList.toggle("flipped", state.bottomSeat !== state.baseBottomSeat);
      state.gameEl.classList.toggle(
        "result-blue",
        Boolean(game.game_over && winnerTeam === "blue"),
      );
      state.gameEl.classList.toggle(
        "result-red",
        Boolean(game.game_over && winnerTeam === "red"),
      );
    }
    state.activeSeat = game.active_turn || null;
    state.lastMove = game.last_move || null;
    state.legalMovesMap = buildLegalMovesMap(legalMoves[boardIdStr] || []);
    state.legalDrops = legalDrops[boardIdStr] || {};

    const seatTeams = game.seat_teams || {};
    updateSeat(state, game.seat_names.white || "", "white", seatTeams.white);
    updateSeat(state, game.seat_names.black || "", "black", seatTeams.black);
    updatePromotion(state, game.promotion_choice.white, "white");
    updatePromotion(state, game.promotion_choice.black, "black");

    state.timerWhiteEl.textContent = formatTime(game.timers.white);
    state.timerBlackEl.textContent = formatTime(game.timers.black);
    state.timerBoxWhiteEl.classList.toggle("active", game.active_turn === "white");
    state.timerBoxBlackEl.classList.toggle("active", game.active_turn === "black");
    state.timerBoxWhiteEl.classList.toggle("low-time", game.timers.white < 15);
    state.timerBoxBlackEl.classList.toggle("low-time", game.timers.black < 15);

    if (!state.yourSeat || state.yourSeat !== state.activeSeat) {
      clearSelection(boardId);
      state.selectedDrop = null;
    }

    if (game.board) {
      const nextBoard = JSON.stringify(game.board);
      const nextMoveKey = JSON.stringify(state.lastMove);
      if (
        nextBoard !== state.lastBoard ||
        nextMoveKey !== state.lastMoveKey ||
        orientationChanged
      ) {
        state.lastBoard = nextBoard;
        state.lastMoveKey = nextMoveKey;
        state.currentBoard = game.board;
        renderBoard(boardId, game.board);
      } else {
        state.currentBoard = game.board;
      }
    }
  });

  const hasSeat = Object.values(boards).some((board) => board.yourSeat);
  chatInput.classList.toggle("hidden", !hasSeat);
  chatInput.disabled = !hasSeat;

  updateCrossBoardCaptures(games);
  renderLastGames(lastGamesList);
});

socket.on("move", (data) => {
  if (!data.from || !data.to) return;
  let sound = data.capture ? captureSound : moveSound;
  if (data.castle) sound = castleSound;
  if (data.promotion) sound = promoteSound;
  if (data.check) sound = checkSound;
  try {
    sound.currentTime = 0;
    sound.play();
  } catch (error) {
    // .
  }
});

socket.on("feed", (data) => {
  if (data.kind === "move" && data.username && data.team && data.move) {
    const entry = document.createElement("div");
    entry.className = "log-entry";
    const name = document.createElement("span");
    name.className = teamClass(data.team);
    name.textContent = `${data.username}: `;
    entry.appendChild(name);
    const boardLabel = data.board ? ` (Board ${data.board})` : "";
    entry.appendChild(document.createTextNode(`${data.move}${boardLabel}`));
    log.prepend(entry);
    return;
  }
  if (data.kind === "seat" && data.username && data.team && data.seat) {
    const entry = document.createElement("div");
    entry.className = "log-entry";
    const name = document.createElement("span");
    name.className = teamClass(data.team);
    name.textContent = data.username;
    entry.appendChild(name);
    const seatLabel = data.seat.charAt(0).toUpperCase() + data.seat.slice(1);
    const boardLabel = data.board ? `Board ${data.board}` : "Board";
    entry.appendChild(document.createTextNode(` has joined as ${boardLabel} ${seatLabel}.`));
    log.prepend(entry);
    try {
      notifySound.currentTime = 0;
      notifySound.play();
    } catch (error) {
      // .
    }
    return;
  }
  if (data.kind === "left" && data.username && data.team && data.seat) {
    const entry = document.createElement("div");
    entry.className = "log-entry";
    const name = document.createElement("span");
    name.className = teamClass(data.team);
    name.textContent = data.username;
    entry.appendChild(name);
    entry.appendChild(document.createTextNode(" has left."));
    log.prepend(entry);
    return;
  }
  if (data.kind === "result" && data.result_type && data.board) {
    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.appendChild(document.createTextNode(`${data.result_type} in Board ${data.board}. `));
    if (data.team) {
      const teamSpan = document.createElement("span");
      teamSpan.className = teamClass(data.team);
      teamSpan.textContent = teamLabel(data.team);
      entry.appendChild(teamSpan);
      const names = Array.isArray(data.winner_names) ? data.winner_names : [];
      const namesSuffix = names.length ? ` (${names.join(", ")})` : "";
      entry.appendChild(document.createTextNode(` wins${namesSuffix}. `));
    }
    entry.appendChild(document.createTextNode("Game resets in 30 seconds."));
    log.prepend(entry);
    try {
      gameEndSound.currentTime = 0;
      gameEndSound.play();
    } catch (error) {
      // .
    }
    return;
  }
  if (data.kind === "start" && data.message) {
    addLog(data.message);
    return;
  }
  if (data.message) addLog(data.message);
});

socket.on("game_start", () => {
  try {
    gameStartSound.currentTime = 0;
    gameStartSound.play();
  } catch (error) {
    // .
  }
});

socket.on("chat", (data) => {
  if (!data.username || !data.message) return;
  addChatMessage(data.username, data.message, data.team);
});

function buildLegalMovesMap(moves) {
  const map = {};
  moves.forEach((move) => {
    if (!move.from || !move.to) return;
    const key = `${move.from.row},${move.from.col}`;
    if (!map[key]) map[key] = [];
    map[key].push(move.to);
  });
  return map;
}

function updateSeat(state, username, seat, team) {
  const inputEl = seat === "white" ? state.nameWhiteEl : state.nameBlackEl;
  const displayEl = seat === "white" ? state.displayWhiteEl : state.displayBlackEl;
  const button = document.querySelector(`.seat-btn[data-seat="${seat}"][data-board="${state.boardId}"]`);
  displayEl.classList.remove("team-blue", "team-red");
  const isOtherSeat = state.yourSeat && state.yourSeat !== seat;
  const hasSeatOnAnyBoard =
    Object.values(boards).some((board) => board.yourSeat);
  if (username) {
    displayEl.textContent = username;
    displayEl.classList.remove("hidden");
    inputEl.classList.add("hidden");
    displayEl.classList.add(teamClass(team || teamFor(state.boardId, seat)));
    if (state.yourSeat === seat) {
      button.textContent = "Leave";
      button.classList.remove("hidden");
      button.disabled = false;
      inputEl.disabled = false;
    } else {
      button.classList.add("hidden");
    }
  } else {
    if (inputEl.classList.contains("hidden")) {
      inputEl.value = "";
    }
    inputEl.classList.remove("hidden");
    displayEl.classList.add("hidden");
    button.textContent = "Join";
    if (isOtherSeat || hasSeatOnAnyBoard) {
      button.classList.add("hidden");
      inputEl.disabled = true;
    } else {
      button.classList.remove("hidden");
      inputEl.disabled = false;
      button.disabled = !isValidUsername(inputEl.value.trim());
    }
  }
}

function isValidUsername(username) {
  return USERNAME_RE.test(username);
}

function updateJoinButtonState(inputEl, buttonEl) {
  if (!buttonEl || buttonEl.classList.contains("hidden")) return;
  buttonEl.disabled = !isValidUsername(inputEl.value.trim());
}

function updatePromotion(state, choice, seat) {
  const selectEl = seat === "white" ? state.promoWhiteEl : state.promoBlackEl;
  const wrapEl = seat === "white" ? state.promoWrapWhiteEl : state.promoWrapBlackEl;
  if (choice) {
    selectEl.value = choice;
  }
  if (state.yourSeat === seat) {
    wrapEl.classList.remove("hidden");
  } else {
    wrapEl.classList.add("hidden");
  }
}

seatButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const seat = btn.dataset.seat;
    const boardId = Number(btn.dataset.board);
    const state = boards[boardId];
    const input = seat === "white" ? state.nameWhiteEl : state.nameBlackEl;
    if (input.classList.contains("hidden")) {
      socket.emit("leave_seat", { board: boardId });
      return;
    }
    const username = input.value.trim();
    if (!isValidUsername(username)) return;
    socket.emit("seat_request", { board: boardId, seat, username });
  });
});

Object.values(boards).forEach((state) => {
  const pairs = [
    [state.nameWhiteEl, document.querySelector(`.seat-btn[data-seat="white"][data-board="${state.boardId}"]`)],
    [state.nameBlackEl, document.querySelector(`.seat-btn[data-seat="black"][data-board="${state.boardId}"]`)],
  ];
  pairs.forEach(([inputEl, buttonEl]) => {
    inputEl.addEventListener("input", () => updateJoinButtonState(inputEl, buttonEl));
    updateJoinButtonState(inputEl, buttonEl);
  });
});

promoSelects.forEach((select) => {
  select.addEventListener("change", () => {
    const boardId = Number(select.dataset.board);
    socket.emit("promotion_select", { board: boardId, choice: select.value });
  });
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  socket.emit("chat_message", { message });
  chatInput.value = "";
});
