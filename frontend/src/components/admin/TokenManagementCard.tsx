/**
 * TokenManagementCard - Admin card for managing all API tokens.
 */

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Key,
  Loader2,
  Plus,
  RefreshCw,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { TokenList } from "@/components/tokens/TokenList";
import { TokenCreateDialog } from "@/components/tokens/TokenCreateDialog";
import { TokenCreatedDialog } from "@/components/tokens/TokenCreatedDialog";
import { TokenDeleteDialog } from "@/components/tokens/TokenDeleteDialog";
import {
  useUserTokens,
  useCreateToken,
  useUpdateToken,
  useDeleteToken,
  useAdminTokens,
  useAdminDeleteToken,
} from "@/hooks/useTokens";
import type { APIToken, APITokenCreateRequest } from "@/types/token";

interface TokenManagementCardProps {
  /** If true, shows admin view with all tokens. Otherwise shows user's tokens. */
  isAdminView?: boolean;
}

export function TokenManagementCard({ isAdminView = false }: TokenManagementCardProps) {
  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);

  // Admin filters
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Dialog states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createdToken, setCreatedToken] = useState<{
    token: string;
    name: string;
  } | null>(null);
  const [renamingToken, setRenamingToken] = useState<APIToken | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deletingToken, setDeletingToken] = useState<APIToken | null>(null);

  // Messages
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const userTokensQuery = useUserTokens({ page, pageSize });
  const adminTokensQuery = useAdminTokens({
    page,
    pageSize,
    isActive: statusFilter === "all" ? undefined : statusFilter === "active",
  });

  const tokensQuery = isAdminView ? adminTokensQuery : userTokensQuery;

  // Mutations
  const createToken = useCreateToken();
  const updateToken = useUpdateToken();
  const deleteToken = useDeleteToken();
  const adminDeleteToken = useAdminDeleteToken();

  // Handlers
  const handleCreate = async (data: APITokenCreateRequest) => {
    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      const response = await createToken.mutateAsync(data);
      setIsCreateOpen(false);
      setCreatedToken({ token: response.token, name: response.token_info.name });
      setSuccessMessage("Token created successfully.");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to create token";
      setErrorMessage(errorMsg);
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleRename = async () => {
    if (!renamingToken || !renameValue.trim()) return;

    try {
      await updateToken.mutateAsync({
        tokenId: renamingToken.id,
        data: { name: renameValue.trim() },
      });
      setRenamingToken(null);
      setSuccessMessage("Token renamed successfully.");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to rename token";
      setErrorMessage(errorMsg);
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleToggleActive = async (token: APIToken) => {
    try {
      await updateToken.mutateAsync({
        tokenId: token.id,
        data: { is_active: !token.is_active },
      });
      setSuccessMessage(
        token.is_active ? "Token revoked successfully." : "Token activated successfully.",
      );
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to update token";
      setErrorMessage(errorMsg);
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleDelete = async () => {
    if (!deletingToken) return;

    try {
      if (isAdminView) {
        await adminDeleteToken.mutateAsync(deletingToken.id);
      } else {
        await deleteToken.mutateAsync(deletingToken.id);
      }
      setDeletingToken(null);
      setSuccessMessage("Token deleted successfully.");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Failed to delete token";
      setErrorMessage(errorMsg);
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const openRenameDialog = (token: APIToken) => {
    setRenamingToken(token);
    setRenameValue(token.name);
  };

  const isLoading = tokensQuery.isLoading;
  const tokens = tokensQuery.data?.items ?? [];
  const total = tokensQuery.data?.total ?? 0;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                {isAdminView ? "All API Tokens" : "My API Tokens"}
                {total > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {total}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                {isAdminView
                  ? "View and manage API tokens across all users"
                  : "Create and manage your personal API tokens"}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => tokensQuery.refetch()}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
              </Button>
              {!isAdminView && (
                <Button size="sm" onClick={() => setIsCreateOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  New Token
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Success Message */}
          {successMessage && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                {successMessage}
              </AlertDescription>
            </Alert>
          )}

          {/* Error Message */}
          {errorMessage && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          {/* Admin Filters */}
          {isAdminView && (
            <div className="flex gap-4">
              <Select
                value={statusFilter}
                onValueChange={(v) => {
                  setStatusFilter(v);
                  setPage(1);
                }}
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Statuses</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="revoked">Revoked</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Token List */}
          <TokenList
            tokens={tokens}
            total={total}
            page={page}
            pageSize={pageSize}
            isLoading={isLoading}
            onPageChange={setPage}
            onRename={openRenameDialog}
            onToggleActive={handleToggleActive}
            onDelete={setDeletingToken}
            isUpdating={updateToken.isPending}
            showUserColumn={isAdminView}
          />
        </CardContent>
      </Card>

      {/* Create Token Dialog */}
      <TokenCreateDialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreate={handleCreate}
        isCreating={createToken.isPending}
      />

      {/* Token Created Dialog (shows plaintext ONCE) */}
      <TokenCreatedDialog
        isOpen={!!createdToken}
        onClose={() => setCreatedToken(null)}
        token={createdToken?.token ?? null}
        tokenName={createdToken?.name ?? ""}
      />

      {/* Rename Dialog */}
      <Dialog
        open={!!renamingToken}
        onOpenChange={(open) => !open && setRenamingToken(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename Token</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="rename-input">Token Name</Label>
              <Input
                id="rename-input"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                autoFocus
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRenamingToken(null)}
              disabled={updateToken.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleRename}
              disabled={!renameValue.trim() || updateToken.isPending}
            >
              {updateToken.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <TokenDeleteDialog
        isOpen={!!deletingToken}
        onClose={() => setDeletingToken(null)}
        onConfirm={handleDelete}
        token={deletingToken}
        isDeleting={deleteToken.isPending || adminDeleteToken.isPending}
      />
    </>
  );
}
