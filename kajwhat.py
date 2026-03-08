#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sqlite3
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


BASE_DIR = Path.home() / "Code" / "whatsapp"
LOG_PATH = BASE_DIR / "kajwhat.log"
CSV_PATH = BASE_DIR / "WhatsApp.csv"
SQLITE_PATH = BASE_DIR / "ChatStorage.sqlite"
LACIE_PATH = Path("/Volumes/LaCie")
IOS_BACKUP_ROOT = LACIE_PATH / "MobileSync" / "Backup"

WEEKDAYS_SV = ["mån", "tis", "ons", "tor", "fre", "lör", "sön"]


@dataclass
class FileStatus:
    exists: bool
    date: Optional[datetime] = None
    mb: Optional[str] = None
    path: Optional[Path] = None


@dataclass
class IOSBackupStatus:
    exists: bool
    latest_backup_name: Optional[str] = None
    latest_backup_date: Optional[datetime] = None
    latest_backup_mb: Optional[str] = None
    latest_backup_path: Optional[Path] = None


@dataclass
class EnvironmentStatus:
    csv: FileStatus
    log: FileStatus
    sqlite: FileStatus
    lacie_exists: bool
    ios_backup: IOSBackupStatus


def format_mb(num_bytes: int) -> str:
    mb = round(num_bytes / (1024 * 1024))
    return f"{mb:,} MB".replace(",", ".")



def format_sv_datetime(dt: datetime) -> str:
    weekday = WEEKDAYS_SV[dt.weekday()]
    return f"{weekday} {dt.day}.{dt.month}.{dt.year} kl. {dt:%H:%M:%S}"



def format_timedelta_since(then: datetime, now: datetime) -> str:
    delta = now - then
    total_seconds = max(int(delta.total_seconds()), 0)
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    if days >= 2:
        return f"för {days}d sedan"
    if days >= 1:
        return f"för {days}d{hours}h sedan"
    return f"för {hours}h{minutes}min sedan"



def file_status(path: Path) -> FileStatus:
    if not path.exists():
        return FileStatus(exists=False, path=path)
    stat = path.stat()
    return FileStatus(
        exists=True,
        date=datetime.fromtimestamp(stat.st_mtime),
        mb=format_mb(stat.st_size),
        path=path,
    )



def latest_ios_backup_status(root: Path) -> IOSBackupStatus:
    if not root.exists() or not root.is_dir():
        return IOSBackupStatus(exists=False)

    candidates = [p for p in root.iterdir() if p.is_dir()]
    if not candidates:
        return IOSBackupStatus(exists=False)

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    stat = latest.stat()

    # Viktigt: gå inte rekursivt genom hela backupen här.
    # En full iPhone-backup kan innehålla hundratusentals eller miljontals filer,
    # och då hänger programmet bara medan det summerar storleken.
    # Katalogens egen mtime räcker för att identifiera senaste backup.
    # Storleken lämnar vi tills vidare okänd i statusutskriften.
    return IOSBackupStatus(
        exists=True,
        latest_backup_name=str(latest),
        latest_backup_date=datetime.fromtimestamp(stat.st_mtime),
        latest_backup_mb=None,
        latest_backup_path=latest,
    )



def collect_environment_status() -> EnvironmentStatus:
    return EnvironmentStatus(
        csv=file_status(CSV_PATH),
        log=file_status(LOG_PATH),
        sqlite=file_status(SQLITE_PATH),
        lacie_exists=LACIE_PATH.exists(),
        ios_backup=latest_ios_backup_status(IOS_BACKUP_ROOT),
    )



def latest_logged_start(log_path: Path) -> Optional[datetime]:
    if not log_path.exists():
        return None

    latest: Optional[datetime] = None
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        marker = "PROGRAM_START "
        if marker not in line:
            continue
        ts = line.split(marker, 1)[1].strip()
        try:
            latest = datetime.fromisoformat(ts)
        except ValueError:
            continue
    return latest



def setup_logging(started_at: datetime) -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("PROGRAM_START %s", started_at.isoformat(timespec="milliseconds"))



def print_verbose_status(previous_start: Optional[datetime], status: EnvironmentStatus, started_at: datetime) -> None:

    print(f"Programmet kajwhat.py startade {format_sv_datetime(started_at)}")
    if previous_start:
        print(
            f"Föregående start var {format_sv_datetime(previous_start)} "
            f"{format_timedelta_since(previous_start, started_at)}"
        )
    else:
        print("Föregående start saknas")

    print(
        f"Extern skiva {LACIE_PATH} "
        f"{'ansluten' if status.lacie_exists else 'icke ansluten'}"
    )
    print(
        f"iOS-backup-katalog {IOS_BACKUP_ROOT} "
        f"{'finns' if IOS_BACKUP_ROOT.exists() else 'saknas'}"
    )

    if status.ios_backup.exists and status.ios_backup.latest_backup_date:
        size_text = (
            f" ({status.ios_backup.latest_backup_mb})"
            if status.ios_backup.latest_backup_mb
            else ""
        )
        print(
            f"iOS-backup-fil {status.ios_backup.latest_backup_name} tagen "
            f"{format_sv_datetime(status.ios_backup.latest_backup_date)} "
            f"{format_timedelta_since(status.ios_backup.latest_backup_date, started_at)}"
            f"{size_text}"
        )
    else:
        print("iOS-backup-fil saknas")

    if status.sqlite.exists and status.sqlite.date and status.sqlite.mb:
        print(
            f"ChatStorage.sqlite extraherad {format_sv_datetime(status.sqlite.date)} "
            f"{format_timedelta_since(status.sqlite.date, started_at)} ({status.sqlite.mb})"
        )
    else:
        print("ChatStorage.sqlite saknas")

    if status.csv.exists and status.csv.date and status.csv.mb:
        print(
            f"WhatsApp.csv skapt {format_sv_datetime(status.csv.date)} "
            f"{format_timedelta_since(status.csv.date, started_at)} ({status.csv.mb})"
        )
    else:
        print("WhatsApp.csv saknas")



def should_skip_verbose(previous_start: Optional[datetime], status: EnvironmentStatus, started_at: datetime) -> bool:
    if not (previous_start and status.csv.exists):
        return False
    return previous_start.date() == started_at.date()



def create_html_from_csv(csv_path: Path, keyword: Optional[str]) -> None:
    logging.info("HTML_GENERATION_START csv=%s keyword=%s", csv_path, keyword)
    if keyword:
        print(f"Nästa steg: skapa HTML-filer utgående från {csv_path.name} med sökord '{keyword}'.")
    else:
        print(f"Nästa steg: skapa HTML-filer utgående från {csv_path.name}.")
    logging.info("HTML_GENERATION_END")



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="kajwhat.py – skördar och analyserar WhatsApp-data"
    )
    parser.add_argument(
        "keyword",
        nargs="?",
        help="valfritt sökord, t.ex. 'Älveskär' eller 'Felix'",
    )
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    started_at = datetime.now()
    previous_start = latest_logged_start(LOG_PATH)
    status = collect_environment_status()
    setup_logging(started_at)
    logging.info("Program started in %s", BASE_DIR)

    logging.info(
        "Status csv_exists=%s log_exists=%s sqlite_exists=%s lacie_exists=%s ios_backup_exists=%s",
        status.csv.exists,
        status.log.exists,
        status.sqlite.exists,
        status.lacie_exists,
        status.ios_backup.exists,
    )

    if should_skip_verbose(previous_start, status, started_at) and status.csv.exists:
        logging.info("Skipping verbose status; continuing directly to HTML generation")
        create_html_from_csv(CSV_PATH, args.keyword)
        logging.info("Program finished")
        return 0

    print_verbose_status(previous_start, status, started_at)
    create_html_from_csv(CSV_PATH, args.keyword)
    logging.info("Program finished")
    return 0


def apple_timestamp_to_datetime(value: float | int | None) -> datetime | None:
    """Convert Apple Core Data timestamp (seconds since 2001-01-01) to datetime."""
    if value is None or pd.isna(value):
        return None
    unix_epoch = datetime.fromtimestamp(0)
    apple_epoch = datetime(2001, 1, 1)
    return datetime.fromtimestamp(float(value)) + (apple_epoch - unix_epoch)


def read_chat_sessions(con: sqlite3.Connection) -> pd.DataFrame:
    query = """
        SELECT
            Z_PK AS chat_id,
            ZPARTNERNAME AS chatpartner,
            ZCONTACTJID AS contact_jid
        FROM ZWACHATSESSION
    """
    return pd.read_sql_query(query, con)


def read_group_members(con: sqlite3.Connection) -> pd.DataFrame:
    query = """
        SELECT
            Z_PK AS group_member_id,
            ZCHATSESSION AS chat_id,
            ZMEMBERJID AS member_jid,
            ZCONTACTNAME AS contact_name,
            ZFIRSTNAME AS first_name
        FROM ZWAGROUPMEMBER
    """
    return pd.read_sql_query(query, con)


def read_media_items(con: sqlite3.Connection) -> pd.DataFrame:
    query = """
        SELECT
            Z_PK AS media_item_id,
            ZMEDIALOCALPATH AS media_path,
            ZLATITUDE AS latitude,
            ZLONGITUDE AS longitude
        FROM ZWAMEDIAITEM
    """
    return pd.read_sql_query(query, con)


def read_messages(con: sqlite3.Connection) -> pd.DataFrame:
    query = """
        SELECT
            Z_PK AS message_id,
            ZCHATSESSION AS chat_id,
            ZMESSAGEDATE AS timestamp,
            ZFROMJID AS from_jid,
            ZTOJID AS to_jid,
            ZTEXT AS text,
            ZISFROMME AS is_from_me,
            ZPARENTMESSAGE AS reply_to,
            ZGROUPMEMBER AS group_member_id,
            ZMESSAGEINFO AS message_info_id,
            ZMEDIAITEM AS media_item_id,
            ZMESSAGETYPE AS message_type,
            ZGROUPEVENTTYPE AS group_event_type,
            ZPUSHNAME AS push_name
        FROM ZWAMESSAGE
    """
    return pd.read_sql_query(query, con)


def best_sender_name(row: pd.Series) -> str | None:
    """Choose the best sender name available for a row."""
    if row["is_from_me"]:
        return "Kaj"

    for key in ("first_name", "contact_name", "push_name", "chatpartner"):
        value = row.get(key)
        if pd.notna(value) and str(value).strip():
            return str(value).strip()

    return None


def best_recipient_name(row: pd.Series) -> str | None:
    """Choose the best recipient name available for a row."""
    if row["is_from_me"]:
        value = row.get("chatpartner")
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return None


def build_whatsapp_dataframe(sqlite_path: Path) -> pd.DataFrame:
    con = sqlite3.connect(sqlite_path)
    try:
        chat_df = read_chat_sessions(con)
        member_df = read_group_members(con)
        media_df = read_media_items(con)
        msg_df = read_messages(con)
    finally:
        con.close()

    # Enrich messages with chat names
    df = msg_df.merge(chat_df, on="chat_id", how="left")

    # Enrich messages with group member data
    df = df.merge(
        member_df,
        on=["chat_id", "group_member_id"],
        how="left",
    )

    # Enrich messages with media data
    df = df.merge(media_df, on="media_item_id", how="left")

    # Derived datetime fields
    df["date_dt"] = df["timestamp"].apply(apple_timestamp_to_datetime)
    df["date"] = df["date_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["year"] = df["date_dt"].dt.year
    df["yyyymm"] = df["date_dt"].dt.strftime("%Y-%m")
    df["dmydate"] = df["date_dt"].dt.strftime("%d.%m.%Y")
    df["hhmm"] = df["date_dt"].dt.strftime("%H:%M:%S")

    # Names
    df["from_name"] = df.apply(best_sender_name, axis=1)
    df["to_name"] = df.apply(best_recipient_name, axis=1)

    # Placeholder for future reaction support
    df["reactions"] = ""

    # Final column order
    columns = [
        "message_id",
        "chat_id",
        "chatpartner",
        "timestamp",
        "date",
        "year",
        "yyyymm",
        "dmydate",
        "hhmm",
        "from_jid",
        "to_jid",
        "from_name",
        "to_name",
        "is_from_me",
        "text",
        "reply_to",
        "group_member_id",
        "message_info_id",
        "reactions",
        "media_item_id",
        "media_path",
        "latitude",
        "longitude",
        "message_type",
        "group_event_type",
        "push_name",
    ]

    df = df[columns].sort_values(["chatpartner", "timestamp", "message_id"])
    return df


def create_whatsapp_csv(sqlite_path: Path, csv_path: Path) -> None:
    df = build_whatsapp_dataframe(sqlite_path)
    df.to_csv(csv_path, sep=";", index=False)


if __name__ == "__main__":
    raise SystemExit(main())
