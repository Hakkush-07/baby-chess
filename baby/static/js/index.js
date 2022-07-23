function onDrop(source, target, piece, newPos, oldPos, orientation) {
    socket.emit("drop", {old: Chessboard.objToFen(oldPos), new: Chessboard.objToFen(newPos), source: source, target: target, piece: piece, orientation: orientation}, function(data) {
        board.position(data.fen)
        board.orientation(data.orientation)
    })
}

let config = {
    position: "start",
    orientation: "white",
    showNotation: false,
    draggable: true,
    sparePieces: true,
    onDrop: onDrop
}
let board = Chessboard("board", config)
let config_mini = {
    position: "start",
    orientation: "black",
    showNotation: false
}
let board_mini = Chessboard("board_mini", config_mini)

let socket = io()

socket.on("info", function(data) {
    let li = document.createElement("li")
    li.setAttribute("class", "system")
    let system = document.createElement("t")
    system.textContent = data
    system.setAttribute("class", "user-link")
    li.appendChild(system)
    let list = document.getElementById("messages")
    list.append(li)
})

socket.on("message", function(data) {
    let li = document.createElement("li")
    let author = document.createElement("span")
    author.textContent = data.author
    author.setAttribute("class", "user-link")
    li.appendChild(author)
    let message = document.createElement("span")
    message.textContent = data.message
    li.appendChild(message)
    let list = document.getElementById("messages")
    list.append(li)
})

socket.on("board", function() {
    socket.emit("get_board", "", function(data) {
        board.position(data.fen)
        board.orientation(data.orientation)
        board_mini.position(data.fen_mini)
        board_mini.orientation(data.orientation_mini)
        document.getElementById("pocket_above").textContent = data.pocket_above
        document.getElementById("pocket_below").textContent = data.pocket_below
    })
})

socket.on("table", function() {
    socket.emit("get_table", "", function(data) {
        document.getElementById("player_below").firstChild.data = data.player_below
        document.getElementById("player_above").firstChild.data = data.player_above
    })
})

socket.on("game_over", function() {
    console.log("game over")
})

function adjust_times(data) {
    let seperator_above = document.createElement("sep")
    seperator_above.append(":")
    let time_above = document.getElementById("time_above")
    time_above.textContent = ""
    time_above.append(("0" + Math.floor(data.time_above / 60)).slice(-2))
    time_above.appendChild(seperator_above)
    time_above.append(("0" + (data.time_above % 60)).slice(-2))
    time_above_parent = document.getElementById("time_above_parent")
    if (data.running_above) {
        time_above_parent.classList.add("running")
    }
    else {
        time_above_parent.classList.remove("running")
    }
    let seperator_below = document.createElement("sep")
    seperator_below.append(":")
    let time_below = document.getElementById("time_below")
    time_below.textContent = ""
    time_below.append(("0" + Math.floor(data.time_below / 60)).slice(-2))
    time_below.appendChild(seperator_below)
    time_below.append(("0" + (data.time_below % 60)).slice(-2))
    time_below_parent = document.getElementById("time_below_parent")
    if (data.running_below) {
        time_below_parent.classList.add("running")
    }
    else {
        time_below_parent.classList.remove("running")
    }
}

socket.on("times", function() {
    socket.emit("get_times", "", adjust_times)
})

socket.on("players", function(data) {
    document.getElementById("xw").firstChild.data  = data.xw
    document.getElementById("xb").firstChild.data  = data.xb
    document.getElementById("yw").firstChild.data  = data.yw
    document.getElementById("yb").firstChild.data  = data.yb
})

socket.on("game_status", function() {
    socket.emit("get_status", "", function(data) {
        let setup = document.createElement("div")
        setup.classList.add("setup")
        setup.append("3+2 Blitz")
        let status = document.getElementById("game_status")
        status.textContent = ""
        status.appendChild(setup)
        status.append(data)
    })
})

function send_msg() {
    let msg = document.getElementById("chat_send").value
    document.getElementById("chat_send").value = ""
    socket.emit("message", msg);
}

function join(role) {
    socket.emit("join", role)
}

setInterval(function() {
    socket.emit("time")
    socket.emit("get_times", "", adjust_times)
}, 100)
