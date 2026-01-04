/**
 * AddPermissionDialog - Dialog for adding a user or team permission.
 */

import { useState } from "react";
import { Loader2, User, Users } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTeams } from "@/hooks/useTeams";
import { useAddPermission } from "@/hooks/usePermissions";
import type { PermissionLevel } from "@/types/permission";
import {
  PERMISSION_LEVEL_LABELS,
  PERMISSION_LEVEL_DESCRIPTIONS,
} from "@/types/permission";
import { cn } from "@/lib/utils";

interface AddPermissionDialogProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
}

type GranteeType = "user" | "team";

const PERMISSION_LEVELS: PermissionLevel[] = ["viewer", "editor", "owner"];

export function AddPermissionDialog({
  isOpen,
  onClose,
  projectId,
}: AddPermissionDialogProps) {
  const [granteeType, setGranteeType] = useState<GranteeType>("team");
  const [userId, setUserId] = useState("");
  const [teamId, setTeamId] = useState("");
  const [permissionLevel, setPermissionLevel] =
    useState<PermissionLevel>("viewer");

  const { data: teamsData, isLoading: isLoadingTeams } = useTeams();
  const addPermission = useAddPermission();

  const handleSubmit = async () => {
    const data =
      granteeType === "user"
        ? { user_id: userId, permission_level: permissionLevel }
        : { team_id: teamId, permission_level: permissionLevel };

    try {
      await addPermission.mutateAsync({ projectId, data });
      handleClose();
    } catch {
      // Error handled by mutation
    }
  };

  const handleClose = () => {
    setGranteeType("team");
    setUserId("");
    setTeamId("");
    setPermissionLevel("viewer");
    onClose();
  };

  const isValid =
    (granteeType === "user" && userId.trim()) ||
    (granteeType === "team" && teamId);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Permission</DialogTitle>
          <DialogDescription>
            Grant access to this project for a user or team.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          {/* Grantee Type Selection */}
          <div className="space-y-2">
            <Label>Grant access to</Label>
            <div className="flex gap-2">
              <Button
                type="button"
                variant={granteeType === "team" ? "default" : "outline"}
                size="sm"
                onClick={() => setGranteeType("team")}
                className={cn(
                  "flex-1",
                  granteeType === "team" && "bg-primary text-primary-foreground",
                )}
              >
                <Users className="mr-2 h-4 w-4" />
                Team
              </Button>
              <Button
                type="button"
                variant={granteeType === "user" ? "default" : "outline"}
                size="sm"
                onClick={() => setGranteeType("user")}
                className={cn(
                  "flex-1",
                  granteeType === "user" && "bg-primary text-primary-foreground",
                )}
              >
                <User className="mr-2 h-4 w-4" />
                User
              </Button>
            </div>
          </div>

          {/* User ID Input */}
          {granteeType === "user" && (
            <div className="space-y-2">
              <Label htmlFor="user-id">User ID</Label>
              <Input
                id="user-id"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                placeholder="Enter user UUID"
              />
              <p className="text-xs text-muted-foreground">
                Enter the UUID of the user to grant access.
              </p>
            </div>
          )}

          {/* Team Selection */}
          {granteeType === "team" && (
            <div className="space-y-2">
              <Label htmlFor="team-select">Team</Label>
              <Select value={teamId} onValueChange={setTeamId}>
                <SelectTrigger id="team-select">
                  <SelectValue placeholder="Select a team" />
                </SelectTrigger>
                <SelectContent>
                  {isLoadingTeams ? (
                    <div className="flex items-center justify-center p-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                    </div>
                  ) : teamsData?.items.length === 0 ? (
                    <div className="p-2 text-center text-sm text-muted-foreground">
                      No teams available
                    </div>
                  ) : (
                    teamsData?.items.map((team) => (
                      <SelectItem key={team.id} value={team.id}>
                        {team.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Permission Level */}
          <div className="space-y-2">
            <Label htmlFor="permission-level">Permission Level</Label>
            <Select
              value={permissionLevel}
              onValueChange={(v) => setPermissionLevel(v as PermissionLevel)}
            >
              <SelectTrigger id="permission-level">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERMISSION_LEVELS.map((level) => (
                  <SelectItem key={level} value={level}>
                    <div className="flex flex-col">
                      <span>{PERMISSION_LEVEL_LABELS[level]}</span>
                      <span className="text-xs text-muted-foreground">
                        {PERMISSION_LEVEL_DESCRIPTIONS[level]}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={addPermission.isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!isValid || addPermission.isPending}
          >
            {addPermission.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Add Permission
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
