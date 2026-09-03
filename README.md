# Schedule Calendar (iCal feed)

Hosts the Master Schedule as an iCal feed so it can be auto-synced to Google Calendar.

- **`Master Schedule.ics`** — the iCal file. Subscribe to this URL in Google Calendar ("From URL").
- **`gen_calendar.py`** — generates `Master Schedule.ics` from the schedule definitions.

## Public feed URL

The feed is served by GitHub Pages at:

```
https://asherhovell-png.github.io/schedule-calendar/Master%20Schedule.ics
```

(URL-encoded space for `Master Schedule.ics`.)

## How to update

1. Edit `gen_calendar.py` (or regenerate `Master Schedule.ics` from the vault).
2. Commit and push to `main`.
3. GitHub Pages serves the new file; Google Calendar picks it up within ~24h (polling).

> Important: the `.ics` is private-ish but GitHub Pages for a private repo requires the repo to be accessible — if the feed stops working, the repo may have been made public or Pages disabled.