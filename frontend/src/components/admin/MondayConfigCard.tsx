/**
 * Monday.com configuration and sync card for admin page.
 */

import { useState } from "react";
import {
  RefreshCw,
  Building2,
  Users,
  Check,
  X,
  AlertCircle,
  Loader2,
  ExternalLink,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  useMondaySyncStatus,
  useMondayConfig,
  useTriggerMondaySync,
} from "@/hooks/useMondaySync";
import type { MondaySyncLog, MondaySyncType } from "@/types/monday";
import { cn } from "@/lib/utils";

const statusColors: Record<string, string> = {
  completed: "bg-green-100 text-green-800 border-green-200",
  in_progress: "bg-blue-100 text-blue-800 border-blue-200",
  pending: "bg-yellow-100 text-yellow-800 border-yellow-200",
  failed: "bg-red-100 text-red-800 border-red-200",
};

function formatDate(dateString: string | null): string {
  if (!dateString) return "Never";
  return new Date(dateString).toLocaleString();
}

function SyncLogSummary({ log }: { log: MondaySyncLog | null }) {
  if (!log) {
    return <span className="text-muted-foreground">Never synced</span>;
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <Badge variant="outline" className={cn(statusColors[log.status])}>
          {log.status.replace("_", " ")}
        </Badge>
        <span className="text-sm text-muted-foreground">
          {formatDate(log.completed_at || log.started_at)}
        </span>
      </div>
      {log.status === "completed" && (
        <div className="text-sm text-muted-foreground">
          {log.items_created} created, {log.items_updated} updated,{" "}
          {log.items_skipped} skipped
        </div>
      )}
      {log.status === "failed" && log.error_message && (
        <div className="text-sm text-destructive">{log.error_message}</div>
      )}
    </div>
  );
}

export function MondayConfigCard() {
  const { data: syncStatus, isLoading: isLoadingStatus } = useMondaySyncStatus();
  const { data: config } = useMondayConfig();
  const triggerSync = useTriggerMondaySync();
  const [syncingType, setSyncingType] = useState<MondaySyncType | null>(null);

  const handleSync = async (syncType: MondaySyncType) => {
    setSyncingType(syncType);
    try {
      await triggerSync.mutateAsync({ sync_type: syncType });
    } finally {
      setSyncingType(null);
    }
  };

  if (isLoadingStatus) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const isConfigured = syncStatus?.is_configured ?? false;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ExternalLink className="h-5 w-5" />
              Monday.com Integration
            </CardTitle>
            <CardDescription>
              Import contacts and organizations from Monday.com boards
            </CardDescription>
          </div>
          <Badge
            variant="outline"
            className={cn(
              isConfigured
                ? "bg-green-100 text-green-800 border-green-200"
                : "bg-yellow-100 text-yellow-800 border-yellow-200"
            )}
          >
            {isConfigured ? (
              <>
                <Check className="mr-1 h-3 w-3" />
                Configured
              </>
            ) : (
              <>
                <AlertCircle className="mr-1 h-3 w-3" />
                Not Configured
              </>
            )}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {!isConfigured ? (
          <div className="rounded-md border border-yellow-200 bg-yellow-50 p-4">
            <h4 className="font-medium text-yellow-800">Configuration Required</h4>
            <p className="mt-1 text-sm text-yellow-700">
              Set the <code className="rounded bg-yellow-100 px-1">MONDAY_API_KEY</code> environment
              variable to enable Monday.com integration.
            </p>
          </div>
        ) : (
          <>
            {/* Organizations Sync */}
            <div className="rounded-md border p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Building2 className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <h4 className="font-medium">Organizations</h4>
                    <SyncLogSummary log={syncStatus?.last_org_sync ?? null} />
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleSync("organizations")}
                  disabled={syncingType !== null || !config?.organizations_board_id}
                >
                  {syncingType === "organizations" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  Sync Now
                </Button>
              </div>
              {!config?.organizations_board_id && (
                <p className="mt-2 text-sm text-muted-foreground">
                  Set <code className="rounded bg-muted px-1">MONDAY_ORGANIZATIONS_BOARD_ID</code> to
                  enable organization sync.
                </p>
              )}
            </div>

            {/* Contacts Sync */}
            <div className="rounded-md border p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Users className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <h4 className="font-medium">Contacts</h4>
                    <SyncLogSummary log={syncStatus?.last_contact_sync ?? null} />
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleSync("contacts")}
                  disabled={syncingType !== null || !config?.contacts_board_id}
                >
                  {syncingType === "contacts" ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-2 h-4 w-4" />
                  )}
                  Sync Now
                </Button>
              </div>
              {!config?.contacts_board_id && (
                <p className="mt-2 text-sm text-muted-foreground">
                  Set <code className="rounded bg-muted px-1">MONDAY_CONTACTS_BOARD_ID</code> to
                  enable contact sync.
                </p>
              )}
            </div>

            {/* Recent Sync Logs */}
            {syncStatus?.recent_logs && syncStatus.recent_logs.length > 0 && (
              <div>
                <h4 className="mb-2 font-medium">Recent Sync Activity</h4>
                <div className="space-y-2">
                  {syncStatus.recent_logs.slice(0, 5).map((log) => (
                    <div
                      key={log.id}
                      className="flex items-center justify-between rounded border p-2 text-sm"
                    >
                      <div className="flex items-center gap-2">
                        {log.sync_type === "organizations" ? (
                          <Building2 className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <Users className="h-4 w-4 text-muted-foreground" />
                        )}
                        <span className="capitalize">{log.sync_type}</span>
                        <Badge
                          variant="outline"
                          className={cn("text-xs", statusColors[log.status])}
                        >
                          {log.status === "completed" ? (
                            <Check className="mr-1 h-3 w-3" />
                          ) : log.status === "failed" ? (
                            <X className="mr-1 h-3 w-3" />
                          ) : null}
                          {log.status.replace("_", " ")}
                        </Badge>
                      </div>
                      <span className="text-muted-foreground">
                        {formatDate(log.started_at)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
