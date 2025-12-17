/**
 * AutoResolutionCard component for the Admin page.
 * Manages auto-resolution rules with CRUD operations.
 */

import { useState } from "react";
import { Wand2, Plus, Loader2, AlertTriangle, CheckCircle } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { AutoResolutionRuleList } from "./AutoResolutionRuleList";
import { AutoResolutionRuleForm } from "./AutoResolutionRuleForm";
import {
  useAutoResolutionRules,
  useCreateAutoResolutionRule,
  useUpdateAutoResolutionRule,
  useDeleteAutoResolutionRule,
  useReorderAutoResolutionRules,
} from "@/hooks/useMondaySync";
import type { AutoResolutionRule, PreferredSource } from "@/types/monday";

export function AutoResolutionCard() {
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AutoResolutionRule | null>(null);
  const [deletingRule, setDeletingRule] = useState<AutoResolutionRule | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data, isLoading } = useAutoResolutionRules();
  const createRule = useCreateAutoResolutionRule();
  const updateRule = useUpdateAutoResolutionRule();
  const deleteRule = useDeleteAutoResolutionRule();
  const reorderRules = useReorderAutoResolutionRules();

  const rules = data?.rules ?? [];

  const handleCreateClick = () => {
    setEditingRule(null);
    setIsFormOpen(true);
  };

  const handleEditClick = (rule: AutoResolutionRule) => {
    setEditingRule(rule);
    setIsFormOpen(true);
  };

  const handleFormClose = () => {
    setIsFormOpen(false);
    setEditingRule(null);
  };

  const handleFormSubmit = async (formData: {
    name: string;
    entity_type: string;
    field_name: string | null;
    preferred_source: PreferredSource;
    is_enabled: boolean;
  }) => {
    try {
      // Cast entity_type to the proper type
      const typedData = {
        ...formData,
        entity_type: formData.entity_type as "contact" | "organization" | "*",
      };

      if (editingRule) {
        await updateRule.mutateAsync({
          ruleId: editingRule.id,
          data: typedData,
        });
        setSuccessMessage("Rule updated successfully");
      } else {
        await createRule.mutateAsync(typedData);
        setSuccessMessage("Rule created successfully");
      }
      handleFormClose();
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to save rule"
      );
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleToggleEnabled = async (rule: AutoResolutionRule) => {
    try {
      await updateRule.mutateAsync({
        ruleId: rule.id,
        data: { is_enabled: !rule.is_enabled },
      });
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to toggle rule"
      );
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deletingRule) return;

    try {
      await deleteRule.mutateAsync(deletingRule.id);
      setSuccessMessage("Rule deleted successfully");
      setDeletingRule(null);
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to delete rule"
      );
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleMoveUp = async (rule: AutoResolutionRule) => {
    const index = rules.findIndex((r) => r.id === rule.id);
    if (index <= 0) return;

    const newOrder = [...rules];
    const prevRule = newOrder[index - 1];
    const currRule = newOrder[index];
    if (prevRule && currRule) {
      newOrder[index - 1] = currRule;
      newOrder[index] = prevRule;
    }

    try {
      await reorderRules.mutateAsync({
        rule_ids: newOrder.map((r) => r.id),
      });
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to reorder rules"
      );
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleMoveDown = async (rule: AutoResolutionRule) => {
    const index = rules.findIndex((r) => r.id === rule.id);
    if (index < 0 || index >= rules.length - 1) return;

    const newOrder = [...rules];
    const currRule = newOrder[index];
    const nextRule = newOrder[index + 1];
    if (currRule && nextRule) {
      newOrder[index] = nextRule;
      newOrder[index + 1] = currRule;
    }

    try {
      await reorderRules.mutateAsync({
        rule_ids: newOrder.map((r) => r.id),
      });
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to reorder rules"
      );
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const isUpdating =
    updateRule.isPending ||
    deleteRule.isPending ||
    reorderRules.isPending;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Wand2 className="h-5 w-5" />
                Auto-Resolution Rules
              </CardTitle>
              <CardDescription>
                Configure automatic conflict resolution preferences
              </CardDescription>
            </div>
            <Button onClick={handleCreateClick}>
              <Plus className="mr-2 h-4 w-4" />
              Add Rule
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {successMessage && (
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                {successMessage}
              </AlertDescription>
            </Alert>
          )}

          {errorMessage && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          <AutoResolutionRuleList
            rules={rules}
            isLoading={isLoading}
            onEdit={handleEditClick}
            onDelete={setDeletingRule}
            onToggleEnabled={handleToggleEnabled}
            onMoveUp={handleMoveUp}
            onMoveDown={handleMoveDown}
            isUpdating={isUpdating}
          />
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <AutoResolutionRuleForm
        isOpen={isFormOpen}
        onClose={handleFormClose}
        onSubmit={handleFormSubmit}
        isSubmitting={createRule.isPending || updateRule.isPending}
        editingRule={editingRule}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deletingRule} onOpenChange={(open) => !open && setDeletingRule(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Rule</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>
              Are you sure you want to delete the rule{" "}
              <strong>"{deletingRule?.name}"</strong>?
            </p>
            <p className="mt-2 text-muted-foreground">
              Conflicts that would have matched this rule will require manual resolution.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingRule(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={deleteRule.isPending}
            >
              {deleteRule.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
