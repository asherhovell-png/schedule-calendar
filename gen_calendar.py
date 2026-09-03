#!/usr/bin/env python3
"""
Generate a Google-Calendar-importable .ics from the Master Schedule.
Regenerate any time the schedule changes, then re-import/replace, then push.

Timezone handling (IMPORTANT):
  Google's "Add by URL" feed importer does NOT reliably honor a VTIMEZONE block;
  it treats TZID-registered wall-clock times as UTC and shifts them by the local
  offset (e.g. +13h in NZDT -> events appear off by a day/time). To guarantee
  correct wall-clock times, every event is emitted with an EXPLICIT UTC instant
  (trailing Z). Google converts UTC to the viewer's local zone correctly.

  New Zealand time is NOT a fixed offset: NZST = UTC+12, NZDT = UTC+13, and NZDT
  begins on the last Sunday of September (2026-09-27). Any recurring event that
  spans that date is SPLIT into two occurrences, one per DST period, so the local
  wall-clock time stays correct across the change.
"""
import datetime
import uuid

# ---------------------------------------------------------------------------
# Auckland timezone offsets (seconds) + DST boundary.
# ---------------------------------------------------------------------------
NZST = 12 * 3600   # UTC+12 (standard)
NZDT = 13 * 3600   # UTC+13 (daylight, from last Sun of Sep)
DST_NZDT_START = datetime.date(2026, 9, 27)  # first NZDT day in 2026

# ---------------------------------------------------------------------------
# Academic week -> start (Monday) date mapping.
# Anchor: week 19 = Mon 2026-08-31 (today is Thu 2026-09-03, week 19).
# ---------------------------------------------------------------------------
WEEK19_MON = datetime.date(2026, 8, 31)
week_start = {n: WEEK19_MON + datetime.timedelta(weeks=n - 19) for n in range(1, 25)}

lines = []
lines.append("BEGIN:VCALENDAR")
lines.append("VERSION:2.0")
lines.append("PRODID:-//Second Brain//Master Schedule//EN")
lines.append("CALSCALE:GREGORIAN")
lines.append("METHOD:PUBLISH")
lines.append("X-WR-TIMEZONE:Pacific/Auckland")
# No VTIMEZONE block: times are emitted as explicit UTC (Z), which Google
# feed imports convert to the viewer's local zone without ambiguity.


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def akl_utc(d, hh, mm, offset_sec):
    """Auckland wall-clock (date d, hh:mm) -> UTC-aware datetime, given offset.

    Returns a timezone-aware UTC datetime so that downstream .astimezone(utc)
    calls are no-ops (a naive datetime would otherwise be re-interpreted in the
    host's local zone and double-shifted).
    """
    local = datetime.datetime(d.year, d.month, d.day, hh, mm)
    utc_naive = local - datetime.timedelta(seconds=offset_sec)
    return utc_naive.replace(tzinfo=datetime.timezone.utc)


def fmt_utc(dt_):
    return dt_.astimezone(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def alarm(minutes_before):
    return [
        "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Reminder",
        "TRIGGER:-PT%dM" % minutes_before, "END:VALARM",
    ]


def vevent_utc(summary, start_utc, end_utc, rrule=None, reminder_minutes=10, desc="", uid_tag=""):
    """Emit one VEVENT with explicit UTC start/end."""
    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, "sb://" + summary + uid_tag + start_utc.strftime("%Y%m%d%H%M")))
    lines.append("BEGIN:VEVENT")
    lines.append("UID:%s" % uid)
    lines.append("DTSTAMP:" + stamp())
    lines.append("DTSTART;VALUE=DATE-TIME:%s" % fmt_utc(start_utc))
    lines.append("DTEND;VALUE=DATE-TIME:%s" % fmt_utc(end_utc))
    lines.append("SUMMARY:%s" % summary)
    if desc:
        lines.append("DESCRIPTION:%s" % desc.replace("\n", "\\n"))
    lines.append("TRANSP:OPAQUE")
    if rrule:
        lines.append("RRULE:%s" % rrule)
    lines.extend(alarm(reminder_minutes))
    lines.append("END:VEVENT")


def weekday_dates(byday, start_date, end_date):
    """Return sorted list of dates from start_date..end_date falling on byday."""
    target = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}[byday]
    out = []
    d = start_date
    while d <= end_date:
        if d.weekday() == target:
            out.append(d)
        d += datetime.timedelta(days=1)
    return out


def emit_recurring(summary, byday, start_date, end_date, hh, mm, dur_min, reminder_minutes=10, desc=""):
    """
    Emit one or more VEVENTs for a weekly (byday) event from start_date to
    end_date at Auckland wall-clock hh:mm, split across the NZ DST boundary so
    the local time stays correct.
    """
    dates = weekday_dates(byday, start_date, end_date)
    if not dates:
        return
    nzst_dates = [d for d in dates if d < DST_NZDT_START]
    nzdt_dates = [d for d in dates if d >= DST_NZDT_START]
    dd = datetime.timedelta(minutes=dur_min)

    if nzst_dates:
        s = akl_utc(nzst_dates[0], hh, mm, NZST)
        e = akl_utc(nzst_dates[0], hh, mm, NZST) + dd
        until = akl_utc(nzst_dates[-1], 23, 59, NZST)
        rrule = "FREQ=WEEKLY;BYDAY=%s;UNTIL=%s" % (byday, fmt_utc(until))
        vevent_utc(summary, s, e, rrule, reminder_minutes, desc, uid_tag="NZST")

    if nzdt_dates:
        s = akl_utc(nzdt_dates[0], hh, mm, NZDT)
        e = akl_utc(nzdt_dates[0], hh, mm, NZDT) + dd
        until = akl_utc(nzdt_dates[-1], 23, 59, NZDT)
        rrule = "FREQ=WEEKLY;BYDAY=%s;UNTIL=%s" % (byday, fmt_utc(until))
        vevent_utc(summary, s, e, rrule, reminder_minutes, desc, uid_tag="NZDT")


def emit_once(summary, d, hh, mm, dur_min, reminder_minutes=10, desc=""):
    """Emit a one-off VEVENT at Auckland wall-clock hh:mm on date d."""
    off = NZDT if d >= DST_NZDT_START else NZST
    s = akl_utc(d, hh, mm, off)
    e = s + datetime.timedelta(minutes=dur_min)
    ld = lambda dt_: dt_.strftime("%Y-%m-%d")
    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, "sb://once:" + summary + ld(d) + str(hh) + str(mm)))
    lines.append("BEGIN:VEVENT")
    lines.append("UID:%s" % uid)
    lines.append("DTSTAMP:" + stamp())
    lines.append("DTSTART;VALUE=DATE-TIME:%s" % fmt_utc(s))
    lines.append("DTEND;VALUE=DATE-TIME:%s" % fmt_utc(e))
    lines.append("SUMMARY:%s" % summary)
    if desc:
        lines.append("DESCRIPTION:%s" % desc.replace("\n", "\\n"))
    lines.append("TRANSP:OPAQUE")
    lines.extend(alarm(reminder_minutes))
    lines.append("END:VEVENT")


# ---------------------------------------------------------------------------
# 1. Sleep — every night 22:00->07:00 (transparent). Spans DST boundary -> split.
# ---------------------------------------------------------------------------
# Sleep occurs every day; split into NZST (Aug 31..Sep 26) and NZDT (Sep 27..end).
sleep_start = datetime.date(2026, 8, 31)
sleep_end = datetime.date(2026, 12, 31)  # far future; runs indefinitely
# NZST segment
s = akl_utc(sleep_start, 22, 0, NZST)
until_s = akl_utc(datetime.date(2026, 9, 26), 23, 59, NZST)
lines.append("BEGIN:VEVENT")
lines.append("UID:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "sb://SleepNZST")))
lines.append("DTSTAMP:" + stamp())
lines.append("DTSTART;VALUE=DATE-TIME:%s" % fmt_utc(s))
lines.append("DURATION:PT9H")
lines.append("SUMMARY:Sleep")
lines.append("TRANSP:TRANSPARENT")
lines.append("RRULE:FREQ=DAILY;UNTIL=%s" % fmt_utc(until_s))
lines.append("END:VEVENT")
# NZDT segment (from Sep 27)
s2 = akl_utc(datetime.date(2026, 9, 27), 22, 0, NZDT)
until2 = akl_utc(sleep_end, 23, 59, NZDT)
lines.append("BEGIN:VEVENT")
lines.append("UID:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "sb://SleepNZDT")))
lines.append("DTSTAMP:" + stamp())
lines.append("DTSTART;VALUE=DATE-TIME:%s" % fmt_utc(s2))
lines.append("DURATION:PT9H")
lines.append("SUMMARY:Sleep")
lines.append("TRANSP:TRANSPARENT")
lines.append("RRULE:FREQ=DAILY;UNTIL=%s" % fmt_utc(until2))
lines.append("END:VEVENT")

# ---------------------------------------------------------------------------
# 2. Gym every other day 07:00-08:00 (anchor 2026-09-05). DST split.
# ---------------------------------------------------------------------------
gym_end = datetime.date(2026, 12, 31)

# Build every-2nd-day date list manually from anchor
gym_anchor = datetime.date(2026, 9, 5)
gym_dates = []
d = gym_anchor
while d <= gym_end:
    gym_dates.append(d)
    d += datetime.timedelta(days=2)
gym_nzst = [x for x in gym_dates if x < DST_NZDT_START]
gym_nzdt = [x for x in gym_dates if x >= DST_NZDT_START]
if gym_nzst:
    s = akl_utc(gym_nzst[0], 7, 0, NZST); e = s + datetime.timedelta(hours=1)
    rr = "FREQ=DAILY;INTERVAL=2;UNTIL=%s" % fmt_utc(akl_utc(gym_nzst[-1], 23, 59, NZST))
    vevent_utc("Gym (full body)", s, e, rr, 30, uid_tag="GymNZST")
if gym_nzdt:
    s = akl_utc(gym_nzdt[0], 7, 0, NZDT); e = s + datetime.timedelta(hours=1)
    rr = "FREQ=DAILY;INTERVAL=2;UNTIL=%s" % fmt_utc(akl_utc(gym_nzdt[-1], 23, 59, NZDT))
    vevent_utc("Gym (full body)", s, e, rr, 30, uid_tag="GymNZDT")

# Rest-day incline walk (days between gym days), 07:00-07:30
walk_dates = []
d = gym_anchor + datetime.timedelta(days=1)
while d <= gym_end:
    walk_dates.append(d)
    d += datetime.timedelta(days=2)
walk_nzst = [x for x in walk_dates if x < DST_NZDT_START]
walk_nzdt = [x for x in walk_dates if x >= DST_NZDT_START]
if walk_nzst:
    s = akl_utc(walk_nzst[0], 7, 0, NZST); e = s + datetime.timedelta(minutes=30)
    rr = "FREQ=DAILY;INTERVAL=2;UNTIL=%s" % fmt_utc(akl_utc(walk_nzst[-1], 23, 59, NZST))
    vevent_utc("Rest-day incline walk", s, e, rr, 15, uid_tag="WalkNZST")
if walk_nzdt:
    s = akl_utc(walk_nzdt[0], 7, 0, NZDT); e = s + datetime.timedelta(minutes=30)
    rr = "FREQ=DAILY;INTERVAL=2;UNTIL=%s" % fmt_utc(akl_utc(walk_nzdt[-1], 23, 59, NZDT))
    vevent_utc("Rest-day incline walk", s, e, rr, 15, uid_tag="WalkNZDT")

# ---------------------------------------------------------------------------
# 3. Lectures (every week while Wellington uni T2 runs: to ~9 Oct 2026)
# ---------------------------------------------------------------------------
wl1 = datetime.date(2026, 8, 31)   # week 19 Mon
lecture_end = datetime.date(2026, 10, 11)
emit_recurring("Crim Lecture",  "MO", wl1, lecture_end, 16, 10, 80, 10, "LAWS214 Crim lecture")
emit_recurring("Torts Lecture", "TU", wl1, lecture_end, 11, 0, 80, 10, "LAWS212 Torts lecture")
emit_recurring("Public Lecture", "WE", wl1, lecture_end, 15, 10, 80, 10, "LAWS213 Public lecture")
emit_recurring("Torts Lecture", "TH", wl1, lecture_end, 11, 0, 80, 10, "LAWS212 Torts lecture")
emit_recurring("Crim Lecture",  "TH", wl1, lecture_end, 16, 10, 80, 10, "LAWS214 Crim lecture")
emit_recurring("Public Lecture", "FR", wl1, lecture_end, 15, 10, 80, 10, "LAWS213 Public lecture")

# ---------------------------------------------------------------------------
# 4. Muay Thai — every week to ~mid-Nov (only while in Wellington), DST split.
# ---------------------------------------------------------------------------
mt_end = datetime.date(2026, 11, 15)
emit_recurring("Muay Thai training", "MO", wl1, mt_end, 18, 30, 60, 30, "Wellington Thai Boxing")
emit_recurring("Sparring",           "MO", wl1, mt_end, 19, 30, 45, 15, "Wellington Thai Boxing")
emit_recurring("Muay Thai training", "WE", wl1, mt_end, 18, 30, 60, 30, "Wellington Thai Boxing")
emit_recurring("Abs (~30 min)",      "WE", wl1, mt_end, 19, 30, 30, 5,  "Post-training abs")

# ---------------------------------------------------------------------------
# 5. Groceries — Sunday 08:00-09:30 (runs through the schedule), DST split.
# ---------------------------------------------------------------------------
gro_end = datetime.date(2026, 11, 15)
emit_recurring("Groceries", "SU", wl1, gro_end, 8, 0, 90, 30, "Sunday groceries")

# ---------------------------------------------------------------------------
# 6. Tutorials — discrete occurrences on their specific weeks.
#    Torts : weeks 21, 23           (Fri 12:40-13:30)
#    Public: weeks 20,21,23,24      (Tue 16:40-17:30)
#    Crim  : weeks 21,22,23,24      (Mon 10:30-11:20)
# ---------------------------------------------------------------------------
def tut(weeknum, day_offset, hh, mm, dur_min, summary, desc):
    d = week_start[weeknum] + datetime.timedelta(days=day_offset)
    emit_once(summary, d, hh, mm, dur_min, 10, desc)

for w in [21, 23]:
    tut(w, 4, 12, 40, 50, "Torts Tutorial", "LAWS212 Torts tutorial - week %d" % w)
for w in [20, 21, 23, 24]:
    tut(w, 1, 16, 40, 50, "Public Tutorial", "LAWS213 Public tutorial - week %d" % w)
for w in [21, 22, 23, 24]:
    tut(w, 0, 10, 30, 50, "Crim Tutorial", "LAWS214 Crim tutorial - week %d" % w)

# ---------------------------------------------------------------------------
# 7. Curious Citizen (public law) — week 23, Wed 30 Sep 20:30-21:30.
# ---------------------------------------------------------------------------
emit_once("Curious Citizen (public law)", datetime.date(2026, 9, 30), 20, 30, 60, 30,
          "Week 23 public-law task (flagged for the calendar system).")

lines.append("END:VCALENDAR")

ics = "\r\n".join(lines) + "\r\n"
out = r"C:\Users\asher\OneDrive\Documents\Second_Brain\Second_Brain\08_Resources\Calendar\Master Schedule.ics"
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write(ics)
print("Wrote", out)
print("Events:", sum(1 for l in lines if l == "BEGIN:VEVENT"))
