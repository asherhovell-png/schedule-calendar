#!/usr/bin/env python3
"""
Generate a Google-Calendar-importable .ics from the Master Schedule.
Regenerate any time the schedule changes, then re-import/replace into Google Calendar.

Conventions (see vault AGENTS.md routing rules):
  - Lectures/training recur weekly by weekday (RRULE).
  - Tutorials run only on specific weeks -> generated as discrete occurrences.
  - Gym is every other day (RRULE interval=2).
  - Times are floating local NZ time (no TZID) so Google uses the device local zone.
"""
import datetime
import uuid

# ---------------------------------------------------------------------------
# Academic week -> start (Monday) date mapping.
# Anchor: week 19 starts Mon 2026-08-31 (today is Thu 2026-09-03, week 19).
# ---------------------------------------------------------------------------
WEEK19_MON = datetime.date(2026, 8, 31)
week_start = {n: WEEK19_MON + datetime.timedelta(weeks=n - 19) for n in range(1, 25)}

def dt(y, m, d, hh, mm):
    return datetime.datetime(y, m, d, hh, mm)

def fmt(dt_):
    return dt_.strftime("%Y%m%dT%H%M%S")

def stamp():
    return datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")

# ---------------------------------------------------------------------------
# Event container
# ---------------------------------------------------------------------------
lines = []
lines.append("BEGIN:VCALENDAR")
lines.append("VERSION:2.0")
lines.append("PRODID:-//Second Brain//Master Schedule//EN")
lines.append("CALSCALE:GREGORIAN")
lines.append("METHOD:PUBLISH")

def alarm(minutes_before, repeat_minutes=0, repeat_count=0):
    """Return VALARM block lines."""
    a = []
    a.append("BEGIN:VALARM")
    a.append("ACTION:DISPLAY")
    a.append("DESCRIPTION:Reminder")
    a.append("TRIGGER:-PT%dM" % minutes_before)
    if repeat_minutes and repeat_count:
        a.append("REPEAT:%d" % repeat_count)
        a.append("DURATION:PT%dM" % repeat_minutes)
    a.append("END:VALARM")
    return a

def vevent(summary, start, end, rrule=None, reminder_minutes=10, desc=""):
    uid = str(uuid.uuid5(uuid.NAMESPACE_URL, "sb://" + summary + start.strftime("%Y%m%d%H%M")))
    lines.append("BEGIN:VEVENT")
    lines.append("UID:%s" % uid)
    lines.append("DTSTAMP:" + stamp())
    lines.append("DTSTART:%s" % fmt(start))
    lines.append("DTEND:%s" % fmt(end))
    lines.append("SUMMARY:%s" % summary)
    if desc:
        lines.append("DESCRIPTION:%s" % desc.replace("\n", "\\n"))
    lines.append("TRANSP:OPAQUE")
    if rrule:
        lines.append("RRULE:%s" % rrule)
    lines.extend(alarm(reminder_minutes))
    lines.append("END:VEVENT")

# ---------------------------------------------------------------------------
# 1. DAILY recurring
# ---------------------------------------------------------------------------
# Sleep every night 10pm -> 7am (transparent, no notification)
lines.append("BEGIN:VEVENT")
lines.append("UID:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "sb://Sleep")))
lines.append("DTSTAMP:" + stamp())
lines.append("DTSTART;VALUE=DATE-TIME:20260831T220000")
lines.append("DURATION:PT9H")
lines.append("SUMMARY:Sleep")
lines.append("TRANSP:TRANSPARENT")
lines.append("RRULE:FREQ=DAILY")
lines.append("END:VEVENT")

# ---------------------------------------------------------------------------
# 2. Gym every other day, 7:00-8:00am (early morning). Anchor on recent session 2026-09-03.
# ---------------------------------------------------------------------------
# Note: every-2nd-day with a fixed anchor drifts relative to weekdays. RRULE interval=2 keeps it.
lines.append("BEGIN:VEVENT")
lines.append("UID:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "sb://Gym")))
lines.append("DTSTAMP:" + stamp())
lines.append("DTSTART;VALUE=DATE-TIME:20260905T070000")
lines.append("DTEND;VALUE=DATE-TIME:20260905T080000")
lines.append("SUMMARY:Gym (full body)")
lines.append("TRANSP:OPAQUE")
lines.append("RRULE:FREQ=DAILY;INTERVAL=2")
lines.extend(alarm(30))
lines.append("END:VEVENT")

# Rest-day incline walk (the days BETWEEN gym days), 7:00-7:30am
lines.append("BEGIN:VEVENT")
lines.append("UID:" + str(uuid.uuid5(uuid.NAMESPACE_URL, "sb://InclineWalk")))
lines.append("DTSTAMP:" + stamp())
lines.append("DTSTART;VALUE=DATE-TIME:20260906T070000")
lines.append("DTEND;VALUE=DATE-TIME:20260906T073000")
lines.append("SUMMARY:Rest-day incline walk")
lines.append("TRANSP:OPAQUE")
lines.append("RRULE:FREQ=DAILY;INTERVAL=2")
lines.extend(alarm(15))
lines.append("END:VEVENT")

# ---------------------------------------------------------------------------
# 3. Weekly recurring (by weekday)
# ---------------------------------------------------------------------------
WEEKLY_MO = "FREQ=WEEKLY;BYDAY=MO;UNTIL=20261011T235959"
WEEKLY_TU = "FREQ=WEEKLY;BYDAY=TU;UNTIL=20261011T235959"
WEEKLY_WE = "FREQ=WEEKLY;BYDAY=WE;UNTIL=20261011T235959"
WEEKLY_TH = "FREQ=WEEKLY;BYDAY=TH;UNTIL=20261011T235959"
WEEKLY_FR = "FREQ=WEEKLY;BYDAY=FR;UNTIL=20261011T235959"
WEEKLY_SU = "FREQ=WEEKLY;BYDAY=SU"
# Muay Thai — only while in Wellington; leave after exams (~mid Nov 2026).
# If the user leaves Wellington before that, remove these (see Master Schedule note).
MARTIAL_MO = "FREQ=WEEKLY;BYDAY=MO;UNTIL=20261115T235959"
MARTIAL_WE = "FREQ=WEEKLY;BYDAY=WE;UNTIL=20261115T235959"

# --- Lectures (every week) ---
vevent("Crim Lecture",             dt(2026,8,31,16,10), dt(2026,8,31,17,30), WEEKLY_MO, reminder_minutes=10, desc="LAWS214 Crim lecture")
vevent("Torts Lecture",            dt(2026,9,1,11,0),   dt(2026,9,1,12,20),  WEEKLY_TU, reminder_minutes=10, desc="LAWS212 Torts lecture")
vevent("Public Lecture",           dt(2026,9,2,15,10),  dt(2026,9,2,16,30),  WEEKLY_WE, reminder_minutes=10, desc="LAWS213 Public lecture")
vevent("Torts Lecture",            dt(2026,9,3,11,0),   dt(2026,9,3,12,20),  WEEKLY_TH, reminder_minutes=10, desc="LAWS212 Torts lecture")
vevent("Crim Lecture",             dt(2026,9,3,16,10),  dt(2026,9,3,17,30),  WEEKLY_TH, reminder_minutes=10, desc="LAWS214 Crim lecture")
vevent("Public Lecture",           dt(2026,9,4,15,10),  dt(2026,9,4,16,30),  WEEKLY_FR, reminder_minutes=10, desc="LAWS213 Public lecture")

# --- Muay Thai (every week, from Training Schedule) ---
vevent("Muay Thai training",       dt(2026,8,31,18,30), dt(2026,8,31,19,30), MARTIAL_MO, reminder_minutes=30, desc="Wellington Thai Boxing")
vevent("Sparring",                 dt(2026,8,31,19,30), dt(2026,8,31,20,15), MARTIAL_MO, reminder_minutes=15, desc="Wellington Thai Boxing")
vevent("Muay Thai training",       dt(2026,9,2,18,30),  dt(2026,9,2,19,30),  MARTIAL_WE, reminder_minutes=30, desc="Wellington Thai Boxing")
vevent("Abs (~30 min)",            dt(2026,9,2,19,30),  dt(2026,9,2,20,0),   MARTIAL_WE, reminder_minutes=5,  desc="Post-training abs")

# --- Groceries (Sunday, before/after gym depending on the day) ---
vevent("Groceries",                dt(2026,9,6,8,0),    dt(2026,9,6,9,30),   WEEKLY_SU, reminder_minutes=30, desc="Sunday groceries")

# ---------------------------------------------------------------------------
# 4. Tutorials — discrete occurrences on their specific weeks
#    Torts  : weeks 21, 23  (Fri 12:40-1:30)
#    Public : weeks 20,21,23,24 (Tue 4:40-5:30)
#    Crim   : weeks 21,22,23,24 (Mon 10:30-11:20)
# ---------------------------------------------------------------------------
def on_date(weeknum, day_offset, hh, mm, hh2, mm2):
    d = week_start[weeknum] + datetime.timedelta(days=day_offset)  # Mon=0
    return datetime.datetime(d.year, d.month, d.day, hh, mm), datetime.datetime(d.year, d.month, d.day, hh2, mm2)

torts_tut_weeks = [21, 23]
public_tut_weeks = [20, 21, 23, 24]
crim_tut_weeks  = [21, 22, 23, 24]

for w in torts_tut_weeks:
    s, e = on_date(w, 4, 12, 40, 13, 30)      # Friday
    vevent("Torts Tutorial", s, e, None, reminder_minutes=10, desc="LAWS212 Torts tutorial - week %d" % w)
for w in public_tut_weeks:
    s, e = on_date(w, 1, 16, 40, 17, 30)       # Tuesday
    vevent("Public Tutorial", s, e, None, reminder_minutes=10, desc="LAWS213 Public tutorial - week %d" % w)
for w in crim_tut_weeks:
    s, e = on_date(w, 0, 10, 30, 11, 20)       # Monday
    vevent("Crim Tutorial", s, e, None, reminder_minutes=10, desc="LAWS214 Crim tutorial - week %d" % w)

# --- Curious Citizen (public law) — week 23, Wednesday evening ---
# Week 23 = Mon 28 Sep 2026, so Wednesday = 30 Sep. Evening after Muay Thai + dinner.
s, e = dt(2026,9,30,20,30), dt(2026,9,30,21,30)
vevent("Curious Citizen (public law)", s, e, None, reminder_minutes=30,
       desc="Week 23 public-law task (flagged for the calendar system).")

lines.append("END:VCALENDAR")

ics = "\r\n".join(lines) + "\r\n"
import sys
out = r"C:\Users\asher\OneDrive\Documents\Second_Brain\Second_Brain\08_Resources\Calendar\Master Schedule.ics"
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write(ics)
print("Wrote", out)
print("Events:", sum(1 for l in lines if l == "BEGIN:VEVENT"))
