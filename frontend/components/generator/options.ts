import { Banknote, Building2, Factory, GraduationCap, HeartPulse, Landmark, PackageCheck, RadioTower, ShoppingBag, ShoppingCart } from "lucide-react";
import type React from "react";
import type { DatabaseType, Domain, LoadType, OutputFormat } from "@/types/api";

export const domains: { id: Domain; name: string; description: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "retail", name: "Retail", description: "Customers, orders, products, payments, and reviews.", icon: ShoppingCart },
  { id: "healthcare", name: "Healthcare", description: "Patients, visits, claims, diagnoses, and payments.", icon: HeartPulse },
  { id: "finance", name: "Finance", description: "Accounts, trades, portfolios, risk, and reconciliations.", icon: Banknote },
  { id: "insurance", name: "Insurance", description: "Policies, claims, coverages, agents, and settlements.", icon: Building2 },
  { id: "logistics", name: "Logistics", description: "Warehouses, shipments, vehicles, drivers, and tracking.", icon: PackageCheck },
  { id: "banking", name: "Banking", description: "Customers, accounts, transactions, cards, and branches.", icon: Landmark },
  { id: "manufacturing", name: "Manufacturing", description: "Factories, production lines, machines, batches, defects, and inventory.", icon: Factory },
  { id: "telecommunications", name: "Telecommunications", description: "Customers, subscriptions, CDRs, SMS, data sessions, towers, billing, and support.", icon: RadioTower },
  { id: "education", name: "Education", description: "Institutions, campuses, programs, students, enrollments, attendance, grades, and fee payments.", icon: GraduationCap },
  { id: "ecommerce", name: "E-commerce Marketplace", description: "Customers, sellers, stores, listings, carts, orders, payments, shipments, returns, and reviews.", icon: ShoppingBag },
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
  { id: "database", name: "Database", description: "Download a database-specific DDL ZIP package." },
];

export const databaseTypes: { id: DatabaseType; name: string; description: string }[] = [
  { id: "postgresql", name: "PostgreSQL", description: "DDL package with CREATE SCHEMA, BOOLEAN, NUMERIC, and TIMESTAMP syntax." },
  { id: "mssql", name: "Microsoft SQL Server", description: "DDL package with SQL Server schema, NVARCHAR, BIT, and DATETIME2 syntax." },
  { id: "mysql", name: "MySQL", description: "DDL package with CREATE DATABASE, VARCHAR, BOOLEAN, and DATETIME syntax." },
];

export const recordCounts = [
  { label: "Empty schema — 0", value: 0, description: "Generate schema-only empty files with headers/schema and zero data rows." },
  { label: "Sample — 100", value: 100, description: "Tiny sample for quick previews and smoke tests." },
  { label: "Development — 10,000", value: 10000, description: "Developer-sized data for local pipelines and notebooks." },
  { label: "Performance — 100,000", value: 100000, description: "Larger performance run for validation and pipeline load tests." },
  { label: "Performance+ — 500,000", value: 500000, description: "Current maximum for heavier local performance testing." },
];

export const issueLabels: Record<string, string> = {
  null_values: "Nulls",
  duplicate_records: "Duplicates",
  schema_drift: "Schema Drift",
  invalid_dates: "Invalid Dates",
  negative_values: "Negative Values",
  foreign_key_break: "Foreign Key Breaks",
};
