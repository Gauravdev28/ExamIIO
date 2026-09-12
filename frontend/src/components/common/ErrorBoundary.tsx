import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, LayoutDashboard } from 'lucide-react';
import { Button } from './Button';
import { Card } from './Card';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  public handleReset = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-[50vh] flex items-center justify-center p-6">
          <Card className="max-w-lg w-full bg-white border border-rose-200 shadow-lg p-6 space-y-4 text-center">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center mx-auto border border-rose-200">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h2 className="text-base font-bold text-slate-900">
                {this.props.fallbackTitle || 'Something went wrong loading this component'}
              </h2>
              <p className="text-xs text-slate-500">
                An unexpected rendering error occurred. The application shell remains active.
              </p>
              {this.state.error && (
                <div className="mt-3 p-3 bg-slate-50 rounded-xl border border-slate-200 text-left font-mono text-[11px] text-rose-700 max-h-32 overflow-y-auto break-all">
                  {this.state.error.message || String(this.state.error)}
                </div>
              )}
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={this.handleReset}
                className="flex items-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Retry
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  window.location.href = '/admin';
                }}
                className="flex items-center gap-1.5"
              >
                <LayoutDashboard className="w-3.5 h-3.5" />
                Back to Dashboard
              </Button>
            </div>
          </Card>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
