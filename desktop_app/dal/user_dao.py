import hashlib
import re
import secrets

from desktop_app.connectors.connector import Connector
from desktop_app.models.user import User

MIN_PASSWORD_LENGTH = 6
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.]{3,30}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
        if not full_name.strip():
            errors.append("Please enter your full name.")
        if not USERNAME_PATTERN.match(username.strip()):
            errors.append("Username must be 3-30 characters: letters, numbers, '_' or '.'.")
        if email.strip() and not EMAIL_PATTERN.match(email.strip()):
            errors.append("Please enter a valid email address.")
        if len(pwd) < MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        elif pwd != confirm:
            errors.append("Passwords do not match.")
        if not errors and UserDao.getUser(username) is not None:
            errors.append("This username is already taken.")
        return errors

    @staticmethod
    def register(full_name, username, email, pwd):
        """Insert a new user and return it (None if the insert failed)."""
        sql = "insert into users(username, password, full_name, email) values (?, ?, ?, ?)"
        val = (username.strip(), UserDao.hashPassword(pwd), full_name.strip(), email.strip() or None)
        conn = Connector()
        conn.connect()
        new_id = conn.executeNonQuery(sql, val)
        conn.disConnect()
        return None if new_id is None else UserDao.getUser(username)
