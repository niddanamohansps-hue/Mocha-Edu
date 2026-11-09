import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { apiBaseUrl } from "./apiBase"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function getMediaUrl(path: string | null | undefined) {
  if (!path) return null;
  if (path.startsWith("http") || path.startsWith("blob:")) return path;

  // Files must come from the school's own host: the backend finds the school from the host name, and a plain
  // "localhost" is the platform site, which has no media route (the browser then blocks the reply as "not an image").
  const baseUrl = apiBaseUrl().replace(/\/api$/, '');

  // Ensure path starts with /
  const cleanPath = path.startsWith('/') ? path : `/${path}`;

  return `${baseUrl}${cleanPath}`;
}
