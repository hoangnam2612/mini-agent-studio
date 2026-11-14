import { useCallback, useEffect, useState } from "react";
import { storage } from "../lib/format";

// Giao diện sáng/tối: "auto" (theo hệ điều hành) | "light" | "dark". Lưu ở localStorage.
// index.html có script nhỏ áp theme trước khi React chạy để tránh nháy màu.

const KEY = "vin15_theme";

export function applyTheme(mode) {
  const root = document.documentElement;
  if (mode === "light" || mode === "dark") root.dataset.theme = mode;
  else delete root.dataset.theme;
}

export function useTheme() {
  const [mode, setMode] = useState(() => storage("get", KEY) || "auto");
  useEffect(() => { applyTheme(mode); }, [mode]);
  const change = useCallback((m) => {
    setMode(m);
    if (m === "auto") storage("del", KEY); else storage("set", KEY, m);
  }, []);
  return [mode, change];
}
