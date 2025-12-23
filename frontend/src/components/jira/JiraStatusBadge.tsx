/**
 * JiraStatusBadge - Display Jira issue status with color coding.
 */

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  JIRA_STATUS_CATEGORIES,
  type JiraStatusCategory,
} from "@/types/jira";
import { cn } from "@/lib/utils";

interface JiraStatusBadgeProps {
  status: string | null;
  cachedAt: string | null;
}

const categoryStyles: Record<JiraStatusCategory, string> = {
  new: "bg-blue-100 text-blue-800 border-blue-200",
  indeterminate: "bg-yellow-100 text-yellow-800 border-yellow-200",
  done: "bg-green-100 text-green-800 border-green-200",
};

function getStatusCategory(status: string | null): JiraStatusCategory {
  if (!status) return "new";
  return JIRA_STATUS_CATEGORIES[status] ?? "indeterminate";
}

function formatCachedAt(cachedAt: string | null): string {
  if (!cachedAt) return "Never synced";
  const date = new Date(cachedAt);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.round(diffMs / 60000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  const diffHours = Math.round(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? "s" : ""} ago`;
  return date.toLocaleDateString();
}

export function JiraStatusBadge({ status, cachedAt }: JiraStatusBadgeProps) {
  const category = getStatusCategory(status);
  const displayStatus = status ?? "Unknown";

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="outline"
            className={cn("gap-1", categoryStyles[category])}
          >
            {displayStatus}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p>Last synced: {formatCachedAt(cachedAt)}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
