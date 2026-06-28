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

export function estimateSize(records: number, tables: number | string[], format: string, domain?: string) {
  const selectedTables = Array.isArray(tables) ? tables : [];
  const tableCount = Array.isArray(tables) ? tables.length : tables;

  if (tableCount === 0) {
    return 0;
  }

  if (domain === "healthcare" && selectedTables.length) {
    const rowCount = selectedTables.reduce((total, table) => total + estimateHealthcareRows(records, table), 0);
    const bytesPerRow = format === "json" ? 911 : format === "parquet" ? 95 : 372;
    return Math.max(0.1, (rowCount * bytesPerRow) / (1024 * 1024));
  }

  const multiplier = format === "parquet" ? 0.00018 : format === "json" ? 0.00075 : 0.00042;
  return Math.max(0.1, records * Math.max(tableCount, 1) * multiplier);
}

function estimateHealthcareRows(records: number, table: string) {
  switch (table) {
    case "patients":
      return Math.min(75_000, Math.max(100, Math.floor(records * 0.2)));
    case "providers":
      return Math.min(5_000, Math.max(20, Math.floor(records * 0.01)));
    case "visits":
    case "diagnoses":
    case "procedures":
    case "claims":
    case "payments":
      return records;
    default:
      return records;
  }
}
