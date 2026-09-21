import React, { useEffect, useId, useRef, useState } from 'react';

export default function PublicationFilterHelp() {
  const [open, setOpen] = useState(false);
  const container = useRef(null);
  const trigger = useRef(null);
  const id = useId();

  useEffect(() => {
    if (!open) return undefined;
    const dismiss = event => {
      if (!container.current?.contains(event.target)) setOpen(false);
    };
    const escape = event => {
      if (event.key === 'Escape') {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener('pointerdown', dismiss);
    document.addEventListener('focusin', dismiss);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', dismiss);
      document.removeEventListener('focusin', dismiss);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  return <div className="de-filter-guide" ref={container}>
    <button type="button" ref={trigger} aria-expanded={open} aria-controls={id}
      onClick={() => setOpen(value => !value)}>
      <span aria-hidden="true">&#9432;</span> How these filters work
    </button>
    {open && <div className="de-filter-popover" id={id} role="region" aria-label="How these filters work">
      <dl>
        <dt>Field</dt><dd>Filters publications by research area.</dd>
        <dt>Publication Year</dt><dd>Includes both ends of the selected period. All years also includes papers with unknown years.</dd>
        <dt>Publication Impact</dt><dd>Uses normal citation counts: high is 10 or more, medium is 5 to below 10, low is above 0 to below 5, and uncited is 0.</dd>
        <dt>Author Contribution</dt><dd>Primary means first-listed; co-author means listed after first. Major means at least 25% contribution; minor means above 0% and below 25%. Roles can overlap. Papers without contribution weights remain visible under All contribution states.</dd>
        <dt>Citation Type</dt><dd>Includes papers with a positive count of the selected type. External citations are estimated as total minus self citations. Self and adjusted citations use the recorded values. All citations includes uncited papers.</dd>
      </dl>
      <button type="button" onClick={() => { setOpen(false); trigger.current?.focus(); }}>Close filter help</button>
    </div>}
  </div>;
}
