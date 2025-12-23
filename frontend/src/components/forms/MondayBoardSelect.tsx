/**
 * Monday.com board selector component.
 */

import { ExternalLink, Loader2 } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useMondayBoardsForProjects } from "@/hooks/useMondaySync";

interface MondayBoardSelectProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function MondayBoardSelect({
  value,
  onChange,
  disabled = false,
}: MondayBoardSelectProps) {
  const { data: boards, isLoading } = useMondayBoardsForProjects();

  if (isLoading) {
    return (
      <div className="flex h-10 w-full items-center gap-2 rounded-md border border-input bg-background px-3 py-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading boards...
      </div>
    );
  }

  if (!boards || boards.length === 0) {
    return (
      <div className="flex h-10 w-full items-center rounded-md border border-input bg-muted px-3 py-2 text-sm text-muted-foreground">
        No boards available
      </div>
    );
  }

  return (
    <Select
      value={value || "none"}
      onValueChange={(val) => onChange(val === "none" ? "" : val)}
      disabled={disabled}
    >
      <SelectTrigger className="w-full">
        <SelectValue placeholder="Select a board...">
          {value ? (
            <span className="flex items-center gap-2">
              <ExternalLink className="h-4 w-4" />
              {boards.find((b) => b.id === value)?.name || "Unknown board"}
            </span>
          ) : (
            <span className="text-muted-foreground">No board linked</span>
          )}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="none">
          <span className="text-muted-foreground">No board linked</span>
        </SelectItem>
        {boards.map((board) => (
          <SelectItem key={board.id} value={board.id}>
            {board.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
