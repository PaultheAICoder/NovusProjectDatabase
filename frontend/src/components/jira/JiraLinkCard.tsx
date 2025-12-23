/**
 * JiraLinkCard - Display a single Jira link with status and actions.
 */

import { ExternalLink, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { JiraStatusBadge } from "./JiraStatusBadge";
import type { JiraLink } from "@/types/jira";

interface JiraLinkCardProps {
  link: JiraLink;
  onDelete: (linkId: string) => void;
  isDeleting?: boolean;
}

export function JiraLinkCard({ link, onDelete, isDeleting }: JiraLinkCardProps) {
  return (
    <div className="flex items-center justify-between rounded-md border p-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-sm font-medium text-primary hover:underline"
          >
            {link.issue_key}
          </a>
          <JiraStatusBadge
            status={link.cached_status}
            cachedAt={link.cached_at}
          />
        </div>
        {link.cached_summary && (
          <p className="mt-1 truncate text-sm text-muted-foreground">
            {link.cached_summary}
          </p>
        )}
      </div>
      <div className="ml-4 flex items-center gap-2">
        <Button variant="ghost" size="icon" asChild className="h-8 w-8">
          <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            title="Open in Jira"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-destructive hover:text-destructive"
          onClick={() => onDelete(link.id)}
          disabled={isDeleting}
          title="Remove link"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
