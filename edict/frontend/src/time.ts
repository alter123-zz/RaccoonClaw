const BEIJING_TIME_ZONE = 'Asia/Shanghai';
const BEIJING_OFFSET = '+08:00';
const HAS_TIME_ZONE_RE = /(Z|[+-]\d{2}:\d{2})$/i;
const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/;
const SPACE_DATETIME_RE = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/;
const ISO_NO_ZONE_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/;

type TimeValue = string | number | Date | null | undefined;

type DateTimeParts = {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
  second: string;
};

function normalizeTimeString(value: string): string {
  const raw = value.trim();
  if (!raw) return raw;

  if (DATE_ONLY_RE.test(raw)) {
    return `${raw}T00:00:00${BEIJING_OFFSET}`;
  }

  if (SPACE_DATETIME_RE.test(raw)) {
    return `${raw.replace(' ', 'T')}${BEIJING_OFFSET}`;
  }

  if (ISO_NO_ZONE_RE.test(raw) && !HAS_TIME_ZONE_RE.test(raw)) {
    return `${raw}${BEIJING_OFFSET}`;
  }

  return raw;
}

export function parseTimeValue(value: TimeValue): Date | null {
  if (value == null || value === '') return null;

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }

  if (typeof value === 'number') {
    const ms = value > 1e12 ? value : value * 1000;
    const date = new Date(ms);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  const normalized = normalizeTimeString(value);
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

function extractParts(value: TimeValue): DateTimeParts | null {
  const date = parseTimeValue(value);
  if (!date) return null;

  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: BEIJING_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date);

  const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return {
    year: lookup.year || '',
    month: lookup.month || '',
    day: lookup.day || '',
    hour: lookup.hour || '00',
    minute: lookup.minute || '00',
    second: lookup.second || '00',
  };
}

export function formatBeijingDate(value: TimeValue): string {
  const parts = extractParts(value);
  if (!parts) return typeof value === 'string' ? value : '';
  return `${parts.year}-${parts.month}-${parts.day}`;
}

export function formatBeijingDateTime(
  value: TimeValue,
  options: { includeYear?: boolean; includeSeconds?: boolean } = {},
): string {
  const parts = extractParts(value);
  if (!parts) return typeof value === 'string' ? value : '';

  const includeYear = options.includeYear !== false;
  const includeSeconds = options.includeSeconds !== false;
  const datePart = includeYear
    ? `${parts.year}-${parts.month}-${parts.day}`
    : `${parts.month}-${parts.day}`;
  const timePart = includeSeconds
    ? `${parts.hour}:${parts.minute}:${parts.second}`
    : `${parts.hour}:${parts.minute}`;
  return `${datePart} ${timePart}`;
}

export function formatBeijingShortDateTime(value: TimeValue): string {
  return formatBeijingDateTime(value, { includeYear: false, includeSeconds: false });
}

export function formatBeijingTime(
  value: TimeValue,
  options: { includeSeconds?: boolean } = {},
): string {
  const parts = extractParts(value);
  if (!parts) return typeof value === 'string' ? value : '';
  return options.includeSeconds === false
    ? `${parts.hour}:${parts.minute}`
    : `${parts.hour}:${parts.minute}:${parts.second}`;
}

export function formatBeijingChineseDate(value: TimeValue, withWeekday = false): string {
  const parts = extractParts(value);
  if (!parts) return typeof value === 'string' ? value : '';

  const dateText = `${Number(parts.year)}年${Number(parts.month)}月${Number(parts.day)}日`;
  if (!withWeekday) return dateText;

  const date = parseTimeValue(value);
  if (!date) return dateText;

  const weekday = new Intl.DateTimeFormat('zh-CN', {
    timeZone: BEIJING_TIME_ZONE,
    weekday: 'short',
  }).format(date);
  return `${dateText} · ${weekday}`;
}

export function beijingTodayKey(): string {
  return formatBeijingDate(new Date());
}

export { BEIJING_TIME_ZONE };
