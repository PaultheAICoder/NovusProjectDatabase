/**
 * AutoResolutionRuleForm component.
 * Dialog form for creating/editing auto-resolution rules.
 */

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
import { Switch } from "@/components/ui/switch";
import type { AutoResolutionRule, PreferredSource } from "@/types/monday";

interface AutoResolutionRuleFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: {
    name: string;
    entity_type: string;
    field_name: string | null;
    preferred_source: PreferredSource;
    is_enabled: boolean;
  }) => void;
  isSubmitting: boolean;
  editingRule?: AutoResolutionRule | null;
}

// Common fields that might have conflicts
const COMMON_FIELDS = [
  { value: "name", label: "Name" },
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone" },
  { value: "title", label: "Title" },
  { value: "department", label: "Department" },
  { value: "address", label: "Address" },
  { value: "website", label: "Website" },
];

export function AutoResolutionRuleForm({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  editingRule,
}: AutoResolutionRuleFormProps) {
  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState<string>("contact");
  const [fieldName, setFieldName] = useState<string | null>(null);
  const [preferredSource, setPreferredSource] = useState<PreferredSource>("npd");
  const [isEnabled, setIsEnabled] = useState(true);

  // Reset form when opening/closing or editing different rule
  useEffect(() => {
    if (isOpen && editingRule) {
      setName(editingRule.name);
      setEntityType(editingRule.entity_type);
      setFieldName(editingRule.field_name);
      setPreferredSource(editingRule.preferred_source);
      setIsEnabled(editingRule.is_enabled);
    } else if (isOpen && !editingRule) {
      setName("");
      setEntityType("contact");
      setFieldName(null);
      setPreferredSource("npd");
      setIsEnabled(true);
    }
  }, [isOpen, editingRule]);

  const handleSubmit = () => {
    if (!name.trim()) return;

    onSubmit({
      name: name.trim(),
      entity_type: entityType,
      field_name: fieldName,
      preferred_source: preferredSource,
      is_enabled: isEnabled,
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>
            {editingRule ? "Edit Rule" : "Create Auto-Resolution Rule"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="rule-name">Rule Name</Label>
            <Input
              id="rule-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Contacts default to NPD"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="entity-type">Entity Type</Label>
            <Select value={entityType} onValueChange={setEntityType}>
              <SelectTrigger id="entity-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="contact">Contact</SelectItem>
                <SelectItem value="organization">Organization</SelectItem>
                <SelectItem value="*">All Types</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="field-name">Field (optional)</Label>
            <Select
              value={fieldName || "_all"}
              onValueChange={(v) => setFieldName(v === "_all" ? null : v)}
            >
              <SelectTrigger id="field-name">
                <SelectValue placeholder="All Fields" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_all">All Fields</SelectItem>
                {COMMON_FIELDS.map((field) => (
                  <SelectItem key={field.value} value={field.value}>
                    {field.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Field-specific rules take priority over entity-wide rules
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="preferred-source">Preferred Source</Label>
            <Select
              value={preferredSource}
              onValueChange={(v: PreferredSource) => setPreferredSource(v)}
            >
              <SelectTrigger id="preferred-source">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="npd">NPD (keep local data)</SelectItem>
                <SelectItem value="monday">Monday.com</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between">
            <Label htmlFor="is-enabled">Enabled</Label>
            <Switch
              id="is-enabled"
              checked={isEnabled}
              onCheckedChange={setIsEnabled}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!name.trim() || isSubmitting}
          >
            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {editingRule ? "Save Changes" : "Create Rule"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
