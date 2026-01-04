/**
 * Error boundary components for graceful error handling.
 */

/* eslint-disable react-refresh/only-export-components */

import { AlertCircle, RefreshCw, Home } from "lucide-react";
import { FallbackProps, ErrorBoundaryProps } from "react-error-boundary";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Props for error fallback customization.
 */
interface ErrorFallbackUIProps extends FallbackProps {
  title?: string;
  showHomeButton?: boolean;
}

/**
 * Full-page error fallback for route-level errors.
 * Displays a centered card with error details and recovery options.
 */
export function PageErrorFallback({
  error,
  resetErrorBoundary,
  title = "Something went wrong",
  showHomeButton = true,
}: ErrorFallbackUIProps) {
  return (
    <div className="flex min-h-[400px] items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-5 w-5" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error Details</AlertTitle>
            <AlertDescription>
              <p className="mb-2">{error.message}</p>
              {import.meta.env.DEV && error.stack && (
                <pre className="mt-2 max-h-32 overflow-auto rounded bg-muted p-2 text-xs">
                  {error.stack}
                </pre>
              )}
            </AlertDescription>
          </Alert>
          <p className="text-sm text-muted-foreground">
            An unexpected error occurred. You can try again or return to the
            home page.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={resetErrorBoundary} variant="default">
              <RefreshCw className="mr-2 h-4 w-4" />
              Try Again
            </Button>
            {showHomeButton && (
              <Button
                variant="outline"
                onClick={() => (window.location.href = "/")}
              >
                <Home className="mr-2 h-4 w-4" />
                Go Home
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

/**
 * Inline error fallback for component-level errors.
 * Displays a compact alert within the component's space.
 */
export function InlineErrorFallback({
  error,
  resetErrorBoundary,
}: FallbackProps) {
  return (
    <Alert variant="destructive" className="my-4">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Failed to load component</AlertTitle>
      <AlertDescription>
        <p className="mb-2">{error.message}</p>
        <Button onClick={resetErrorBoundary} variant="outline" size="sm">
          <RefreshCw className="mr-2 h-3 w-3" />
          Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}

/**
 * Error info type for the onError callback.
 * Matches the ErrorInfo type from react-error-boundary.
 */
type ErrorInfo = Parameters<NonNullable<ErrorBoundaryProps["onError"]>>[1];

/**
 * Global error handler for logging errors.
 * Can be extended to send errors to a monitoring service.
 */
export function logError(error: Error, info: ErrorInfo) {
  // In development, log to console
  if (import.meta.env.DEV) {
    console.error("[ErrorBoundary] Caught error:", error);
    console.error("[ErrorBoundary] Component stack:", info.componentStack);
  }

  // TODO: In production, send to error monitoring service
  // e.g., Sentry.captureException(error, { extra: info });
}
