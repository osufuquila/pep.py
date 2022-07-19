from __future__ import annotations

import bcrypt
from common.constants import privileges

from objects import glob


def username_safe(s: str) -> str:
    """Returns safe to use username."""

    return s.lower().strip().replace(" ", "_")


def verify_password(user_id: int, password: str) -> bool:
    """Verifies if the provided username + password combination is correct,
    providing a cache to ensure speed with bcrypt.

    Note:
        This only supports Ripple Password v2 (MD5 + BCrypt) as no one in
            their right mind should be using v1.

    Args:
        user_id (int): The ID of the user within the database.
        password (str): The user's password hashed with MD5.
    """

    # Check if we already cached them, for speed benefit.
    passw = glob.cached_passwords.get(user_id)
    if passw:
        return password == passw

    # Nope. Sad. Bcrypt time.
    passw_db = glob.db.fetch(
        "SELECT password_md5 FROM users WHERE id = %s LIMIT 1",
        (user_id,),
    )["password_md5"]

    res = bcrypt.checkpw(password.encode(), passw_db.encode())
    # Cache it for later
    if res:
        glob.cached_passwords[user_id] = password
    return res


def get_country(user_id: int) -> str:
    """Returns the country of the user.

    Args:
        user_id (int): The ID of the user within the database.
    """

    return glob.db.fetch(
        "SELECT country FROM users WHERE id = %s LIMIT 1",
        (user_id,),
    )["country"]


def set_country(user_id: int, country_code: str) -> None:
    """Sets the country for a specific user to `country_code`.

    Args:
        user_id (int): The user ID for the user.
        country_code (str): The 2 letter country code to set.
    """

    country_code = country_code.upper()

    glob.db.execute(
        "UPDATE users SET country = %s WHERE id = %s LIMIT 1",
        (country_code, user_id),
    )


def insert_ban_log(
    user_id: int,
    summary: str,
    detail: str,
    prefix: bool = True,
    from_id: int = 999,  # TODO: Don't hardcode the bot id.
) -> None:
    """Inserts a ban log for a user into the database.

    Args:
        user_id (int): The ID of the user to assign the log to.
        summary (str): A short description of the reason.
        detail (str): A more detailed, in-depth description of the reason.
        prefix (bool, optional): Whether the detail should be prefixed by
            the peppy signature. Defaults to True.
        from_id (int, optional): The ID of the user who banned the user.
            Defaults to 999 (the bot).
    """

    if prefix:
        detail = "pep.py Autoban: " + detail

    glob.db.execute(
        "INSERT INTO ban_logs (from_id, to_id, summary, detail) VALUES (%s, %s, %s, %s)",
        (
            from_id,
            user_id,
            summary,
            detail,
        ),
    )


def restrict_with_log(
    user_id: int,
    summary: str,
    detail: str,
    prefix: bool = True,
    from_id: int = 999,
) -> None:
    """Restricts the user alongside inserting a log into the database.

    Args:
        user_id (int): The ID of the user to assign the log to.
        summary (str): A short description of the reason.
        detail (str): A more detailed, in-depth description of the reason.
        prefix (bool, optional): Whether the detail should be prefixed by
            the peppy signature. Defaults to True.
        from_id (int, optional): The ID of the user who banned the user.
            Defaults to 999 (the bot).
    """

    glob.db.execute(
        f"UPDATE users SET privileges = privileges & ~{privileges.USER_PUBLIC} WHERE id = %s LIMIT 1",
        (user_id,),
    )

    insert_ban_log(user_id, summary, detail, prefix, from_id)
