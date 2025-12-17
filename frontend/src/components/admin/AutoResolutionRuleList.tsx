/**
 * AutoResolutionRuleList component.
 * Displays auto-resolution rules with enable/disable toggles and actions.
 */

import { ArrowUp, ArrowDown, Edit, Trash2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import type { AutoResolutionRule } from "@/types/monday";

interface AutoResolutionRuleListProps {
  rules: AutoResolutionRule[];
  isLoading: boolean;
  onEdit: (rule: AutoResolutionRule) => void;
  onDelete: (rule: AutoResolutionRule) => void;
  onToggleEnabled: (rule: AutoResolutionRule) => void;
  onMoveUp: (rule: AutoResolutionRule) => void;
  onMoveDown: (rule: AutoResolutionRule) => void;
  isUpdating?: boolean;
}

export function AutoResolutionRuleList({
  rules,
  isLoading,
  onEdit,
  onDelete,
  onToggleEnabled,
  onMoveUp,
  onMoveDown,
  isUpdating,
}: AutoResolutionRuleListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (rules.length === 0) {
    return (
      <div className="py-8 text-center text-muted-foreground">
        No auto-resolution rules configured
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-4 py-2 text-left text-sm font-medium">Name</th>
            <th className="px-4 py-2 text-left text-sm font-medium">Type</th>
            <th className="px-4 py-2 text-left text-sm font-medium">Field</th>
            <th className="px-4 py-2 text-left text-sm font-medium">Source</th>
            <th className="px-4 py-2 text-center text-sm font-medium">Enabled</th>
            <th className="px-4 py-2 text-center text-sm font-medium">Order</th>
            <th className="px-4 py-2 text-right text-sm font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((rule, index) => (
            <tr key={rule.id} className="border-b last:border-0">
              <td className="px-4 py-3 font-medium">{rule.name}</td>
              <td className="px-4 py-3">
                <Badge variant="outline">
                  {rule.entity_type === "*" ? "All" : rule.entity_type}
                </Badge>
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {rule.field_name || "(all fields)"}
              </td>
              <td className="px-4 py-3">
                <Badge
                  className={
                    rule.preferred_source === "npd"
                      ? "bg-blue-100 text-blue-800"
                      : "bg-purple-100 text-purple-800"
                  }
                >
                  {rule.preferred_source === "npd" ? "NPD" : "Monday"}
                </Badge>
              </td>
              <td className="px-4 py-3 text-center">
                <Switch
                  checked={rule.is_enabled}
                  onCheckedChange={() => onToggleEnabled(rule)}
                  disabled={isUpdating}
                />
              </td>
              <td className="px-4 py-3 text-center">
                <div className="flex items-center justify-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onMoveUp(rule)}
                    disabled={index === 0 || isUpdating}
                  >
                    <ArrowUp className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onMoveDown(rule)}
                    disabled={index === rules.length - 1 || isUpdating}
                  >
                    <ArrowDown className="h-4 w-4" />
                  </Button>
                </div>
              </td>
              <td className="px-4 py-3 text-right">
                <div className="flex items-center justify-end gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onEdit(rule)}
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDelete(rule)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
