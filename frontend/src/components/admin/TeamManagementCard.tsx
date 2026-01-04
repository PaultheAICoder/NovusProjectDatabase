/**
 * TeamManagementCard - Admin card for managing teams.
 */

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Edit,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  Users,
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
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  useTeams,
  useTeam,
  useCreateTeam,
  useUpdateTeam,
  useDeleteTeam,
  useSyncTeam,
} from "@/hooks/useTeams";
import { TeamMemberList } from "@/components/admin/TeamMemberList";
import type { Team, TeamCreate, TeamUpdate } from "@/types/team";

export function TeamManagementCard() {
  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);

  // Dialog states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingTeam, setEditingTeam] = useState<Team | null>(null);
  const [deletingTeam, setDeletingTeam] = useState<Team | null>(null);
  const [viewingTeamId, setViewingTeamId] = useState<string | null>(null);

  // Form states
  const [createForm, setCreateForm] = useState<TeamCreate>({
    name: "",
    azure_ad_group_id: "",
    description: "",
  });
  const [editForm, setEditForm] = useState<TeamUpdate>({
    name: "",
    description: "",
  });

  // Messages
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const { data: teamsData, isLoading, refetch } = useTeams({ page, pageSize });
  const { data: teamDetail, isLoading: isLoadingDetail } =
    useTeam(viewingTeamId);

  // Mutations
  const createTeam = useCreateTeam();
  const updateTeam = useUpdateTeam();
  const deleteTeam = useDeleteTeam();
  const syncTeam = useSyncTeam();

  const showSuccess = (message: string) => {
    setSuccessMessage(message);
    setTimeout(() => setSuccessMessage(null), 5000);
  };

  const showError = (message: string) => {
    setErrorMessage(message);
    setTimeout(() => setErrorMessage(null), 5000);
  };

  // Handlers
  const handleCreate = async () => {
    if (!createForm.name.trim() || !createForm.azure_ad_group_id.trim()) return;

    try {
      await createTeam.mutateAsync({
        name: createForm.name.trim(),
        azure_ad_group_id: createForm.azure_ad_group_id.trim(),
        description: createForm.description?.trim() || undefined,
      });
      setIsCreateOpen(false);
      setCreateForm({ name: "", azure_ad_group_id: "", description: "" });
      showSuccess("Team created successfully.");
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to create team";
      showError(errorMsg);
    }
  };

  const handleEdit = async () => {
    if (!editingTeam || !editForm.name?.trim()) return;

    try {
      await updateTeam.mutateAsync({
        teamId: editingTeam.id,
        data: {
          name: editForm.name?.trim(),
          description: editForm.description?.trim() || undefined,
        },
      });
      setEditingTeam(null);
      showSuccess("Team updated successfully.");
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to update team";
      showError(errorMsg);
    }
  };

  const handleDelete = async () => {
    if (!deletingTeam) return;

    try {
      await deleteTeam.mutateAsync(deletingTeam.id);
      setDeletingTeam(null);
      showSuccess("Team deleted successfully.");
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to delete team";
      showError(errorMsg);
    }
  };

  const handleSync = async (teamId: string) => {
    try {
      const result = await syncTeam.mutateAsync(teamId);
      showSuccess(
        `Sync complete: ${result.members_added} added, ${result.members_removed} removed`,
      );
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to sync team";
      showError(errorMsg);
    }
  };

  const openEditDialog = (team: Team) => {
    setEditingTeam(team);
    setEditForm({
      name: team.name,
      description: team.description || "",
    });
  };

  const teams = teamsData?.items ?? [];
  const total = teamsData?.total ?? 0;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Team Management
                {total > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {total}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Manage teams linked to Azure AD groups for project permissions
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isLoading}
              >
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
              </Button>
              <Button size="sm" onClick={() => setIsCreateOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                New Team
              </Button>
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

          {/* Teams List */}
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="text-muted-foreground">Loading teams...</span>
            </div>
          ) : teams.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              No teams created yet. Create a team to start assigning project
              permissions.
            </div>
          ) : (
            <div className="space-y-2">
              {teams.map((team) => (
                <div
                  key={team.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{team.name}</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Azure AD Group: {team.azure_ad_group_id}
                    </div>
                    {team.description && (
                      <div className="text-sm text-muted-foreground">
                        {team.description}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setViewingTeamId(team.id)}
                    >
                      <Users className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSync(team.id)}
                      disabled={syncTeam.isPending}
                    >
                      {syncTeam.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(team)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeletingTeam(team)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-end gap-2">
              <span className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="icon"
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={() => setPage(page + 1)}
                disabled={page >= totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Team Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Team</DialogTitle>
            <DialogDescription>
              Create a new team linked to an Azure AD group.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="team-name">Team Name</Label>
              <Input
                id="team-name"
                value={createForm.name}
                onChange={(e) =>
                  setCreateForm({ ...createForm, name: e.target.value })
                }
                placeholder="e.g., Engineering Team"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="azure-group-id">Azure AD Group ID</Label>
              <Input
                id="azure-group-id"
                value={createForm.azure_ad_group_id}
                onChange={(e) =>
                  setCreateForm({
                    ...createForm,
                    azure_ad_group_id: e.target.value,
                  })
                }
                placeholder="e.g., 12345678-abcd-1234-abcd-123456789012"
              />
              <p className="text-xs text-muted-foreground">
                The Object ID of the Azure AD group to sync members from.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description (optional)</Label>
              <Textarea
                id="description"
                value={createForm.description}
                onChange={(e) =>
                  setCreateForm({ ...createForm, description: e.target.value })
                }
                placeholder="Brief description of the team..."
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsCreateOpen(false)}
              disabled={createTeam.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={
                !createForm.name.trim() ||
                !createForm.azure_ad_group_id.trim() ||
                createTeam.isPending
              }
            >
              {createTeam.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Team Dialog */}
      <Dialog
        open={!!editingTeam}
        onOpenChange={(open) => !open && setEditingTeam(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Team</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Team Name</Label>
              <Input
                id="edit-name"
                value={editForm.name}
                onChange={(e) =>
                  setEditForm({ ...editForm, name: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label>Azure AD Group ID</Label>
              <div className="rounded-md border bg-muted/50 p-2">
                <code className="text-xs">{editingTeam?.azure_ad_group_id}</code>
              </div>
              <p className="text-xs text-muted-foreground">
                Group ID cannot be changed after creation.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-description">Description</Label>
              <Textarea
                id="edit-description"
                value={editForm.description}
                onChange={(e) =>
                  setEditForm({ ...editForm, description: e.target.value })
                }
                rows={2}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditingTeam(null)}
              disabled={updateTeam.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleEdit}
              disabled={!editForm.name?.trim() || updateTeam.isPending}
            >
              {updateTeam.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Team Dialog */}
      <Dialog
        open={!!deletingTeam}
        onOpenChange={(open) => !open && setDeletingTeam(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              Delete Team
            </DialogTitle>
            <DialogDescription>
              Are you sure you want to delete the team "{deletingTeam?.name}"?
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-muted-foreground">
              This will remove the team and all its permission assignments. Team
              members will lose access to any projects where this team was
              granted permissions.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeletingTeam(null)}
              disabled={deleteTeam.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteTeam.isPending}
            >
              {deleteTeam.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Delete Team
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Team Members Dialog */}
      <Dialog
        open={!!viewingTeamId}
        onOpenChange={(open) => !open && setViewingTeamId(null)}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              Team Members: {teamDetail?.name}
            </DialogTitle>
            <DialogDescription>
              Members synced from Azure AD group
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <TeamMemberList
              members={teamDetail?.members ?? []}
              isLoading={isLoadingDetail}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setViewingTeamId(null)}
            >
              Close
            </Button>
            {viewingTeamId && (
              <Button
                onClick={() => handleSync(viewingTeamId)}
                disabled={syncTeam.isPending}
              >
                {syncTeam.isPending && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                <RefreshCw className="mr-2 h-4 w-4" />
                Sync Now
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
