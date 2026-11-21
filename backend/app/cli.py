"""Command line helpers.

    python -m app.cli init                     # migrate DB + seed stores/admin/sample data
    python -m app.cli scrape all               # scrape every store now (no Celery needed)
    python -m app.cli scrape igeek --categories cpu,gpu
    python -m app.cli create-admin --email you@example.com --password secret123
    python -m app.cli rematch                  # redo cross-store matching after improving the rules
    python -m app.cli export-snapshot          # save current catalog as demo data
    python -m app.cli import-snapshot          # load demo data into an empty catalog
"""
import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from app.database import session_scope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="run migrations and seed the database")
    scrape = sub.add_parser("scrape", help="scrape a store (or 'all') right now")
    scrape.add_argument("store")
    scrape.add_argument("--categories", help="comma separated, e.g. cpu,gpu")
    admin = sub.add_parser("create-admin")
    admin.add_argument("--email", required=True)
    admin.add_argument("--password", required=True)
    admin.add_argument("--username", default="admin")
    sub.add_parser("rematch", help="re-run product matching on stored offers (no scraping)")
    exp = sub.add_parser("export-snapshot")
    exp.add_argument("path", nargs="?")
    imp = sub.add_parser("import-snapshot")
    imp.add_argument("path", nargs="?")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.cmd == "init":
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
        from app.seed import seed

        with session_scope() as db:
            print(json.dumps(seed(db), indent=2))
    elif args.cmd == "scrape":
        from app.scraping.registry import SCRAPERS
        from app.scraping.runner import run_scrape
        from app.services.email import send_notification_email

        def send_inline(ids: list[int]) -> None:
            with session_scope() as db:
                for note_id in ids:
                    send_notification_email(db, note_id)

        slugs = list(SCRAPERS) if args.store == "all" else [args.store]
        cats = args.categories.split(",") if args.categories else None
        for slug in slugs:
            print(json.dumps(run_scrape(slug, trigger="cli", categories=cats, on_notifications=send_inline), indent=2))
    elif args.cmd == "create-admin":
        from app.seed import create_admin

        with session_scope() as db:
            user = create_admin(db, args.email, args.password, args.username)
            print(f"admin ready: {user.username} <{user.email}>")
    elif args.cmd == "rematch":
        from app.scraping.rematch import rematch_all

        with session_scope() as db:
            print(json.dumps(rematch_all(db), indent=2))
    elif args.cmd in ("export-snapshot", "import-snapshot"):
        from app import seed as seed_mod

        path = Path(args.path) if args.path else seed_mod.SNAPSHOT_PATH
        with session_scope() as db:
            fn = seed_mod.export_snapshot if args.cmd == "export-snapshot" else seed_mod.import_snapshot
            print(json.dumps(fn(db, path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
