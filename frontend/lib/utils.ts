import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function titleCase(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\w\S*/g, (word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase());
}

export function formatNumber(value: number | undefined) {
  return new Intl.NumberFormat("en-US").format(value ?? 0);
}

export function estimateSize(records: number, tables: number, format: string) {
  const multiplier = format === "parquet" ? 0.00018 : format === "json" ? 0.00075 : 0.00042;
  return Math.max(0.1, records * Math.max(tables, 1) * multiplier);
}
