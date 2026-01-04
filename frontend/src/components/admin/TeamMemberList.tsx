/**
 * TeamMemberList - Display team members.
 */

import { Loader2, User } from "lucide-react";
import { format } from "date-fns";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { TeamMember } from "@/types/team";

interface TeamMemberListProps {
  members: TeamMember[];
  isLoading?: boolean;
}

export function TeamMemberList({
  members,
  isLoading = false,
}: TeamMemberListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-4">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Loading members...</span>
      </div>
    );
  }

  if (members.length === 0) {
    return (
      <div className="py-4 text-center text-sm text-muted-foreground">
        No members in this team yet.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>User ID</TableHead>
          <TableHead>Synced At</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.map((member) => (
          <TableRow key={member.id}>
            <TableCell>
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" />
                <code className="text-xs">{member.user_id}</code>
              </div>
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {format(new Date(member.synced_at), "MMM d, yyyy HH:mm")}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
