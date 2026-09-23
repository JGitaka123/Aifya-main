"use client";

import { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="flex flex-col items-center justify-center min-h-[40vh] text-center p-8">
            <div className="bg-red-50 border border-red-200 rounded-xl p-8 max-w-md">
              <h2 className="text-xl font-semibold text-red-700 mb-2">Something went wrong</h2>
              <p className="text-red-600 text-sm mb-4">
                {this.state.error?.message || "An unexpected error occurred."}
              </p>
              <button
                onClick={() => this.setState({ hasError: false, error: null })}
                className="px-4 py-2 bg-red-600 text-white rounded-md text-sm hover:bg-red-700"
              >
                Try Again
              </button>
            </div>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
