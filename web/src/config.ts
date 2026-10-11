/** Backend base URL; override with VITE_API_BASE. */
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) || "http://127.0.0.1:8099";
