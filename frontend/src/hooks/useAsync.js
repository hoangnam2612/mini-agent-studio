import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Tải dữ liệu bất đồng bộ.
 *   const { data, error, loading, reload } = useAsync(() => api("GET", "/x"), [dep]);
 * `reload()` gọi lại (dùng sau khi ghi dữ liệu). Chỉ lần tải đầu hiện `loading`.
 */
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const seq = useRef(0);

  const load = useCallback(async () => {
    const id = ++seq.current;
    try {
      const data = await fnRef.current();
      if (id === seq.current) setState({ data, error: null, loading: false });
    } catch (error) {
      if (id === seq.current) setState((s) => ({ ...s, error, loading: false }));
    }
  }, []);

  useEffect(() => {
    setState((s) => ({ ...s, loading: true }));
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { ...state, reload: load };
}
