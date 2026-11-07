// How decimal values -- indexes, scores, adjusted citations, weights, averages
// -- are shown everywhere: on the pages, in chart tooltips and in the exported
// PDF and CSV files. At most MAX_DECIMALS decimals, without padding zeros
// (77.1234 -> 77.123, 1.5 -> 1.5, 2 -> 2). Change it here to change it
// everywhere.
export const MAX_DECIMALS = 3;

// en-US for a '.' decimal point whatever the visitor's language; no
// thousands separators, as the whole numbers on the pages have none.
const decimal = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: MAX_DECIMALS,
  useGrouping: false,
});

/** A number as shown in the app; '—' when there is no number. */
export function formatDecimal(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  const text = decimal.format(number);
  return text === '-0' ? '0' : text; // e.g. -0.0001
}

// For Recharts' <Tooltip formatter={...}>: rounds the numbers, leaves text alone.
export const formatTooltipValue = (value) => (typeof value === 'number' ? formatDecimal(value) : value);
