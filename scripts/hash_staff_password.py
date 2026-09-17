#!/usr/bin/env python3
import getpass
import sys

from werkzeug.security import generate_password_hash

password = getpass.getpass("Staff password: ")
if not password.strip():
    sys.exit("Password required")
print(generate_password_hash(password))
