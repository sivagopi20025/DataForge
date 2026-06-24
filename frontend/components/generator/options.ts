import { Banknote, Building2, HeartPulse, Landmark, PackageCheck, ShoppingCart } from "lucide-react";
import type React from "react";
import type { Domain, LoadType, OutputFormat } from "@/types/api";

export const domains: { id: Domain; name: string; description: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "retail", name: "Retail", description: "Customers, orders, products, payments, and reviews.", icon: ShoppingCart },
  { id: "healthcare", name: "Healthcare", description: "Patients, visits, claims, diagnoses, and payments.", icon: HeartPulse },
  { id: "finance", name: "Finance", description: "Accounts, trades, portfolios, risk, and reconciliations.", icon: Banknote },
  { id: "insurance", name: "Insurance", description: "Policies, claims, coverages, agents, and settlements.", icon: Building2 },
  { id: "logistics", name: "Logistics", description: "Warehouses, shipments, vehicles, drivers, and tracking.", icon: PackageCheck },
  { id: "banking", name: "Banking", description: "Customers, accounts, transactions, cards, and branches.", icon: Landmark },
];

export const loadTypes: { id: LoadType; name: string; description: string }[] = [
  { id: "bulk", name: "Bulk", description: "Full snapshot exports for baseline pipeline tests." },
  { id: "incremental", name: "Incremental", description: "Day-partitioned arrivals with late and updated rows." },
  { id: "delta", name: "Delta", description: "New, updated, and deleted records in one change set." },
  { id: "cdc", name: "CDC", description: "Insert, update, and delete event envelopes." },
  { id: "event_stream", name: "Event Stream", description: "Event-shaped datasets for streaming consumers." },
];

export const formats: { id: OutputFormat; name: string; description: string }[] = [
  { id: "csv", name: "CSV", description: "Simple tabular exports." },
  { id: "json", name: "JSON", description: "API and document-style exports." },
  { id: "parquet", name: "Parquet", description: "Columnar analytics files." },
];

export const recordCounts = [
  { label: "1K", value: 1000 },
  { label: "10K", value: 10000 },
  { label: "100K", value: 100000 },
  { label: "500K", value: 500000 },
];

export const issueLabels: Record<string, string> = {
  null_values: "Nulls",
  duplicate_records: "Duplicates",
  schema_drift: "Schema Drift",
  invalid_dates: "Invalid Dates",
  negative_values: "Negative Values",
  foreign_key_break: "Foreign Key Breaks",
};
