/**
 * SyncStatusBadge component for displaying Monday.com sync status.
 */

import { CheckCircle, Clock, AlertTriangle, Ban } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { RecordSyncStatus } from "@/types/monday";

interface StatusConfig {
  icon: typeof CheckCircle;
  label: string;
  tooltip: string;
  variant: "success" | "warning" | "destructive" | "secondary";
}

const statusConfig: Record<RecordSyncStatus, StatusConfig> = {
  synced: {
    icon: CheckCircle,
    label: "Synced",
    tooltip: "Synced with Monday.com",
    variant: "success",
  },
  pending: {
    icon: Clock,
    label: "Pending",
    tooltip: "Pending sync to Monday.com",
    variant: "warning",
  },
  conflict: {
    icon: AlertTriangle,
    label: "Conflict",
    tooltip: "Sync conflict - needs resolution",
    variant: "destructive",
  },
  disabled: {
    icon: Ban,
    label: "Disabled",
    tooltip: "Sync disabled for this record",
    variant: "secondary",
  },
};

interface SyncStatusBadgeProps {
  status: RecordSyncStatus;
}

export function SyncStatusBadge({ status }: SyncStatusBadgeProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant={config.variant}
            className="gap-1"
            aria-label={`Sync status: ${config.label}`}
          >
            <Icon className="h-3 w-3" />
            {config.label}
          </Badge>
        </TooltipTrigger>
        <TooltipContent>
          <p>{config.tooltip}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
