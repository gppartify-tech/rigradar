import { useCallback, useEffect, useState } from "react";

// The PC builder keeps the chosen part ids in localStorage: { cpu: 12, gpu: 40, ... }
const KEY = "partify_build";
const EVENT = "build:change";

function read() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || {};
  } catch {
    return {};
  }
}

function write(build) {
  try {
    localStorage.setItem(KEY, JSON.stringify(build));
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event(EVENT));
}

export function setBuildParts(parts) {
  write(parts);
}

export function useBuild() {
  const [build, setBuild] = useState(read);

  useEffect(() => {
    const sync = () => setBuild(read());
    window.addEventListener(EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const setPart = useCallback((category, productId) => write({ ...read(), [category]: productId }), []);
  const removePart = useCallback((category) => {
    const next = { ...read() };
    delete next[category];
    write(next);
  }, []);
  const clear = useCallback(() => write({}), []);

  return { build, setPart, removePart, clear, replace: write };
}
