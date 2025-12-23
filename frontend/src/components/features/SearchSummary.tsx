/**
 * Displays AI-generated search result summary.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Sparkles, AlertCircle } from "lucide-react";
import type { SummarizationResponse } from "@/types/search";

interface SearchSummaryProps {
  summary: SummarizationResponse | undefined;
  isLoading: boolean;
  error: Error | null;
}

export function SearchSummary({ summary, isLoading, error }: SearchSummaryProps) {
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Unable to generate summary. {error.message}
        </AlertDescription>
      </Alert>
    );
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4" />
            AI Summary
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-[90%]" />
          <Skeleton className="h-4 w-[80%]" />
        </CardContent>
      </Card>
    );
  }

  if (!summary) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary" />
          AI Summary
          {summary.truncated && (
            <span className="text-xs font-normal text-muted-foreground">
              (partial - context truncated)
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed whitespace-pre-line">
          {summary.summary}
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Based on {summary.context_used} source(s)
        </p>
      </CardContent>
    </Card>
  );
}
