import React from 'react';

export default function PublicationYearRange({ years, value, onChange }) {
  const id = React.useId();
  const min = years[0];
  const max = years[years.length - 1];
  const [start, end] = value || [min, max];
  return <fieldset className="de-year-range">
    <legend>PUBLICATION YEAR</legend>
    <label className="de-all-years"><input type="checkbox" checked={!value} disabled={!years.length}
      onChange={e => onChange(e.target.checked ? null : [min, max])} /> All years</label>
    {years.length ? <div className="de-year-inputs">
      <label htmlFor={`${id}-start`}>Start Year <output>{start}</output><input id={`${id}-start`} type="range" min={min} max={max} value={start}
        disabled={min === max} onChange={e => onChange([Math.min(Number(e.target.value), end), end])} /></label>
      <label htmlFor={`${id}-end`}>End Year <output>{end}</output><input id={`${id}-end`} type="range" min={min} max={max} value={end}
        disabled={min === max} onChange={e => onChange([start, Math.max(Number(e.target.value), start)])} /></label>
    </div> : <small>No publication years available</small>}
  </fieldset>;
}
