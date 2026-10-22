"""Generate the ADMIN_PASSWORD_HASH value for your .env file."""
from getpass import getpass
from werkzeug.security import generate_password_hash

pw = getpass("Choose an admin password: ")
if len(pw) < 12:
    raise SystemExit("Use at least 12 characters.")
print("\nADMIN_PASSWORD_HASH='" + generate_password_hash(pw) + "'")
