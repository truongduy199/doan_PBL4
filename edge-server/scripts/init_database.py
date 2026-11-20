"""Script khởi tạo cơ sở dữ liệu MySQL/InnoDB và chạy toàn bộ migrations idempotent."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Optional

# Ensure src/ is on sys.path when invoked directly from CLI
_EDGE_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _EDGE_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from smart_parking.config.settings import Settings, get_settings


def _split_sql_statements(sql_text: str) -> list[str]:
    """Split SQL file into individual executable statements while skipping comments."""
    cleaned_lines: list[str] = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        cleaned_lines.append(line)
    joined = "\n".join(cleaned_lines)
    return [stmt.strip() for stmt in joined.split(";") if stmt.strip()]


def _clean_orphaned_xampp_ibd_files(cursor, db_name: str, force_remove_dir: bool = False) -> None:
    """
    In XAMPP MariaDB/MySQL on Windows, an unexpected shutdown can leave an orphaned .ibd file
    without a matching .frm file inside <datadir>/<db_name>, causing errno 1010 on DROP DATABASE
    or errno 150 / 1813 on CREATE TABLE. Remove orphaned .ibd files safely.
    """
    try:
        cursor.execute("SELECT @@datadir")
        row = cursor.fetchone()
        if not row:
            return
        datadir = Path(str(row[0]))
        db_dir = datadir / db_name
        if not db_dir.is_dir():
            return
        if force_remove_dir:
            shutil.rmtree(db_dir, ignore_errors=True)
            return

        # Check for any .ibd file that has no matching .frm or .sdi file (orphaned tablespace)
        ibd_files = list(db_dir.glob("*.ibd"))
        frm_names = {p.stem.lower() for p in db_dir.glob("*.frm")}
        if ibd_files and not frm_names:
            for ibd in ibd_files:
                try:
                    ibd.unlink()
                except OSError:
                    pass
    except Exception:
        pass


def init_mysql_database(
    settings: Optional[Settings] = None,
    migrations_dir: Optional[str | Path] = None,
    drop_existing: bool = False,
) -> None:
    """Create MySQL database (if missing) and execute all SQL migration files in order."""
    import mysql.connector

    cfg = settings or get_settings()
    mig_path = Path(migrations_dir) if migrations_dir else (_EDGE_ROOT / "migrations")
    if not mig_path.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục migrations: {mig_path}")

    # 1. Connect to MySQL server without database to create DB if not exists
    server_conn = mysql.connector.connect(
        host=cfg.mysql_host,
        port=cfg.mysql_port,
        user=cfg.mysql_user,
        password=cfg.mysql_password,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        use_pure=True,
        autocommit=True,
    )
    try:
        cursor = server_conn.cursor()
        db_name = cfg.mysql_database.replace("`", "")
        if drop_existing:
            try:
                cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            except mysql.connector.Error as exc:
                if exc.errno == 1010:
                    _clean_orphaned_xampp_ibd_files(cursor, db_name, force_remove_dir=True)
                    cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
                else:
                    raise
        else:
            _clean_orphaned_xampp_ibd_files(cursor, db_name, force_remove_dir=False)

        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        cursor.close()
    finally:
        server_conn.close()

    # 2. Connect to target database and run migrations
    db_conn = mysql.connector.connect(
        host=cfg.mysql_host,
        port=cfg.mysql_port,
        user=cfg.mysql_user,
        password=cfg.mysql_password,
        database=cfg.mysql_database,
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci",
        use_pure=True,
        autocommit=False,
    )
    try:
        cursor = db_conn.cursor()
        cursor.execute("SET time_zone = '+00:00'")
        sql_files = sorted(f for f in os.listdir(mig_path) if f.endswith(".sql"))
        for sql_file in sql_files:
            full_path = mig_path / sql_file
            sql_content = full_path.read_text(encoding="utf-8")
            statements = _split_sql_statements(sql_content)
            for stmt in statements:
                try:
                    cursor.execute(stmt)
                except mysql.connector.Error as exc:
                    # 1005 / 1022 / 1826: Duplicate foreign key constraint name on ALTER TABLE
                    # 1061: Duplicate key name
                    # 1050: Table already exists
                    if (
                        exc.errno in (1022, 1050, 1061, 1826)
                        or "Duplicate" in str(exc)
                        or (stmt.upper().startswith("ALTER TABLE") and exc.errno == 1005)
                    ):
                        continue
                    raise
        db_conn.commit()
        cursor.close()
        print(
            f"[OK] MySQL Database '{cfg.mysql_database}' initialized successfully "
            f"({len(sql_files)} migration files applied)."
        )
    finally:
        db_conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Khởi tạo cơ sở dữ liệu MySQL/InnoDB cho Smart Parking PBL4"
    )
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Xóa và tạo lại database từ đầu (chỉ dùng cho môi trường dev/test)",
    )
    args = parser.parse_args()
    init_mysql_database(drop_existing=args.drop_existing)


if __name__ == "__main__":
    main()
