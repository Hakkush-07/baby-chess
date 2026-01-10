import socketio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from baby.constants import ASSETS_DIR, FRONTEND_DIR
from baby.babychess import on_startup, set_sio
from baby.routes import register_routes
from baby.socket_handlers import register_socket_handlers

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
set_sio(sio)

app = FastAPI()
app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

register_routes(app)
register_socket_handlers(sio)

@app.on_event("startup")
async def app_startup():
    await on_startup()

socket_app = socketio.ASGIApp(sio, other_asgi_app=app, socketio_path="socket.io")
