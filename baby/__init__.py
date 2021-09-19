from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_socketio import SocketIO
import string

chars = string.ascii_lowercase + string.digits + string.ascii_uppercase

app = Flask(__name__)
app.config["SECRET_KEY"] = "3a1b4c1d5e9f"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
sio = SocketIO(app)

from baby import routes
