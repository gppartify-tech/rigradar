import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

// Light / dark theme.
// - Until the visitor clicks the toggle, we follow the operating system's setting.
// - After a click the choice is remembered in localStorage.
// - Dark mode = the "dark" class on <html>; Tailwind's `dark:` variants key off it.
//   (index.html sets the class before the first paint, so there is no white flash.)
const KEY = "partify_theme";
const systemQuery = () => window.matchMedia("(prefers-color-scheme: dark)");

function storedChoice() {
  try {
    const value = localStorage.getItem(KEY);
    return value === "dark" || value === "light" ? value : null;
  } catch {
    return null; // private mode / blocked storage
  }
}

const ThemeContext = createContext({ isDark: false, toggle() {} });

export function ThemeProvider({ children }) {
  const [choice, setChoice] = useState(storedChoice); // null = follow the system
  const [systemDark, setSystemDark] = useState(() => systemQuery().matches);

  useEffect(() => {
    const query = systemQuery();
    const onChange = (event) => setSystemDark(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const isDark = choice ? choice === "dark" : systemDark;

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
  }, [isDark]);

  const toggle = useCallback(() => {
    const next = isDark ? "light" : "dark";
    setChoice(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* ignore */
    }
  }, [isDark]);

  const value = useMemo(() => ({ isDark, toggle }), [isDark, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  return useContext(ThemeContext);
}
