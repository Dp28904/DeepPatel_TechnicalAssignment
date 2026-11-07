"""Command-line tools.

Create an account (the password is prompted for, never passed on the command line):

    python -m app.cli create-user --name "Asha Admin" --email asha@example.com --role ADMIN
"""

import argparse
import getpass
import sys

from pydantic import ValidationError

from app.core.database import SessionLocal
from app.core.enums import Role
from app.core.exceptions import AppError
from app.modules.users import service as user_service
from app.modules.users.schemas import UserCreate


def create_user_command(args: argparse.Namespace) -> int:
    password = getpass.getpass("Password (min 8 characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("Error: passwords do not match.", file=sys.stderr)
        return 1
    try:
        data = UserCreate(name=args.name, email=args.email, password=password, role=args.role)
    except ValidationError as exc:
        for err in exc.errors():
            field = ".".join(str(p) for p in err["loc"])
            print(f"Error: {field}: {err['msg']}", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        try:
            user = user_service.create_user(db, data)
        except AppError as exc:
            print(f"Error: {exc.message}", file=sys.stderr)
            return 1
    print(f"Created {user.role.value} user #{user.id}: {user.email}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-user", help="Create a login account")
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--role", required=True, choices=[r.value for r in Role])
    create.set_defaults(handler=create_user_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
