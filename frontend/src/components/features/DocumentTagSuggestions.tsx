/**
 * Component for displaying tag suggestions from document content analysis.
 */

import { useState } from "react";
import { Plus, X, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useProjectTagSuggestions } from "@/hooks/useDocuments";
import { useUpdateProject } from "@/hooks/useProjects";
import type { Tag } from "@/types/tag";

interface DocumentTagSuggestionsProps {
  projectId: string;
  currentTagIds: string[];
}

export function DocumentTagSuggestions({
  projectId,
  currentTagIds,
}: DocumentTagSuggestionsProps) {
  const { data: suggestions, isLoading } = useProjectTagSuggestions(projectId);
  const updateProject = useUpdateProject();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  // Filter out already-dismissed tags (client-side for instant feedback)
  const activeSuggestions =
    suggestions?.filter((tag) => !dismissed.has(tag.id)) || [];

  if (isLoading || activeSuggestions.length === 0) {
    return null;
  }

  const handleAddTag = async (tag: Tag) => {
    try {
      await updateProject.mutateAsync({
        id: projectId,
        data: {
          tag_ids: [...currentTagIds, tag.id],
        },
      });
      setDismissed((prev) => new Set(prev).add(tag.id));
    } catch {
      // Error handled by mutation
    }
  };

  const handleDismiss = (tagId: string) => {
    setDismissed((prev) => new Set(prev).add(tagId));
  };

  const handleDismissAll = () => {
    const allIds = new Set(activeSuggestions.map((t) => t.id));
    setDismissed((prev) => new Set([...prev, ...allIds]));
  };

  return (
    <Alert className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950">
      <Sparkles className="h-4 w-4 text-amber-600" />
      <AlertTitle className="text-amber-800 dark:text-amber-200">
        Suggested tags from documents
      </AlertTitle>
      <AlertDescription>
        <div className="mt-2 flex flex-wrap gap-2">
          {activeSuggestions.map((tag) => (
            <Badge
              key={tag.id}
              variant="outline"
              className="group flex items-center gap-1 pr-1"
            >
              {tag.name}
              <Button
                variant="ghost"
                size="icon"
                className="h-4 w-4 p-0 hover:bg-green-100"
                onClick={() => handleAddTag(tag)}
                title="Add tag"
                disabled={updateProject.isPending}
              >
                <Plus className="h-3 w-3 text-green-600" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-4 w-4 p-0 hover:bg-red-100"
                onClick={() => handleDismiss(tag.id)}
                title="Dismiss suggestion"
              >
                <X className="h-3 w-3 text-red-600" />
              </Button>
            </Badge>
          ))}
        </div>
        <div className="mt-2">
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground"
            onClick={handleDismissAll}
          >
            Dismiss all suggestions
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  );
}
