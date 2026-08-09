"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { DatabaseType, Domain, LoadType, OutputFormat } from "@/types/api";

export type IssueConfig = { enabled: boolean; percentage: number };

type GeneratorState = {
  domain: Domain;
  loadType: LoadType;
  format: OutputFormat;
  databaseType: DatabaseType;
  records: number;
  selectedTables: string[];
  issues: Record<string, IssueConfig>;
  setDomain: (domain: Domain) => void;
  setLoadType: (loadType: LoadType) => void;
  setFormat: (format: OutputFormat) => void;
  setDatabaseType: (databaseType: DatabaseType) => void;
  setRecords: (records: number) => void;
  setSelectedTables: (tables: string[]) => void;
  toggleIssue: (issue: string) => void;
  setIssuePercentage: (issue: string, percentage: number) => void;
};

const defaultIssues: Record<string, IssueConfig> = {
  null_values: { enabled: false, percentage: 2 },
  duplicate_records: { enabled: false, percentage: 2 },
  schema_drift: { enabled: false, percentage: 1 },
  invalid_dates: { enabled: false, percentage: 2 },
  negative_values: { enabled: false, percentage: 1 },
  foreign_key_break: { enabled: false, percentage: 1 },
};

export const useGeneratorStore = create<GeneratorState>()(
  persist(
    (set) => ({
      domain: "retail",
      loadType: "bulk",
      format: "csv",
      databaseType: "postgresql",
      records: 1000,
      selectedTables: [],
      issues: defaultIssues,
      setDomain: (domain) => set({ domain, selectedTables: [] }),
      setLoadType: (loadType) => set({ loadType }),
      setFormat: (format) => set({ format }),
      setDatabaseType: (databaseType) => set({ databaseType }),
      setRecords: (records) => set({ records: Math.min(500_000, Math.max(0, Math.floor(records))) }),
      setSelectedTables: (selectedTables) => set({ selectedTables }),
      toggleIssue: (issue) =>
        set((state) => ({
          issues: {
            ...state.issues,
            [issue]: { ...state.issues[issue], enabled: !state.issues[issue].enabled },
          },
        })),
      setIssuePercentage: (issue, percentage) =>
        set((state) => ({
          issues: {
            ...state.issues,
            [issue]: { ...state.issues[issue], percentage },
          },
        })),
    }),
    {
      name: "dataforge-generator",
      version: 4,
      migrate: (persisted) => ({ ...(persisted as GeneratorState), selectedTables: [] }),
    },
  ),
);
