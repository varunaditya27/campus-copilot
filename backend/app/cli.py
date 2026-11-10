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


def _create_admin_key(args: argparse.Namespace) -> int:
    from app.security import api_keys

    key, digest = api_keys.generate_key()
    print("API key (shown once, keep it secret; send it as the X-Admin-Key header):")
    print(f"  {key}")
    print("\nAdd its digest to the server's ADMIN_API_KEY_HASHES (comma-separated for several keys), then restart:")
    print(f"  {digest}")
    return 0


def _create_vapid_keys(args: argparse.Namespace) -> int:
    import base64

    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid

    def encode(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    pair = Vapid()
    pair.generate_keys()
    private = encode(pair.private_key.private_numbers().private_value.to_bytes(32, "big"))
    public = encode(pair.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    print("Add these to the server's settings. Keep the private key secret, and set VAPID_SUBJECT to a contact such as mailto:admin@college.edu.")
    print(f"VAPID_PUBLIC_KEY={public}")
    print(f"VAPID_PRIVATE_KEY={private}")
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

    key = commands.add_parser("create-admin-key", help="make an API key for scripts to call the admin endpoints")
    key.set_defaults(run=_create_admin_key)

    vapid = commands.add_parser("create-vapid-keys", help="make the key pair that web push notifications are signed with")
    vapid.set_defaults(run=_create_vapid_keys)

    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
