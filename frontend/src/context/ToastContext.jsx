import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";

// Toast + helper `run(fn, okMsg)`: chạy thao tác, báo thành công/lỗi, ném lại lỗi để caller dừng luồng.

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [message, setMessage] = useState("");
  const timer = useRef();

  const toast = useCallback((msg) => {
    setMessage(msg);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(""), 4000);
  }, []);

  const run = useCallback(async (fn, okMsg) => {
    try {
      const result = await fn();
      if (okMsg) toast(okMsg);
      return result;
    } catch (e) {
      toast(e.message);
      throw e;
    }
  }, [toast]);

  const value = useMemo(() => ({ toast, run }), [toast, run]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      {message && <div className="toast" role="status">{message}</div>}
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
