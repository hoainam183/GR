import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function parseUtcDate(dateStr: string): Date {
  if (!dateStr) return new Date();
  
  let parsedStr = dateStr.trim();
  // If it's a naive ISO string without timezone info (no Z, no +/- offset), append Z to treat as UTC
  if (!parsedStr.endsWith('Z') && !/[+-]\d{2}:?\d{2}$/.test(parsedStr)) {
    // Some backend timestamps use space instead of T for separation
    parsedStr = parsedStr.replace(' ', 'T');
    parsedStr += 'Z';
  }
  
  return new Date(parsedStr);
}
