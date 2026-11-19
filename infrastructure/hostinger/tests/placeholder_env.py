"""Prints an env file for `docker compose config`: the keys of .env.example with made-up values.

Used by CI:  python3 infrastructure/hostinger/tests/placeholder_env.py > "$env_file"
"""

from support import placeholder_env

if __name__ == "__main__":
    for name, value in placeholder_env().items():
        print(f"{name}={value}")
