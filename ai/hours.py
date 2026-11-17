"""
Read a shop's free-text opening hours, such as "Mon-Fri 7am-6pm; Sat 9am-2pm".

Understood: day ranges (Mon-Fri), single days, comma lists of days (Mon, Wed, Fri),
times like 7am, 7:30am, 6pm or 18:00, a dash or "to" between the two times, and
several segments separated by ";" or ",". Anything else gives None: the parser
never guesses. Closing after midnight ("6pm-2am") is not understood either.
"""

import re

_DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
_DAY = r'(?:mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)'
_SEP = r'\s*(?:-|to)\s*'
_DAY_SPEC = rf'{_DAY}(?:{_SEP}{_DAY})?'
_TIME = r'\d{1,2}(?::\d{2})?\s*(?:am|pm)?'
_SEGMENT = rf'({_DAY_SPEC}(?:\s*,\s*{_DAY_SPEC})*)\s+({_TIME}){_SEP}({_TIME})'     # groups: days, start, end
_WHOLE = re.compile(rf'{_SEGMENT}(?:\s*[;,]\s*{_SEGMENT})*')


def _minute(text):
    """'7am' -> 420, '18:00' -> 1080. None for a bare '7' (am or pm?) or an impossible time."""
    hour, minute, half = re.fullmatch(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text).groups()
    hour, minute = int(hour), int(minute or 0)
    if minute > 59:
        return None
    if half:
        if not 1 <= hour <= 12:
            return None
        return (hour % 12 + (12 if half == 'pm' else 0)) * 60 + minute
    if ':' not in text or hour > 23:
        return None
    return hour * 60 + minute


def _weekdays(text):
    """'mon-wed, fri' -> [0, 1, 2, 4]. A range may wrap past Sunday (sat-mon)."""
    days = []
    for spec in text.split(','):
        ends = [_DAYS.index(name[:3]) for name in re.findall(_DAY, spec)]
        first, last = ends[0], ends[-1]
        days += [(first + i) % 7 for i in range((last - first) % 7 + 1)]
    return days


def parse_hours(text):
    """{weekday 0-6 (Monday is 0): [(start_minute, end_minute), ...]}, or None when not understood."""
    text = text.strip().lower().replace('–', '-')
    if not _WHOLE.fullmatch(text):
        return None
    hours = {}
    for days, start, end in re.findall(_SEGMENT, text):
        start, end = _minute(start), _minute(end)
        if start is None or end is None or end <= start:
            return None
        for day in _weekdays(days):
            hours.setdefault(day, []).append((start, end))
    return hours


def open_minutes(hours):
    return sum(end - start for spans in hours.values() for start, end in spans)


def overlap_minutes(a, b):
    """Minutes per week when both shops are open."""
    return sum(max(0, min(a_end, b_end) - max(a_start, b_start))
               for day in a for a_start, a_end in a[day] for b_start, b_end in b.get(day, []))
