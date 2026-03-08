#!/usr/bin/env python3

"""
kajwhat.py structure

1. Imports
2. Configuration
3. Dataclasses
4. Helpers
5. Environment status
6. SQLite → CSV pipeline
7. HTML generation
8. Program flow
"""


from __future__ import annotations

import argparse
import logging
import sqlite3
import pandas as pd
import time
import json
import html

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager



def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file missing: {config_path}. "
            "Create config.json with my_name, external_volume, and ios_backup_subdir."
        )

    config = json.loads(config_path.read_text(encoding="utf-8"))

    required = ["my_name", "external_volume", "ios_backup_subdir"]
    missing = [key for key in required if key not in config or not str(config[key]).strip()]
    if missing:
        raise ValueError(f"Missing required config keys in {config_path}: {', '.join(missing)}")

    return config



BASE_DIR = Path.home() / "Code" / "whatsapp"
LOG_PATH = BASE_DIR / "kajwhat.log"
CSV_PATH = BASE_DIR / "WhatsApp.csv"
SQLITE_PATH = BASE_DIR / "ChatStorage.sqlite"

CONFIG = load_config(BASE_DIR / "config.json")
MY_NAME = CONFIG["my_name"]
LACIE_PATH = Path("/Volumes") / CONFIG["external_volume"]
IOS_BACKUP_ROOT = LACIE_PATH / CONFIG["ios_backup_subdir"]

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



def _section_formatting_and_conversion():
    pass



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



def format_index_date(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    weekday = WEEKDAYS_SV[dt.weekday()]
    return f"{weekday} {dt.day}.{dt.month}.{dt.year}"



def apple_timestamp_to_datetime(value: float | int | None) -> datetime | None:
    """Convert Apple Core Data timestamp (seconds since 2001-01-01) to datetime."""
    if value is None or pd.isna(value):
        return None
    unix_epoch = datetime.fromtimestamp(0)
    apple_epoch = datetime(2001, 1, 1)
    return datetime.fromtimestamp(float(value)) + (apple_epoch - unix_epoch)



def _section_environment_status():
    pass



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



def should_show_verbose_preamble(previous_start: Optional[datetime], status: EnvironmentStatus, started_at: datetime) -> bool:
    if not (previous_start and status.csv.exists):
        return True
    return previous_start.date() != started_at.date()


def _section_sqlite_csv_pipeline():
    pass



def archive_existing_csv(csv_path: Path, archive_dir: Path) -> None:
    if not csv_path.exists():
        return

    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromtimestamp(csv_path.stat().st_mtime).strftime("%Y-%m-%d-%H-%M")
    archived = archive_dir / f"WhatsApp_{stamp}.csv"
    csv_path.rename(archived)
    logging.info("CSV_ARCHIVED from=%s to=%s", csv_path, archived)
    print(f"Arkiverade tidigare CSV till {archived.name}.")



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



def normalize_jid(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    return s or None



def build_jid_name_map(chat_df: pd.DataFrame, member_df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}

    for _, row in chat_df.iterrows():
        jid = normalize_jid(row.get("contact_jid"))
        name = row.get("chatpartner")
        if jid and pd.notna(name) and str(name).strip():
            mapping[jid] = str(name).strip()

    for _, row in member_df.iterrows():
        jid = normalize_jid(row.get("member_jid"))
        name = row.get("contact_name")
        if pd.isna(name) or not str(name).strip():
            name = row.get("first_name")
        if jid and pd.notna(name) and str(name).strip():
            mapping[jid] = str(name).strip()
    return mapping



def best_sender_name(row: pd.Series) -> str | None:
    if row["is_from_me"]:
        return MY_NAME

    for key in (
        "group_member_jid_name",
        "jid_name",
        "first_name",
        "contact_name",
        "push_name",
        "chatpartner",
    ):
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
    df["date"] = df["date_dt"].dt.strftime("%Y-%m-%d %H:%M")
    df["year"] = df["date_dt"].dt.year
    df["yyyymm"] = df["date_dt"].dt.strftime("%Y-%m")
    df["dmydate"] = df["date_dt"].dt.strftime("%d.%m.%Y")
    df["hhmm"] = df["date_dt"].dt.strftime("%H:%M")

    jid_name_map = build_jid_name_map(chat_df, member_df)

    df["from_jid_norm"] = df["from_jid"].map(normalize_jid)
    df["member_jid_norm"] = df["member_jid"].map(normalize_jid)

    df["jid_name"] = df["from_jid_norm"].map(jid_name_map)
    df["group_member_jid_name"] = df["member_jid_norm"].map(jid_name_map)

    # Names
    df["from_name"] = df.apply(best_sender_name, axis=1)
    df["to_name"] = df.apply(best_recipient_name, axis=1)

    df["weekday_sv"] = df["date_dt"].dt.weekday.map(lambda x: WEEKDAYS_SV[x])
    df["dmydate_with_weekday"] = df["weekday_sv"] + " " + df["dmydate"]

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
        "weekday_sv",
        "dmydate_with_weekday",
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



def _section_html_generation():
    pass



def make_filename(name: str) -> str:
    if not isinstance(name, str):
        return "ej-str"
    s = name.replace(" ", "_")
    for pair in ["ÅA", "ÄA", "ÖO", "ÜU", "ßs", "åa", "äa", "öo", "üu", "/_"]:
        s = s.replace(pair[0], pair[1])
    return s



def render_message_text(text: str) -> str:
    if not text:
        return ""
    return html.escape(text)



def html_message_line(row: pd.Series, reply_lookup: dict[int, dict]) -> str:
    text = render_message_text(row["text"] if pd.notna(row["text"]) else "")
    anchor = f"msg_{int(row['message_id'])}"
    hhmm = row["hhmm"]

    if row["is_from_me"]:
        sender = MY_NAME
        msg_class = "msg msg-me"
    else:
        sender = row["from_name"] if pd.notna(row["from_name"]) else row["chatpartner"]
        msg_class = "msg msg-other"

    reply_html = ""
    if pd.notna(row["reply_to"]):
        reply_id = int(row["reply_to"])
        reply = reply_lookup.get(reply_id)
        if reply:
            reply_sender = reply["from_name"] if pd.notna(reply["from_name"]) else reply["chatpartner"]
            reply_text = render_message_text(reply["text"] if pd.notna(reply["text"]) else "")
            reply_html = (
                f"<div class='reply-preview'>"
                f"<a href='#msg_{reply_id}'>"
                f"<span class='reply-sender'>{html.escape(str(reply_sender))}:</span> "
                f"{reply_text}"
                f"</a></div>"
            )
        else:
            reply_html = (
                f"<div class='reply-preview'>"
                f"<a href='#msg_{reply_id}'>↩ tidigare meddelande</a>"
                f"</div>"
            )

    return (
        f"<div class='{msg_class}' id='{anchor}'>\n"
        f"  {reply_html}\n"
        f"  <div class='msg-main'>\n"
        f"    <span class='sender'>{html.escape(str(sender))}</span>: "
        f"<span class='text'>{text}</span>\n"
        f"    <span class='time'>{hhmm}</span>\n"
        f"  </div>\n"
        f"</div>\n"
    )



def build_chat_toc(chat_df: pd.DataFrame) -> list[str]:
    lines = ["<div class='chat-toc'>\n", "<h2>Index</h2>\n"]

    for year, year_df in chat_df.groupby("year", sort=True):
        lines.append(f"<div><a href='#year_{year}'>{year}</a></div>\n")

        for yyyymm, month_df in year_df.groupby("yyyymm", sort=True):
            day_links = []
            for dmydate, day_df in month_df.groupby("dmydate", sort=True):
                day_num = day_df["dmydate"].iloc[0].split(".")[0].lstrip("0")
                day_anchor = f"day_{dmydate}"
                day_links.append(f"<a href='#{day_anchor}'>{day_num}</a>")

            month_anchor = f"month_{yyyymm}"
            lines.append(
                f"<div class='chat-toc-month'>&bull; "
                f"<a href='#{month_anchor}'>{yyyymm}</a>: "
                f"{' '.join(day_links)}"
                f"</div>\n"
            )

    lines.append("</div>\n")
    return lines



def write_chat_html(chat_df: pd.DataFrame, out_dir: Path) -> None:
    if chat_df.empty:
        return

    chatpartner = chat_df["chatpartner"].iloc[0]
    filename = out_dir / f"{make_filename(chatpartner)}.html"
    style = '<link rel="stylesheet" href="../whatsapp.css">'

    lines = [
        f"<html><head><title>WhatsApp {chatpartner}</title>{style}</head><body>\n",
        f"<h1>{chatpartner}</h1>\n",
    ]
    lines.extend(build_index_nav())
    lines.extend(build_chat_toc(chat_df))
    reply_lookup = (
        chat_df.set_index("message_id")[["from_name", "chatpartner", "text"]]
        .to_dict("index")
    )

    for year, year_df in chat_df.groupby("year", sort=True):
        year_anchor = f"year_{year}"
        lines.append(f"<h2 id='{year_anchor}'>{year}</h2>\n")
        for yyyymm, month_df in year_df.groupby("yyyymm", sort=True):
            month_anchor = f"month_{yyyymm}"
            lines.append(f"<h3 id='{month_anchor}'>{yyyymm}</h3>\n")
            for dmydate_with_weekday, day_df in month_df.groupby("dmydate_with_weekday", sort=True):
                day_anchor = f"day_{day_df['dmydate'].iloc[0]}"
                lines.append(f"<h4 id='{day_anchor}'>{dmydate_with_weekday}</h4>\n")
                for _, row in day_df.iterrows():
                    lines.append(html_message_line(row, reply_lookup))

    lines.append("</body></html>\n")
    filename.write_text("".join(lines), encoding="utf-8")



def filter_index_scope(df: pd.DataFrame, scope: str) -> pd.DataFrame:
    today = datetime.now()

    if scope == "all":
        return df

    if scope == "year":
        return df[df["year"] == today.year]

    if scope == "month":
        current_yyyymm = today.strftime("%Y-%m")
        return df[df["yyyymm"] == current_yyyymm]

    raise ValueError(f"Unknown scope: {scope}")



def build_index_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("chatpartner", dropna=False)
        .agg(
            message_count=("message_id", "count"),
            latest_timestamp=("timestamp", "max"),
            latest_date=("date", "max"),
        )
        .reset_index()
    )

    grouped["filename"] = grouped["chatpartner"].map(lambda x: f"{make_filename(str(x))}.html")
    return grouped



def sort_index_dataframe(index_df: pd.DataFrame, order: str) -> pd.DataFrame:
    if order == "alpha":
        return index_df.sort_values(["chatpartner"])
    if order == "size":
        return index_df.sort_values(["message_count", "chatpartner"], ascending=[False, True])
    if order == "date":
        return index_df.sort_values(["latest_timestamp", "chatpartner"], ascending=[False, True])
    raise ValueError(f"Unknown order: {order}")



def build_index_nav() -> list[str]:
    lines = ["<div class='index-nav'>\n"]
    for scope in ["month", "year", "all"]:
        for order in ["alpha", "size", "date"]:
            href = f"index_{scope}_{order}.html"
            label = f"{scope}/{order}"
            lines.append(f"<a href='{href}'>{label}</a> ")
    lines.append("</div>\n")
    return lines



def write_index_html(index_df: pd.DataFrame, out_dir: Path, scope: str, order: str) -> None:
    filename = out_dir / f"index_{scope}_{order}.html"
    style = '<link rel="stylesheet" href="../whatsapp.css">'

    def scope_label(scope: str) -> str:
        now = datetime.now()
        if scope == "all":
            return "all"
        if scope == "year":
            return str(now.year)
        if scope == "month":
            return now.strftime("%Y-%m")
        raise ValueError(f"Unknown scope: {scope}")    
    title = f"WhatsApp {scope_label(scope)} / {order}"

    lines = [
        f"<html><head><title>{title}</title>{style}</head><body>\n",
        f"<h1>{title}</h1>\n",
    ]
    lines.extend(build_index_nav())
    lines.extend("<ol>\n")

    for _, row in index_df.iterrows():
        chatpartner = html.escape(str(row["chatpartner"]))
        href = html.escape(str(row["filename"]))
        count = int(row["message_count"])
        latest = html.escape(format_index_date(str(row["latest_date"])))
        lines.append(
            f"<li><a href='{href}'>{chatpartner}</a> "
            f"({count}) {latest}</li>\n"
        )

    lines.append("</ol>\n")
    lines.append("</body></html>\n")
    filename.write_text("".join(lines), encoding="utf-8")



def create_index_pages_from_csv(csv_path: Path) -> None:
    df = pd.read_csv(csv_path, sep=";")
    out_dir = BASE_DIR / "html"
    out_dir.mkdir(parents=True, exist_ok=True)

    for scope in ["month", "year", "all"]:
        scoped_df = filter_index_scope(df, scope)
        index_df = build_index_dataframe(scoped_df)

        for order in ["alpha", "size", "date"]:
            sorted_index_df = sort_index_dataframe(index_df, order)
            write_index_html(sorted_index_df, out_dir, scope, order)



def create_html_from_csv(csv_path: Path, keyword: Optional[str]) -> tuple[int, int]:
    df = pd.read_csv(csv_path, sep=";")
    out_dir = BASE_DIR / "html"
    out_dir.mkdir(parents=True, exist_ok=True)

    if keyword:
        mask = (
            df["text"].fillna("").str.contains(keyword, case=False, na=False) |
            df["chatpartner"].fillna("").str.contains(keyword, case=False, na=False)
        )
        df = df[mask]

    df = df.sort_values(["chatpartner", "timestamp", "message_id"])

    created = 0
    overwritten = 0

    for _, chat_df in df.groupby("chatpartner", sort=True):
        target = out_dir / f"{make_filename(chat_df['chatpartner'].iloc[0])}.html"
        existed = target.exists()
        write_chat_html(chat_df, out_dir)
        if existed:
            overwritten += 1
        else:
            created += 1

    return created, overwritten



def _section_program_flow():
    pass



@contextmanager
def timed_step(label: str, start_text: str, end_text: str | None = None):
    print(start_text)
    logging.info("%s_START", label)
    started = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - started
        logging.info("%s_END seconds=%.3f", label, elapsed)
        if end_text:
            print(f"{end_text} ({elapsed:.1f} s)")



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

    if should_show_verbose_preamble(previous_start, status, started_at):
        print_verbose_status(previous_start, status, started_at)

    # TODO: During development it may be useful to reuse an existing CSV
    # instead of always archiving and rebuilding it. For normal production
    # use, rebuilding CSV from SQLite is the intended default.

    if not CSV_PATH.exists():
        with timed_step(
            "CSV_GENERATION",
            "Skapar WhatsApp.csv från ChatStorage.sqlite...",
            "WhatsApp.csv skapad"
        ):
            create_whatsapp_csv(SQLITE_PATH, CSV_PATH)
    else:
        print("Återanvänder befintlig WhatsApp.csv.")
        logging.info("CSV_REUSED path=%s", CSV_PATH)

    with timed_step(
        "HTML_GENERATION",
        "Skapar HTML-filer från WhatsApp.csv...",
        "HTML-filer skapade"
    ):
        created, overwritten = create_html_from_csv(CSV_PATH, args.keyword)

    with timed_step(
        "INDEX_GENERATION",
        "Skapar indexsidor...",
        "Indexsidor skapade"
    ):
        create_index_pages_from_csv(CSV_PATH)

    print(f"HTML-filer: {created} skapade, {overwritten} överskrivna.")
    logging.info("HTML files created=%s overwritten=%s", created, overwritten)

    logging.info("Program finished")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
