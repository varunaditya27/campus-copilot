"""Administration commands. Run from backend/ with: python -m app.cli <command>

There is no public sign-up for faculty, staff or admin accounts (anyone could
make themselves an admin), so they are created here by someone with access to
the server.
"""
import argparse
import getpass
import sys

from pydantic import ValidationError

from app.core.errors import AppError
from app.models.auth import NewStaffAccount
from app.services import auth_service


def _create_user(args: argparse.Namespace) -> int:
    # The password is prompted for, never taken as an argument, so it does not
    # end up in shell history or the process list.
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Repeat password: "):
        print("The passwords do not match.", file=sys.stderr)
        return 1
    try:
        account = NewStaffAccount(
            role=args.role,
            name=args.name,
            email=args.email,
            password=password,
            department=args.department,
            office=args.office,
            office_hours=args.office_hours,
        )
        user_id = auth_service.create_staff_account(account)
    except ValidationError as exc:
        for error in exc.errors():
            field = ".".join(str(part) for part in error["loc"]) or "account"
            print(f"{field}: {error['msg']}", file=sys.stderr)
        return 1
    except AppError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    print(f"Created {account.role} account for {account.email.lower()} (user id {user_id}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-user", help="create a faculty, staff or admin account")
    create.add_argument("--role", required=True, choices=["faculty", "staff", "admin"])
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--department", help="required for faculty")
    create.add_argument("--office")
    create.add_argument("--office-hours")
    create.set_defaults(run=_create_user)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
