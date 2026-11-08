import hashlib
import re
import secrets
import unicodedata

from desktop_app.connectors.connector import Connector
from desktop_app.models.user import User

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 64
MAX_NAME_LENGTH = 60
MAX_USERNAME_LENGTH = 30
MAX_EMAIL_LENGTH = 100
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.]{3,30}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_PUNCTUATION = set(" .'-")


def nameError(name):
    """Error message for a person's name, or None. Letters (Vietnamese too), spaces and . ' - only."""
    name = unicodedata.normalize("NFC", name.strip())
    if not name:
        return "Please enter your full name."
    if len(name) > MAX_NAME_LENGTH:
        return f"Full name must be at most {MAX_NAME_LENGTH} characters."
    if not any(ch.isalpha() for ch in name) or any(not (ch.isalpha() or ch in NAME_PUNCTUATION) for ch in name):
        return "Full name may only contain letters, spaces and . ' - (no numbers or symbols)."
    return None


def passwordError(pwd):
    """Error message for a new password, or None: 8-64 characters with at least one letter and one digit."""
    if len(pwd) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(pwd) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if not (re.search(r"[A-Za-z]", pwd) and re.search(r"\d", pwd)):
        return "Password must contain both letters and numbers."
    return None


class UserDao:
    @staticmethod
    def hashPassword(pwd, salt=None):
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
        return f"{salt}${digest}"

    @staticmethod
    def checkPassword(pwd, stored):
        salt, _ = stored.split("$", 1)
        return secrets.compare_digest(UserDao.hashPassword(pwd, salt), stored)

    @staticmethod
    def rowToUser(row):
        return User(id=int(row["id"]), username=row["username"], password=row["password"],
                    full_name=row["full_name"], email=row["email"], is_banned=int(row["is_banned"]),
                    role=row["role"], created_at=row["created_at"])

    @staticmethod
    def getUser(username):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select * from users where username=?", (username.strip(),))
        conn.disConnect()
        if df is None or len(df) == 0:
            return None
        return UserDao.rowToUser(df.iloc[0])

    @staticmethod
    def emailTaken(email):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select id from users where lower(email)=lower(?)", (email.strip(),))
        conn.disConnect()
        return df is not None and len(df) > 0

    @staticmethod
    def login(uid, pwd):
        """Return the User when username + password are correct, otherwise None (login failed)."""
        us = UserDao.getUser(uid)
        if us is None or not UserDao.checkPassword(pwd, us.password):
            return None
        return us

    @staticmethod
    def validateRegister(full_name, username, email, pwd, confirm):
        """List of error messages (empty list = valid)."""
        errors = []
        if error := nameError(full_name):
            errors.append(error)
        if not USERNAME_PATTERN.match(username.strip()):
            errors.append("Username must be 3-30 characters: letters, numbers, '_' or '.'.")
        if email.strip() and (len(email.strip()) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.match(email.strip())):
            errors.append("Please enter a valid email address.")
        if error := passwordError(pwd):
            errors.append(error)
        elif pwd != confirm:
            errors.append("Passwords do not match.")
        if not errors and UserDao.getUser(username) is not None:
            errors.append("This username is already taken.")
        if not errors and email.strip() and UserDao.emailTaken(email):
            errors.append("This email is already used by another account.")
        return errors

    @staticmethod
    def register(full_name, username, email, pwd):
        """Insert a new user and return it (None if the insert failed)."""
        sql = "insert into users(username, password, full_name, email) values (?, ?, ?, ?)"
        val = (username.strip(), UserDao.hashPassword(pwd), unicodedata.normalize("NFC", full_name.strip()), email.strip() or None)
        conn = Connector()
        conn.connect()
        new_id = conn.executeNonQuery(sql, val)
        conn.disConnect()
        return None if new_id is None else UserDao.getUser(username)
