from datetime import datetime, timezone
import zoneinfo

DHAKA_TZ = zoneinfo.ZoneInfo("Asia/Dhaka")


def utc_now() -> datetime:
    """Return current timestamp in UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


def to_dhaka_time(dt: datetime) -> datetime:
    """Convert any datetime to Asia/Dhaka local time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(DHAKA_TZ)


def format_dhaka_date(dt: datetime) -> str:
    """Format datetime as YYYY-MM-DD in Asia/Dhaka."""
    return to_dhaka_time(dt).strftime("%Y-%m-%d")


def format_dhaka_datetime(dt: datetime) -> str:
    """Format datetime as YYYY-MM-DD HH:MM:SS in Asia/Dhaka."""
    return to_dhaka_time(dt).strftime("%Y-%m-%d %I:%M:%S %p")

