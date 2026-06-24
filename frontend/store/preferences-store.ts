"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Domain, LoadType, OutputFormat } from "@/types/api";

type PreferencesState = {
  defaultDomain: Domain;
  defaultLoadType: LoadType;
  defaultFormat: OutputFormat;
  preferredRecordCount: number;
  recentDomains: Domain[];
  theme: "system" | "light" | "dark";
  notifications: boolean;
  exportManifest: boolean;
  apiEndpoint: string;
  setPreference: <K extends keyof PreferencesState>(key: K, value: PreferencesState[K]) => void;
  addRecentDomain: (domain: Domain) => void;
};

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      defaultDomain: "retail",
      defaultLoadType: "bulk",
      defaultFormat: "csv",
      preferredRecordCount: 10000,
      recentDomains: ["retail"],
      theme: "system",
      notifications: true,
      exportManifest: true,
      apiEndpoint: process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010",
      setPreference: (key, value) => set({ [key]: value } as Partial<PreferencesState>),
      addRecentDomain: (domain) =>
        set((state) => ({ recentDomains: [domain, ...state.recentDomains.filter((item) => item !== domain)].slice(0, 5) })),
    }),
    { name: "dataforge-preferences" },
  ),
);
