from fastapi.responses import FileResponse, RedirectResponse
from baby.constants import FRONTEND_DIR
from baby.babychess import reset_all_games

def register_routes(app):
    @app.get("/")
    async def index():
        return FileResponse(f"{FRONTEND_DIR}/index.html")

    @app.get("/reset")
    async def reset_route():
        await reset_all_games()
        return RedirectResponse(url="/")
