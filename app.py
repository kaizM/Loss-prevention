import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database - using SQLite for local storage
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///loss_prevention.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["CLIPS_FOLDER"] = "clips"
app.config["VIDEO_SOURCE_FOLDER"] = "video_source"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

# Initialize the app with the extension
db.init_app(app)

# Create upload directories if they don't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["CLIPS_FOLDER"], exist_ok=True)
os.makedirs(app.config["VIDEO_SOURCE_FOLDER"], exist_ok=True)

with app.app_context():
    # Import models to create tables
    import models
    db.create_all()

# Import routes
import routes
