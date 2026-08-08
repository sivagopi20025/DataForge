"use client";

import React from "react";
import { Button } from "@/components/ui/button";

export class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="m-8 rounded-3xl border border-border bg-card p-8">
          <h2 className="text-2xl font-semibold">Something went sideways.</h2>
          <p className="mt-2 text-muted-foreground">DataForge caught the UI error before it reached your workflow.</p>
          <Button className="mt-6" onClick={() => this.setState({ hasError: false })}>Try again</Button>
        </div>
      );
    }
    return this.props.children;
  }
}
