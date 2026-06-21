import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";

interface Props { children: ReactNode; }
interface State { error: Error | null; }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(_error: Error, info: ErrorInfo) {
    console.error("Uncaught render error:", info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen gap-4 text-center px-4">
          <p className="text-red-500 font-medium">Something went wrong.</p>
          <p className="text-muted text-sm">{this.state.error.message}</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="text-sm text-accent hover:underline"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
