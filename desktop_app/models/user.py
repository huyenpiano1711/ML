class User:
    def __init__(self, id=None, username=None, password=None, full_name=None,
                 email=None, is_banned=None, role=None, created_at=None):
        self.id = id
        self.username = username
        self.password = password
        self.full_name = full_name
        self.email = email
        self.is_banned = is_banned
        self.role = role
        self.created_at = created_at

    @property
    def display_name(self):
        """First word of the full name, e.g. 'Huyen Nguyen' -> 'Huyen'."""
        name = (self.full_name or self.username or "").strip()
        return name.split()[0] if name else ""
