import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from desktop_app.dal.user_dao import UserDao

print(UserDao.validateRegister("Test User", "testuser", "test@email.com", "autowise2021", "autowise2021"))
if UserDao.getUser("testuser") is None:
    UserDao.register("Test User", "testuser", "test@email.com", "autowise2021")
us = UserDao.login("testuser", "autowise2021")
print("Login success" if us else "Login failed", us.full_name if us else "")
print("Wrong password ->", UserDao.login("testuser", "wrong"))
