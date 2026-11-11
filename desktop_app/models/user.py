ROLE_USER, ROLE_ADMIN = "user", "admin"


class User:
    def __init__(self, id=None, username=None, password=None, full_name=None, email=None, is_banned=None,
                 role=None, created_at=None, failed_count=0, locked_until=None, last_login_at=None,
                 updated_at=None):
        self.id = id
        self.username = username
        self.password = password
        self.full_name = full_name
        self.email = email
        self.is_banned = is_banned
        self.role = role
        self.created_at = created_at
        self.failed_count = failed_count
        self.locked_until = locked_until
        self.last_login_at = last_login_at
        self.updated_at = updated_at

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def display_name(self):
        """First word of the full name, e.g. 'Huyen Nguyen' -> 'Huyen'."""
        name = (self.full_name or self.username or "").strip()
        return name.split()[0] if name else ""

    def __str__(self):
        return f"{self.id}\t{self.username}\t{self.full_name}\t{self.role}"
