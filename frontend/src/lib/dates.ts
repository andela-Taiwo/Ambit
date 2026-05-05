/** Date helpers that stay in the user's local calendar, never UTC-shifted. */

const pad = (value: number): string => String(value).padStart(2, '0');

export const toLocalIso = (date: Date): string =>
  `${String(date.getFullYear())}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

export const todayIso = (): string => toLocalIso(new Date());

export const parseLocalDate = (iso: string): Date => {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1);
};

export const formatDate = (iso: string): string =>
  new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(parseLocalDate(iso));

export const formatDateTime = (iso: string): string =>
  new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso));

export const currentMonth = (): string => todayIso().slice(0, 7);

export const monthStartIso = (month: string): string => `${month}-01`;

export const monthLabel = (month: string): string => {
  const [year, monthNumber] = month.split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', {
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(year ?? 1970, (monthNumber ?? 1) - 1, 1)));
};

export const addMonthsToMonth = (month: string, delta: number): string => {
  const [year, monthNumber] = month.split('-').map(Number);
  const index = (year ?? 1970) * 12 + ((monthNumber ?? 1) - 1) + delta;
  const nextYear = Math.floor(index / 12);
  const nextMonth = (index % 12) + 1;
  return `${String(nextYear).padStart(4, '0')}-${pad(nextMonth)}`;
};

export const nextMonthStartIso = (month: string): string =>
  monthStartIso(addMonthsToMonth(month, 1));
