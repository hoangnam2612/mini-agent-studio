// Bộ icon nét đường (stroke) dùng chung. Thêm icon mới: thêm 1 dòng vào PATHS.
const PATHS = {
  file: "M6 3h9l4 4v14H6zM14 3v5h5",
  notebook: "M4 5h16v14H4zM8 9h8M8 13h5",
  chat: "M4 5h16v11H9l-5 4z",
  book: "M5 4h11a3 3 0 013 3v13H8a3 3 0 01-3-3zM9 9h6",
  inbox: "M4 6h16M4 12h16M4 18h10",
  users: "M2.5 20c0-3.5 3-6 6.5-6s6.5 2.5 6.5 6M16 5a3.5 3.5 0 010 7M18 14c2.2.6 3.5 2.5 3.5 5M9 4.5a3.5 3.5 0 100 7 3.5 3.5 0 000-7z",
  flag: "M5 21V4M5 4h12l-2 4 2 4H5",
  settings: "M12 8.5a3.5 3.5 0 100 7 3.5 3.5 0 000-7zM4 12h2M18 12h2M12 4v2M12 18v2M6.3 6.3l1.4 1.4M16.3 16.3l1.4 1.4M6.3 17.7l1.4-1.4M16.3 7.7l1.4-1.4",
  bell: "M6 17V11a6 6 0 0112 0v6l2 2H4zM10 21h4",
  logout: "M9 4H5v16h4M16 8l4 4-4 4M20 12H9",
  check: "M5 12l4 4 10-10",
  alert: "M12 8v5M12 17h.01M12 3a9 9 0 100 18 9 9 0 000-18z",
  sparkle: "M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8z",
  cap: "M3 9l9-5 9 5-9 5-9-5zM7 11.5V16c0 1.2 2.2 3 5 3s5-1.8 5-3v-4.5",
  upload: "M12 16V4M7 9l5-5 5 5M5 20h14",
  sun: "M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z",
  monitor: "M3 5h18v11H3zM8 20h8M12 16v4",
  clip:"M8 12l5-5a3 3 0 014 4l-7 7a5 5 0 01-7-7l6-6",
};

export default function Icon({ name, size = 20, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      <path d={PATHS[name]} />
    </svg>
  );
}
