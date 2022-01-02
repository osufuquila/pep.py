from objects import glob
import bcrypt

def username_safe(s: str):
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
    if passw: return password == passw

    # Nope. Sad. Bcrypt time.
    passw_db = glob.db.fetch(
        "SELECT password_md5 FROM users WHERE id = %s LIMIT 1", (user_id,)
    )["password_md5"]

    res = bcrypt.checkpw(password.encode(), passw_db.encode())
    # Cache it for later
    if res: glob.cached_passwords[user_id] = password
    return res