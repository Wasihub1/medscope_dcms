import { useEffect, useRef } from 'react';

/**
 * Prompt 10F: refetch a page's data when the user comes back to the window/tab, so changes made
 * elsewhere (a result saved in My Work, an order moved to another room) show without a manual
 * reload. Pages also fetch on mount, which covers navigation. Throttled to one call per 2 s.
 */
export function useRefetchOnFocus(refetch: () => void): void {
  const ref = useRef(refetch);
  const lastRun = useRef(0);
  useEffect(() => {
    ref.current = refetch;
  }, [refetch]);

  useEffect(() => {
    const run = () => {
      const now = Date.now();
      if (now - lastRun.current < 2000) return;
      lastRun.current = now;
      ref.current();
    };
    const onVisibility = () => {
      if (document.visibilityState === 'visible') run();
    };
    window.addEventListener('focus', run);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      window.removeEventListener('focus', run);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);
}
