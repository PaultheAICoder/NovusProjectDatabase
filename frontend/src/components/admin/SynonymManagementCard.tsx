/**
 * SynonymManagementCard - Admin card for managing tag synonym relationships.
 */

import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Link2,
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
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SynonymTable } from "./SynonymTable";
import {
  useSynonyms,
  useCreateSynonym,
  useDeleteSynonym,
  useAllTags,
} from "@/hooks/useTags";
import type { TagSynonymDetail, TagType } from "@/types/tag";

const tagTypeLabels: Record<TagType, string> = {
  technology: "Technology",
  domain: "Domain",
  test_type: "Test Type",
  freeform: "Custom",
};

export function SynonymManagementCard() {
  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  // Dialog states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedTagId, setSelectedTagId] = useState<string>("");
  const [selectedSynonymTagId, setSelectedSynonymTagId] = useState<string>("");
  const [deletingItem, setDeletingItem] = useState<TagSynonymDetail | null>(null);

  // Messages
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Queries
  const {
    data: synonymsData,
    isLoading: isLoadingSynonyms,
    refetch,
  } = useSynonyms({ page, pageSize });

  const { data: allTags, isLoading: isLoadingTags } = useAllTags();

  // Mutations
  const createSynonym = useCreateSynonym();
  const deleteSynonym = useDeleteSynonym();

  // Handlers
  const handleCreate = async () => {
    if (!selectedTagId || !selectedSynonymTagId) return;

    if (selectedTagId === selectedSynonymTagId) {
      setErrorMessage("Cannot create synonym with the same tag.");
      setTimeout(() => setErrorMessage(null), 5000);
      return;
    }

    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      await createSynonym.mutateAsync({
        tag_id: selectedTagId,
        synonym_tag_id: selectedSynonymTagId,
        confidence: 1.0,
      });
      setIsCreateOpen(false);
      setSelectedTagId("");
      setSelectedSynonymTagId("");
      setSuccessMessage("Synonym created successfully.");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to create synonym";
      setErrorMessage(errorMsg);
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleDelete = async () => {
    if (!deletingItem) return;

    setSuccessMessage(null);
    setErrorMessage(null);

    try {
      await deleteSynonym.mutateAsync({
        tagId: deletingItem.tag_id,
        synonymTagId: deletingItem.synonym_tag_id,
      });
      setDeletingItem(null);
      setSuccessMessage("Synonym deleted successfully.");
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to delete synonym";
      setErrorMessage(errorMsg);
      setTimeout(() => setErrorMessage(null), 5000);
    }
  };

  const handleRefresh = () => {
    refetch();
  };

  const isLoading = isLoadingSynonyms || isLoadingTags;
  const synonyms = synonymsData?.items ?? [];
  const total = synonymsData?.total ?? 0;
  const hasMore = synonymsData?.has_more ?? false;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Link2 className="h-5 w-5" />
                Tag Synonyms
                {total > 0 && (
                  <Badge variant="secondary" className="ml-2">
                    {total}
                  </Badge>
                )}
              </CardTitle>
              <CardDescription>
                Manage synonym relationships between tags for improved search
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleRefresh}
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
                Add Synonym
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

          {/* Synonym Table */}
          <SynonymTable
            items={synonyms}
            total={total}
            page={page}
            pageSize={pageSize}
            hasMore={hasMore}
            isLoading={isLoadingSynonyms}
            onPageChange={setPage}
            onDelete={setDeletingItem}
            isDeleting={deleteSynonym.isPending}
          />
        </CardContent>
      </Card>

      {/* Create Synonym Dialog */}
      <Dialog
        open={isCreateOpen}
        onOpenChange={(open) => {
          if (!open) {
            setIsCreateOpen(false);
            setSelectedTagId("");
            setSelectedSynonymTagId("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Tag Synonym</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p className="text-sm text-muted-foreground">
              Create a synonym relationship between two tags. When users search for
              one tag, results with the other will also be included.
            </p>
            <div className="space-y-2">
              <Label htmlFor="primary-tag">Primary Tag</Label>
              <Select value={selectedTagId} onValueChange={setSelectedTagId}>
                <SelectTrigger id="primary-tag">
                  <SelectValue placeholder="Select a tag" />
                </SelectTrigger>
                <SelectContent>
                  {allTags?.map((tag) => (
                    <SelectItem key={tag.id} value={tag.id}>
                      {tag.name} ({tagTypeLabels[tag.type]})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="synonym-tag">Synonym Tag</Label>
              <Select
                value={selectedSynonymTagId}
                onValueChange={setSelectedSynonymTagId}
              >
                <SelectTrigger id="synonym-tag">
                  <SelectValue placeholder="Select a synonym tag" />
                </SelectTrigger>
                <SelectContent>
                  {allTags
                    ?.filter((tag) => tag.id !== selectedTagId)
                    .map((tag) => (
                      <SelectItem key={tag.id} value={tag.id}>
                        {tag.name} ({tagTypeLabels[tag.type]})
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateOpen(false);
                setSelectedTagId("");
                setSelectedSynonymTagId("");
              }}
              disabled={createSynonym.isPending}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={
                !selectedTagId ||
                !selectedSynonymTagId ||
                selectedTagId === selectedSynonymTagId ||
                createSynonym.isPending
              }
            >
              {createSynonym.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={!!deletingItem}
        onOpenChange={(open) => !open && setDeletingItem(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Synonym</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>
              Are you sure you want to delete the synonym relationship between{" "}
              <strong>"{deletingItem?.tag.name}"</strong> and{" "}
              <strong>"{deletingItem?.synonym_tag.name}"</strong>?
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              This will remove the link between these tags. Search results will no
              longer include one tag when searching for the other.
            </p>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeletingItem(null)}
              disabled={deleteSynonym.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteSynonym.isPending}
            >
              {deleteSynonym.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
