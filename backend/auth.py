from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token
from passlib.hash import pbkdf2_sha256
import os
from datetime import timedelta

# Initialize SQLAlchemy
db = SQLAlchemy()


# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = pbkdf2_sha256.hash(password)

    def check_password(self, password):
        return pbkdf2_sha256.verify(password, self.password_hash)


# Initialize JWT manager
jwt = JWTManager()


def init_auth(app):
    """Initialize authentication components"""
    # Configure SQLAlchemy
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'users.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Configure JWT
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)

    # Create tables
    with app.app_context():
        db.create_all()


def authenticate_user(username, password):
    """Authenticate a user and return a JWT token"""
    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        # Create access token with username as identity
        access_token = create_access_token(identity=username)
        return access_token

    return None


def register_user(username, password):
    """Register a new user"""
    existing_user = User.query.filter_by(username=username).first()

    if existing_user:
        return False, "Username already exists"

    new_user = User(username=username)
    new_user.set_password(password)

    try:
        db.session.add(new_user)
        db.session.commit()
        return True, "User registered successfully"
    except Exception as e:
        db.session.rollback()
        return False, f"Registration failed: {str(e)}"
