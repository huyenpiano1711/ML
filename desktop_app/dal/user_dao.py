"""
user_dao.py - Accounts: register, sign in (with lock after wrong passwords), profile, password, admin actions.

Rules (same spirit as the course exam: 3 wrong passwords -> stop):
    - password stored as salt$PBKDF2-HMAC-SHA256 (120.000 rounds), never plain text
    - 3 wrong passwords in a row on one account -> the account is locked for 5 minutes (saved in the database,
      so restarting the app does not unlock it); LoginMainWindowEx also closes the app after 3 failed tries
    - a banned account (locked by an admin) cannot sign in
    - every attempt is written to login_history
    - there is always at least one admin; an admin cannot ban, demote or delete himself
"""
import hashlib
import re
import secrets
import string
import unicodedata
from datetime import datetime, timedelta

from desktop_app.connectors.connector import Connector
from desktop_app.models.user import ROLE_ADMIN, ROLE_USER, User

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 64
MAX_NAME_LENGTH = 60
MAX_USERNAME_LENGTH = 30
MAX_EMAIL_LENGTH = 100
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.]{3,30}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_PUNCTUATION = set(" .'-")

MAX_FAILED_LOGINS = 3            # wrong passwords in a row before the account is locked
LOCK_MINUTES = 5
DEFAULT_ADMIN = ("admin", "Admin@2026", "AutoWise Administrator")
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Results of UserDao.authenticate()
AUTH_OK, AUTH_WRONG, AUTH_LOCKED, AUTH_BANNED, AUTH_EMPTY = "ok", "wrong", "locked", "banned", "empty"


def now():
    return datetime.now().strftime(TIME_FORMAT)


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


def passwordError(pwd, username=""):
    """Error message for a new password, or None: 8-64 characters with at least one letter and one digit,
    no spaces, and not containing the username."""
    if len(pwd) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(pwd) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    if not (re.search(r"[A-Za-z]", pwd) and re.search(r"\d", pwd)):
        return "Password must contain both letters and numbers."
    if re.search(r"\s", pwd):
        return "Password must not contain spaces."
    if username and len(username.strip()) >= 3 and username.strip().lower() in pwd.lower():
        return "Password must not contain your username."
    return None


def emailError(email):
    email = email.strip()
    if email and (len(email) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.match(email)):
        return "Please enter a valid email address."
    return None


class AuthResult:
    def __init__(self, status, user=None, message="", minutes=0):
        self.status = status
        self.user = user
        self.message = message
        self.minutes = minutes

    @property
    def ok(self):
        return self.status == AUTH_OK


class UserDao:
    # ------------------------------------------------------------------ helpers
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
        get = row.get if hasattr(row, "get") else (lambda k, d=None: row[k] if k in row else d)
        return User(id=int(row["id"]), username=row["username"], password=row["password"],
                    full_name=row["full_name"], email=row["email"], is_banned=int(row["is_banned"]),
                    role=row["role"], created_at=row["created_at"], failed_count=int(get("failed_count", 0) or 0),
                    locked_until=get("locked_until"), last_login_at=get("last_login_at"),
                    updated_at=get("updated_at"))

    @staticmethod
    def query(sql, val=None):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset(sql, val)
        conn.disConnect()
        return df

    @staticmethod
    def execute(sql, val=None):
        conn = Connector()
        conn.connect()
        result = conn.executeNonQuery(sql, val)
        conn.disConnect()
        return result

    # ------------------------------------------------------------------ read
    @staticmethod
    def getUser(username):
        df = UserDao.query("select * from users where username=?", (username.strip(),))
        if df is None or len(df) == 0:
            return None
        return UserDao.rowToUser(df.iloc[0])

    @staticmethod
    def getUserById(user_id):
        df = UserDao.query("select * from users where id=?", (int(user_id),))
        if df is None or len(df) == 0:
            return None
        return UserDao.rowToUser(df.iloc[0])

    @staticmethod
    def emailTaken(email, except_id=None):
        df = UserDao.query("select id from users where lower(email)=lower(?) and id<>?", (email.strip(), except_id or -1))
        return df is not None and len(df) > 0

    @staticmethod
    def countAdmins():
        df = UserDao.query("select count(*) n from users where role='admin' and is_banned=0")
        return int(df.iloc[0]["n"]) if df is not None else 0

    # ------------------------------------------------------------------ sign in
    @staticmethod
    def login(uid, pwd):
        """Return the User when username + password are correct, otherwise None (no lock counting).
        Kept for the simple test scripts; the window uses authenticate()."""
        us = UserDao.getUser(uid)
        if us is None or not UserDao.checkPassword(pwd, us.password):
            return None
        return us

    @staticmethod
    def lockedMinutes(us):
        """Minutes left while the account is locked after wrong passwords, else 0."""
        if not us or not us.locked_until:
            return 0
        until = datetime.strptime(us.locked_until, TIME_FORMAT)
        left = (until - datetime.now()).total_seconds()
        return int(-(-left // 60)) if left > 0 else 0

    @staticmethod
    def recordAttempt(username, user_id, success, reason):
        UserDao.execute("insert into login_history(user_id, username, success, reason) values (?, ?, ?, ?)",
                        (user_id, username.strip()[:MAX_USERNAME_LENGTH], int(success), reason))

    @staticmethod
    def authenticate(uid, pwd):
        """Check a sign-in and apply the lock rules. Returns AuthResult(status, user, message)."""
        uid = uid.strip()
        if not uid or not pwd:
            return AuthResult(AUTH_EMPTY, message="Please enter your username and password.")
        us = UserDao.getUser(uid)
        if us is None:
            UserDao.recordAttempt(uid, None, False, "unknown_user")
            return AuthResult(AUTH_WRONG, message="Incorrect username or password.")
        if minutes := UserDao.lockedMinutes(us):
            UserDao.recordAttempt(uid, us.id, False, "locked")
            return AuthResult(AUTH_LOCKED, us, f"Too many wrong passwords. This account is locked, please try "
                                                f"again in {minutes} minute{'s' if minutes > 1 else ''}.", minutes)
        if not UserDao.checkPassword(pwd, us.password):
            failed = us.failed_count + 1
            if failed >= MAX_FAILED_LOGINS:
                until = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).strftime(TIME_FORMAT)
                UserDao.execute("update users set failed_count=0, locked_until=? where id=?", (until, us.id))
                UserDao.recordAttempt(uid, us.id, False, "wrong_password_locked")
                return AuthResult(AUTH_LOCKED, us, f"{MAX_FAILED_LOGINS} wrong passwords in a row. This account is "
                                                    f"locked for {LOCK_MINUTES} minutes.", LOCK_MINUTES)
            UserDao.execute("update users set failed_count=? where id=?", (failed, us.id))
            UserDao.recordAttempt(uid, us.id, False, "wrong_password")
            left = MAX_FAILED_LOGINS - failed
            return AuthResult(AUTH_WRONG, us, f"Incorrect username or password. {left} attempt{'s' if left > 1 else ''} "
                                              "left before this account is locked.")
        if us.is_banned:
            UserDao.recordAttempt(uid, us.id, False, "banned")
            return AuthResult(AUTH_BANNED, us, "This account has been locked by an administrator.")
        UserDao.execute("update users set failed_count=0, locked_until=null, last_login_at=? where id=?", (now(), us.id))
        UserDao.recordAttempt(uid, us.id, True, "ok")
        return AuthResult(AUTH_OK, UserDao.getUserById(us.id))

    # ------------------------------------------------------------------ register
    @staticmethod
    def validateRegister(full_name, username, email, pwd, confirm):
        """List of error messages (empty list = valid)."""
        errors = []
        if error := nameError(full_name):
            errors.append(error)
        if not USERNAME_PATTERN.match(username.strip()):
            errors.append("Username must be 3-30 characters: letters, numbers, '_' or '.'.")
        if error := emailError(email):
            errors.append(error)
        if error := passwordError(pwd, username):
            errors.append(error)
        elif pwd != confirm:
            errors.append("Passwords do not match.")
        if not errors and UserDao.getUser(username) is not None:
            errors.append("This username is already taken.")
        if not errors and email.strip() and UserDao.emailTaken(email):
            errors.append("This email is already used by another account.")
        return errors

    @staticmethod
    def register(full_name, username, email, pwd, role=ROLE_USER):
        """Insert a new user and return it (None if the insert failed)."""
        sql = "insert into users(username, password, full_name, email, role) values (?, ?, ?, ?, ?)"
        val = (username.strip(), UserDao.hashPassword(pwd), unicodedata.normalize("NFC", full_name.strip()),
               email.strip() or None, role)
        new_id = UserDao.execute(sql, val)
        return None if new_id is None else UserDao.getUser(username)

    @staticmethod
    def ensureDefaultAdmin():
        """First run: create the default admin account when the database has no admin. Returns it or None."""
        if UserDao.countAdmins() > 0:
            return None
        username, pwd, name = DEFAULT_ADMIN
        if UserDao.getUser(username) is not None:
            UserDao.execute("update users set role='admin', is_banned=0 where username=?", (username,))
            return UserDao.getUser(username)
        return UserDao.register(name, username, "", pwd, role=ROLE_ADMIN)

    # ------------------------------------------------------------------ profile
    @staticmethod
    def updateProfile(user_id, full_name, email):
        errors = [e for e in (nameError(full_name), emailError(email)) if e]
        if not errors and email.strip() and UserDao.emailTaken(email, except_id=user_id):
            errors.append("This email is already used by another account.")
        if errors:
            return errors
        UserDao.execute("update users set full_name=?, email=?, updated_at=? where id=?",
                        (unicodedata.normalize("NFC", full_name.strip()), email.strip() or None, now(), user_id))
        return []

    @staticmethod
    def changePassword(user_id, old_pwd, new_pwd, confirm):
        us = UserDao.getUserById(user_id)
        if us is None or not UserDao.checkPassword(old_pwd, us.password):
            return ["Your current password is not correct."]
        if error := passwordError(new_pwd, us.username):
            return [error]
        if new_pwd != confirm:
            return ["New passwords do not match."]
        if old_pwd == new_pwd:
            return ["The new password must be different from the current one."]
        UserDao.execute("update users set password=?, updated_at=? where id=?",
                        (UserDao.hashPassword(new_pwd), now(), user_id))
        return []

    # ------------------------------------------------------------------ admin
    @staticmethod
    def listUsers(keyword="", role="", status=""):
        """Users with their number of analyses, for the admin table. status: '', 'active', 'banned', 'locked'."""
        sql = """select u.id, u.username, u.full_name, u.email, u.role, u.is_banned, u.locked_until,
                        u.created_at, u.last_login_at,
                        (select count(*) from searches s where s.user_id = u.id) as n_searches
                 from users u where 1=1"""
        val = []
        if keyword.strip():
            sql += " and (u.username like ? or u.full_name like ? or ifnull(u.email,'') like ?)"
            val += [f"%{keyword.strip()}%"] * 3
        if role:
            sql += " and u.role=?"
            val.append(role)
        if status == "banned":
            sql += " and u.is_banned=1"
        elif status == "active":
            sql += " and u.is_banned=0"
        elif status == "locked":
            sql += " and u.locked_until > ?"
            val.append(now())
        return UserDao.query(sql + " order by u.id", tuple(val))

    @staticmethod
    def adminGuard(admin, target_id, action):
        """Error message when an admin action is not allowed, else None."""
        if admin is not None and admin.id == int(target_id) and action in ("ban", "demote", "delete"):
            return "You cannot do this to your own account."
        target = UserDao.getUserById(target_id)
        if target is None:
            return "This account no longer exists."
        if target.is_admin and action in ("ban", "demote", "delete") and UserDao.countAdmins() <= 1:
            return "There must always be at least one active admin."
        return None

    @staticmethod
    def setBanned(admin, user_id, banned):
        if banned and (error := UserDao.adminGuard(admin, user_id, "ban")):
            return error
        UserDao.execute("update users set is_banned=?, failed_count=0, locked_until=null, updated_at=? where id=?",
                        (int(banned), now(), user_id))
        AuditDao.log(admin, "ban" if banned else "unban", user_id)
        return None

    @staticmethod
    def unlock(admin, user_id):
        UserDao.execute("update users set failed_count=0, locked_until=null where id=?", (user_id,))
        AuditDao.log(admin, "unlock", user_id)
        return None

    @staticmethod
    def setRole(admin, user_id, role):
        if role not in (ROLE_USER, ROLE_ADMIN):
            return "Unknown role."
        if role == ROLE_USER and (error := UserDao.adminGuard(admin, user_id, "demote")):
            return error
        UserDao.execute("update users set role=?, updated_at=? where id=?", (role, now(), user_id))
        AuditDao.log(admin, f"set_role:{role}", user_id)
        return None

    @staticmethod
    def resetPassword(admin, user_id):
        """Give the account a new random password (shown once to the admin). Returns (password, error)."""
        if UserDao.getUserById(user_id) is None:
            return None, "This account no longer exists."
        alphabet = string.ascii_letters + string.digits
        while True:
            pwd = "".join(secrets.choice(alphabet) for _ in range(10))
            if passwordError(pwd) is None:
                break
        UserDao.execute("update users set password=?, failed_count=0, locked_until=null, updated_at=? where id=?",
                        (UserDao.hashPassword(pwd), now(), user_id))
        AuditDao.log(admin, "reset_password", user_id)
        return pwd, None

    @staticmethod
    def deleteUser(admin, user_id):
        if error := UserDao.adminGuard(admin, user_id, "delete"):
            return error
        target = UserDao.getUserById(user_id)
        UserDao.execute("delete from users where id=?", (user_id,))
        AuditDao.log(admin, "delete_user", user_id, target.username if target else "")
        return None


class AuditDao:
    @staticmethod
    def log(admin, action, target=None, detail=""):
        UserDao.execute("insert into audit_log(admin_id, action, target, detail) values (?, ?, ?, ?)",
                        (getattr(admin, "id", None), action, None if target is None else str(target), detail))

    @staticmethod
    def recent(limit=200):
        return UserDao.query("""select a.created_at, ifnull(u.username, '(deleted)') as admin, a.action, a.target, a.detail
                                from audit_log a left join users u on u.id = a.admin_id
                                order by a.id desc limit ?""", (limit,))

    @staticmethod
    def loginHistory(limit=300):
        return UserDao.query("""select created_at, username, case success when 1 then 'success' else 'failed' end as result,
                                       reason from login_history order by id desc limit ?""", (limit,))
