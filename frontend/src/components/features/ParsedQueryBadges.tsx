/**
 * Displays parsed query interpretation as badges.
 */

import { Badge } from "@/components/ui/badge";
import { Calendar, Building2, Tag, CheckCircle2 } from "lucide-react";
import type { ParsedQueryIntent } from "@/types/search";

interface ParsedQueryBadgesProps {
  intent: ParsedQueryIntent;
  className?: string;
}

export function ParsedQueryBadges({ intent, className }: ParsedQueryBadgesProps) {
  const badges: { icon: React.ReactNode; label: string; value: string }[] = [];

  // Date range badge
  if (intent.date_range?.original_expression) {
    badges.push({
      icon: <Calendar className="h-3 w-3" />,
      label: "Time",
      value: intent.date_range.original_expression,
    });
  }

  // Organization badge
  if (intent.organization_name) {
    badges.push({
      icon: <Building2 className="h-3 w-3" />,
      label: "Client",
      value: intent.organization_name,
    });
  }

  // Technology keywords badges
  if (intent.technology_keywords.length > 0) {
    badges.push({
      icon: <Tag className="h-3 w-3" />,
      label: "Tech",
      value: intent.technology_keywords.join(", "),
    });
  }

  // Status badge
  if (intent.status.length > 0) {
    badges.push({
      icon: <CheckCircle2 className="h-3 w-3" />,
      label: "Status",
      value: intent.status.join(", "),
    });
  }

  if (badges.length === 0 && !intent.search_text) {
    return null;
  }

  return (
    <div className={className}>
      <span className="text-sm text-muted-foreground mr-2">Searching for:</span>
      <div className="inline-flex flex-wrap gap-2">
        {badges.map((badge, index) => (
          <Badge key={index} variant="secondary" className="gap-1">
            {badge.icon}
            <span className="font-medium">{badge.label}:</span>
            <span>{badge.value}</span>
          </Badge>
        ))}
        {intent.search_text && (
          <Badge variant="outline" className="gap-1">
            <span className="font-medium">Keywords:</span>
            <span>{intent.search_text}</span>
          </Badge>
        )}
      </div>
    </div>
  );
}
