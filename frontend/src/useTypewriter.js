import { useEffect, useState } from 'react';

// Users with reduced motion get the finished text immediately -- never an
// animation they did not ask for.
const prefersReducedMotion = () =>
  typeof window !== 'undefined'
  && typeof window.matchMedia === 'function'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * Types `text` once, left to right, when `start` turns true.
 * Returns { shown, done } so callers can chain one line after another.
 */
export function useTypewriter(text, { start = true, speed = 34, startDelay = 0 } = {}) {
  const reduce = prefersReducedMotion();
  const [shown, setShown] = useState(reduce ? text : '');
  const [done, setDone] = useState(reduce);

  useEffect(() => {
    if (reduce) {
      setShown(text);
      setDone(true);
      return undefined;
    }
    if (!start) return undefined;

    let index = 0;
    let timer;
    const tick = () => {
      index += 1;
      setShown(text.slice(0, index));
      if (index < text.length) {
        timer = setTimeout(tick, speed);
      } else {
        setDone(true);
      }
    };
    timer = setTimeout(tick, startDelay);
    return () => clearTimeout(timer);
  }, [text, start, speed, startDelay, reduce]);

  return { shown, done };
}

/**
 * Cycles through `phrases`: type -> hold -> erase -> next.
 * Pass a stable array (module constant), not an inline literal.
 * When `start` goes false the current text is frozen rather than reset, so
 * focusing the input does not make the placeholder jump.
 */
export function useCyclingText(phrases, {
  start = true, typeSpeed = 52, eraseSpeed = 26, hold = 1900, gap = 280,
} = {}) {
  const reduce = prefersReducedMotion();
  const [shown, setShown] = useState(phrases[0]);

  useEffect(() => {
    if (reduce || !start) return undefined;

    let phrase = 0;
    let index = 0;
    let erasing = false;
    setShown('');

    let timer;
    const tick = () => {
      const full = phrases[phrase];
      if (!erasing) {
        index += 1;
        setShown(full.slice(0, index));
        if (index < full.length) timer = setTimeout(tick, typeSpeed);
        else { erasing = true; timer = setTimeout(tick, hold); }
      } else {
        index -= 1;
        setShown(full.slice(0, index));
        if (index > 0) timer = setTimeout(tick, eraseSpeed);
        else {
          erasing = false;
          phrase = (phrase + 1) % phrases.length;
          timer = setTimeout(tick, gap);
        }
      }
    };
    timer = setTimeout(tick, gap);
    return () => clearTimeout(timer);
  }, [phrases, start, typeSpeed, eraseSpeed, hold, gap, reduce]);

  return shown;
}
