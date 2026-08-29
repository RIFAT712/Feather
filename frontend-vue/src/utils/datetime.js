// Single source of truth for parsing and formatting the timestamps the API
// returns.
//
// Why this exists: the backend stores and serializes *naive* UTC datetimes, so
// `/api/contests` hands back strings like "2026-08-01T00:00:00" with no
// trailing "Z". `new Date("2026-08-01T00:00:00")` is specified to parse a
// date-time without an offset as LOCAL time, so every one of those strings was
// silently shifted by the viewer's UTC offset. Some views worked around it by
// concatenating a "Z" before parsing and some didn't, and a few did it
// unconditionally (double-"Z" -> Invalid Date). The result was that, on a
// Bangladesh clock, AdminDashboard's contest status/progress bar,
// ContestDashboard's active check and countdown, ContestLayout's date range,
// ActivityLog's timestamps and ReviewQueue's creation date were all six hours
// out, while the formatDate() right next to them was correct.
//
// dayjs's utc plugin parses an offset-less string as UTC explicitly, which
// removes the whole class of bug -- and its timezone plugin replaces the
// hand-rolled `new Date(t.getTime() + 6 * 60 * 60 * 1000)` arithmetic that
// AdminDashboard and ContestConfig used to convert to Bangladesh time.
//
// Display convention is unchanged: everything renders in the *viewer's* local
// timezone, exactly as toLocaleDateString/toLocaleString did before. Only the
// contest date/time editors work in Bangladesh time, because that is what
// their inputs are labelled as.
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc.js';
import timezone from 'dayjs/plugin/timezone.js';

dayjs.extend(utc);
dayjs.extend(timezone);

// Bengali Wiktionary contests are scheduled in Bangladesh Standard Time.
// Named rather than hardcoded as +06:00 so the tz database stays authoritative.
export const CONTEST_TZ = 'Asia/Dhaka';

/**
 * Parse an API timestamp as UTC, tolerating both "…T00:00:00" and "…T00:00:00Z".
 * Returns a dayjs object in the viewer's local zone, or null for empty input.
 */
export function parseApiDate(value) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = dayjs.utc(String(value));
  return parsed.isValid() ? parsed.local() : null;
}

/** Native Date for the arithmetic that still wants one (countdowns, progress). */
export function toDate(value) {
  const parsed = parseApiDate(value);
  return parsed ? parsed.toDate() : null;
}

/** "Aug 1, 2026" — matches the old toLocaleDateString('en-US', {month:'short',…}). */
export function formatDate(value, fallback = '—') {
  const parsed = parseApiDate(value);
  return parsed ? parsed.format('MMM D, YYYY') : fallback;
}

/** "August 1, 2026" — the long form ContestDashboard's header uses. */
export function formatDateLong(value, fallback = '—') {
  const parsed = parseApiDate(value);
  return parsed ? parsed.format('MMMM D, YYYY') : fallback;
}

/** "01 Aug 2026" — the en-GB day-first form ReviewQueue shows. */
export function formatDateDayFirst(value, fallback = '—') {
  const parsed = parseApiDate(value);
  return parsed ? parsed.format('DD MMM YYYY') : fallback;
}

/** "Aug 1, 2026, 09:30" — date plus 24h time. */
export function formatDateTime(value, fallback = '—') {
  const parsed = parseApiDate(value);
  return parsed ? parsed.format('MMM D, YYYY, HH:mm') : fallback;
}

/** "01 Aug 2026, 09:30" — the en-GB variant ActivityLog and the log table use. */
export function formatDateTimeDayFirst(value, fallback = '—') {
  const parsed = parseApiDate(value);
  return parsed ? parsed.format('DD MMM YYYY, HH:mm') : fallback;
}

/** True while `now` falls inside [start, end]. */
export function isWithinWindow(start, end, now = dayjs()) {
  const from = parseApiDate(start);
  const to = parseApiDate(end);
  if (!from || !to) return false;
  return !now.isBefore(from) && !now.isAfter(to);
}

/** 'upcoming' | 'active' | 'ended' for a contest's date window. */
export function windowStatus(start, end, now = dayjs()) {
  const from = parseApiDate(start);
  const to = parseApiDate(end);
  if (!from || !to) return 'upcoming';
  if (now.isBefore(from)) return 'upcoming';
  if (now.isAfter(to)) return 'ended';
  return 'active';
}

/** Percentage elapsed through a contest window, clamped to 0–100. */
export function windowProgress(start, end, now = dayjs()) {
  const from = parseApiDate(start);
  const to = parseApiDate(end);
  if (!from || !to) return 0;
  const span = to.valueOf() - from.valueOf();
  if (span <= 0) return 100;
  const elapsed = now.valueOf() - from.valueOf();
  if (elapsed <= 0) return 0;
  if (elapsed >= span) return 100;
  return Math.round((elapsed / span) * 100);
}

/**
 * Contest editors: a date ("2026-08-01") plus a time ("09:30") entered in
 * Bangladesh time -> the UTC ISO string the API stores.
 */
export function contestTimeToUtcIso(date, time) {
  return dayjs.tz(`${date} ${time || '00:00'}`, CONTEST_TZ).utc().toISOString();
}

/**
 * The inverse: a stored UTC timestamp -> the { date, time } pair the contest
 * editors' inputs bind to, in Bangladesh time.
 */
export function utcToContestTimeParts(value) {
  const parsed = value ? dayjs.utc(String(value)) : null;
  if (!parsed || !parsed.isValid()) return { date: '', time: '' };
  const local = parsed.tz(CONTEST_TZ);
  return { date: local.format('YYYY-MM-DD'), time: local.format('HH:mm') };
}

export { dayjs };
