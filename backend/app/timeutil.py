"""
Times as people say them: "tomorrow at 9", "in 2h", "every monday 10am".

Everything is stored in UTC; phrases are read in NOTIFICATION_TIMEZONE, the
same timezone the morning briefing and cron schedules use.
"""

import calendar
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings

RECURRENCES = ("daily", "weekdays", "weekly", "monthly")
DEFAULT_HOUR = 9

WEEKDAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_name) if name})
PARTS_OF_DAY = {"morning": 9, "noon": 12, "midday": 12, "afternoon": 14, "evening": 18, "night": 20}
UNITS = {
    "m": "minutes", "min": "minutes", "mins": "minutes", "minute": "minutes", "minutes": "minutes",
    "h": "hours", "hr": "hours", "hrs": "hours", "hour": "hours", "hours": "hours",
    "d": "days", "day": "days", "days": "days",
    "w": "weeks", "week": "weeks", "weeks": "weeks",
}

_RELATIVE = re.compile(r"(?:in )?(\d+|an?|half an) ?([a-z]+)")
_TIME = re.compile(r"(\d{1,2})(?::(\d{2}))? ?(am|pm)?")
_ORDINAL = r"(\d{1,2})(?:st|nd|rd|th)?"


def local_tz() -> ZoneInfo:
    return ZoneInfo(settings.notification_timezone)


def aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; everything is stored in UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt: datetime | None) -> str | None:
    dt = aware(dt)
    return dt.isoformat() if dt else None


def now_local() -> datetime:
    return datetime.now(local_tz())


def _at(day: date, hour: int, minute: int, tz) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=tz)


def end_of_day(dt: datetime) -> datetime:
    """23:59 on dt's local day, in UTC: a due *date* is overdue once that day
    is over. (UTC because SQLite compares stored times without their offset.)"""
    local = dt.astimezone(local_tz())
    return _at(local.date(), 23, 59, local_tz()).astimezone(timezone.utc)


def _parse_relative(s: str, now: datetime) -> datetime | None:
    m = _RELATIVE.fullmatch(s)
    if not m or m.group(2) not in UNITS:
        return None
    amount = {"a": 1, "an": 1, "half an": 0.5}.get(m.group(1)) or int(m.group(1))
    if not s.startswith("in ") and not m.group(1).isdigit():
        return None
    return now + timedelta(**{UNITS[m.group(2)]: amount})


def _parse_time(s: str, explicit: bool) -> tuple[int, int] | None:
    """"9am", "9:30", "21:00", "noon", "evening". A bare "9" only counts when
    explicit (after "at", or next to a day), so "buy 2 apples" isn't a time."""
    s = s.removeprefix("in the ").removeprefix("the ")
    if s.startswith("at "):
        s, explicit = s[3:], True
    if s in PARTS_OF_DAY:
        return PARTS_OF_DAY[s], 0
    if s == "midnight":
        return 23, 59
    m = _TIME.fullmatch(s)
    if not m:
        return None
    hour, minute, meridiem = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if not (explicit or meridiem or m.group(2)):
        return None
    if meridiem:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
    elif 1 <= hour <= 7 and not m.group(2):
        hour += 12  # "at 5" means 5pm, not 5am
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def _parse_day(s: str, today: date) -> tuple[date, int] | None:
    """A day and the hour to use when no time is given."""
    s = s.removeprefix("on ")
    if s == "today":
        return today, DEFAULT_HOUR
    if s == "tonight":
        return today, PARTS_OF_DAY["night"]
    if s in ("tomorrow", "tmrw", "tmr", "tomorrow morning"):
        return today + timedelta(days=1), DEFAULT_HOUR
    if s == "next week":
        return today + timedelta(days=7 - today.weekday()), DEFAULT_HOUR
    if s in ("weekend", "this weekend"):
        return today + timedelta(days=(5 - today.weekday()) % 7), DEFAULT_HOUR
    nxt = s.startswith("next ")
    name = s.removeprefix("next ").removeprefix("this ")
    if name in WEEKDAYS:
        ahead = (WEEKDAYS[name] - today.weekday()) % 7
        if nxt and ahead == 0:
            ahead = 7
        return today + timedelta(days=ahead), DEFAULT_HOUR
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            return date.fromisoformat(s), DEFAULT_HOUR
        except ValueError:
            return None
    m = re.fullmatch(rf"([a-z]+) {_ORDINAL}", s) or re.fullmatch(rf"{_ORDINAL} (?:of )?([a-z]+)", s)
    if m:
        month_name, day_str = (m.group(1), m.group(2)) if not m.group(1).isdigit() else (m.group(2), m.group(1))
        month = MONTHS.get(month_name)
        if not month:
            return None
        for year in (today.year, today.year + 1):
            try:
                day = date(year, month, int(day_str))
            except ValueError:
                return None
            if day >= today:
                return day, DEFAULT_HOUR
    return None


def parse_when(text: str, now: datetime | None = None) -> datetime | None:
    """Parse a whole phrase as a moment in time, or return None."""
    now = (now or now_local()).astimezone(local_tz())
    s = " ".join(text.lower().replace(",", " ").split())
    if not s:
        return None
    tz = local_tz()

    rel = _parse_relative(s, now)
    if rel:
        return rel

    # A day, a time, or both in either order ("tomorrow at 9", "9am friday")
    tokens = s.split()
    splits = [(s, "")] + [(" ".join(tokens[:i]), " ".join(tokens[i:])) for i in range(1, len(tokens))]
    for first, second in splits:
        for day_part, time_part in ((first, second), (second, first)):
            day = _parse_day(day_part, now.date()) if day_part else None
            if day_part and not day:
                continue
            clock = _parse_time(time_part, explicit=bool(day)) if time_part else None
            if time_part and not clock:
                continue
            if not day and not clock:
                continue
            if day:
                (d, default_hour), word = day, day_part.removeprefix("on ")
                if clock:
                    hour, minute = clock
                    if word == "tonight" and hour < 12:
                        hour += 12
                else:
                    hour, minute = default_hour, 0
                when = _at(d, hour, minute, tz)
                if when <= now and word.removeprefix("this ") in WEEKDAYS:
                    when += timedelta(days=7)
                return when
            when = _at(now.date(), *clock, tz)
            return when if when > now else when + timedelta(days=1)
    return None


def next_occurrence(dt: datetime, recurrence: str) -> datetime:
    """The same local time one step later (stepping in local time keeps 9am at
    9am across daylight-saving changes)."""
    tz = local_tz()
    local = aware(dt).astimezone(tz).replace(tzinfo=None)
    if recurrence == "daily":
        local += timedelta(days=1)
    elif recurrence == "weekdays":
        local += timedelta(days={4: 3, 5: 2}.get(local.weekday(), 1))
    elif recurrence == "weekly":
        local += timedelta(days=7)
    elif recurrence == "monthly":
        year, month = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
        local = local.replace(year=year, month=month, day=min(local.day, calendar.monthrange(year, month)[1]))
    else:
        raise ValueError(f"Unknown recurrence: {recurrence}")
    return local.replace(tzinfo=tz)


_RECURRENCE_PHRASE = re.compile(
    r"\b(?:every ?day|daily|every weekday|weekdays|every week|weekly|every month|monthly|"
    r"every (" + "|".join(sorted(WEEKDAYS, key=len, reverse=True)) + r"))\b"
)


_RECURRENCE_OF = {
    "everyday": "daily", "every day": "daily", "daily": "daily",
    "every weekday": "weekdays", "weekdays": "weekdays",
    "every week": "weekly", "weekly": "weekly",
    "every month": "monthly", "monthly": "monthly",
}


def split_reminder(text: str, now: datetime | None = None) -> tuple[datetime | None, str, str | None]:
    """Split "tomorrow at 9 call Sam" / "call Sam every monday 10am" into
    (when, what, recurrence). when is None if no time was found."""
    now = (now or now_local()).astimezone(local_tz())
    words = text.strip().split()
    if words and words[0].lower() == "me":
        words = words[1:]
    rest = " ".join(words)

    recurrence = None
    m = _RECURRENCE_PHRASE.search(rest.lower())
    if m:
        phrase = m.group(0)
        weekday = m.group(1)
        recurrence = "weekly" if weekday else _RECURRENCE_OF[phrase]
        rest = (rest[:m.start()] + (weekday or "") + rest[m.end():]).strip()

    tokens = rest.split()
    when, what = None, rest
    # Longest time phrase at the start, then at the end
    for i in range(len(tokens) - 1, 0, -1):
        when = parse_when(" ".join(tokens[:i]), now)
        if when:
            what = " ".join(tokens[i:])
            break
    if not when:
        for j in range(1, len(tokens)):
            when = parse_when(" ".join(tokens[j:]), now)
            if when:
                what = " ".join(tokens[:j])
                break
    if not when and recurrence:
        when = parse_when("tomorrow", now) if now.hour >= DEFAULT_HOUR else _at(now.date(), DEFAULT_HOUR, 0, local_tz())

    if when and recurrence == "weekdays" and when.weekday() >= 5:
        when += timedelta(days=7 - when.weekday())

    what = re.sub(r"^(?:to|that|about)\s+", "", what.strip(), flags=re.IGNORECASE).strip(" ,.:-")
    return when, what[:1].upper() + what[1:], recurrence


def parse_datetime(value: str | None, now: datetime | None = None) -> datetime | None:
    """An ISO datetime (naive means local time) or a phrase like "tomorrow 9am"."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
        return dt if dt.tzinfo else dt.replace(tzinfo=local_tz())
    except ValueError:
        return parse_when(value, now)


def describe(dt: datetime, now: datetime | None = None) -> str:
    """"today 9:00", "tomorrow 18:30", "Mon Oct 12 9:00". End-of-day times
    (due dates) are just the day: "today", "Mon Oct 12"."""
    now = (now or now_local()).astimezone(local_tz())
    local = aware(dt).astimezone(local_tz())
    if (local.hour, local.minute) == (23, 59):
        clock = ""
    else:
        clock = " " + (local.strftime("%H:%M").lstrip("0") if local.hour else local.strftime("%H:%M"))
    days = (local.date() - now.date()).days
    if days == 0:
        return f"today{clock}"
    if days == 1:
        return f"tomorrow{clock}"
    if days == -1:
        return f"yesterday{clock}"
    fmt = "%a %b %d" if local.year == now.year else "%a %b %d %Y"
    return f"{local.strftime(fmt).replace(' 0', ' ')}{clock}"
