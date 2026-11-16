import { useEffect, useRef } from "react";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export function useJobEvents<T extends { status: string }>(
  path: string | null,
  onEvent: (payload: T) => void,
) {
  const callback = useRef(onEvent);
  callback.current = onEvent;

  useEffect(() => {
    if (!path) return undefined;
    const source = new EventSource(path);
    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as T;
        callback.current(payload);
        if (TERMINAL.has(payload.status)) source.close();
      } catch {
        source.close();
      }
    };
    return () => source.close();
  }, [path]);
}
