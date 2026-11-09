import { useEffect } from "react";

/** Re-run `refetch` whenever the browser tab/window regains focus, so changes
 * made on another page (or another tab) show up. Pages already load on mount,
 * and each route mounts fresh, so opening a page also refetches. */
export function useRefetchOnFocus(refetch: () => unknown) {
  useEffect(() => {
    const onFocus = () => {
      try {
        Promise.resolve(refetch()).catch(() => {});
      } catch {
        /* ignore: the page shows its own load errors */
      }
    };
    const onVisible = () => {
      if (document.visibilityState === "visible") onFocus();
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refetch]);
}
