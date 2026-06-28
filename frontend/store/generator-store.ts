"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Domain, LoadType, OutputFormat } from "@/types/api";

export type IssueConfig = { enabled: boolean; percentage: number };

type GeneratorState = {
  domain: Domain;
  loadType: LoadType;
  format: OutputFormat;
  records: number;
  selectedTables: string[];
  issues: Record<string, IssueConfig>;
  setDomain: (domain: Domain) => void;
  setLoadType: (loadType: LoadType) => void;
  setFormat: (format: OutputFormat) => void;
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
      records: 1000,
      selectedTables: [],
      issues: defaultIssues,
      setDomain: (domain) => set({ domain, selectedTables: [] }),
      setLoadType: (loadType) => set({ loadType }),
      setFormat: (format) => set({ format }),
      setRecords: (records) => set({ records: Math.min(500_000, Math.max(1, Math.floor(records))) }),
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
      version: 2,
      migrate: (persisted) => ({ ...(persisted as GeneratorState), selectedTables: [] }),
    },
  ),
);
