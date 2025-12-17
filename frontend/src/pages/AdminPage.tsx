/**
 * Admin page for tag management and system configuration.
 */

import { useState } from "react";
import { Settings, Tag as TagIcon, Trash2, Edit, Loader2, Merge } from "lucide-react";
import { AutoResolutionCard } from "@/components/admin/AutoResolutionCard";
import { ConflictCard } from "@/components/admin/ConflictCard";
import { DocumentQueueCard } from "@/components/admin/DocumentQueueCard";
import { MondayConfigCard } from "@/components/admin/MondayConfigCard";
import { SyncQueueCard } from "@/components/admin/SyncQueueCard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  useTags,
  useCreateStructuredTag,
  useUpdateTag,
  useDeleteTag,
  useMergeTags,
  usePopularTags,
  useTagUsage,
} from "@/hooks/useTags";
import { useAuth } from "@/hooks/useAuth";
import type { Tag, TagType } from "@/types/tag";
import { cn } from "@/lib/utils";

const tagTypeColors: Record<TagType, string> = {
  technology: "bg-blue-100 text-blue-800 border-blue-200",
  domain: "bg-green-100 text-green-800 border-green-200",
  test_type: "bg-purple-100 text-purple-800 border-purple-200",
  freeform: "bg-gray-100 text-gray-800 border-gray-200",
};

const tagTypeLabels: Record<TagType, string> = {
  technology: "Technology",
  domain: "Domain",
  test_type: "Test Type",
  freeform: "Custom",
};

export function AdminPage() {
  const { user } = useAuth();
  const { data: tags, isLoading } = useTags();
  const [filterType, setFilterType] = useState<TagType | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Create tag state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [newTagName, setNewTagName] = useState("");
  const [newTagType, setNewTagType] = useState<TagType>("technology");
  const createTag = useCreateStructuredTag();

  // Edit tag state
  const [editingTag, setEditingTag] = useState<Tag | null>(null);
  const [editName, setEditName] = useState("");
  const [editType, setEditType] = useState<TagType>("technology");
  const updateTag = useUpdateTag();

  // Delete tag state
  const [deletingTag, setDeletingTag] = useState<Tag | null>(null);
  const deleteTag = useDeleteTag();

  // Merge tag state
  const [isMergeOpen, setIsMergeOpen] = useState(false);
  const [sourceTagId, setSourceTagId] = useState("");
  const [targetTagId, setTargetTagId] = useState("");
  const mergeTags = useMergeTags();

  // Usage counts for tags
  const { data: popularTags } = usePopularTags(undefined, 500); // Get all tags with counts
  const { data: deletingTagUsage, isLoading: isLoadingUsage } = useTagUsage(
    deletingTag?.id ?? null
  );

  // Check if user is admin (in real app, check user roles)
  const isAdmin = user?.is_admin ?? false;

  if (!isAdmin) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold">Access Denied</h1>
        <p className="mt-2 text-muted-foreground">
          You need administrator privileges to access this page.
        </p>
      </div>
    );
  }

  // Get all tags as a flat array, sorted alphabetically by name
  const allTags = tags
    ? [...tags.technology, ...tags.domain, ...tags.test_type, ...tags.freeform].sort(
        (a, b) => a.name.localeCompare(b.name)
      )
    : [];

  // Create usage count map from popular tags data
  const usageMap = new Map<string, number>();
  if (popularTags) {
    popularTags.forEach((pt) => {
      usageMap.set(pt.tag.id, pt.usage_count);
    });
  }

  // Filter tags
  const filteredTags = allTags
    .filter((tag) => filterType === "all" || tag.type === filterType)
    .filter(
      (tag) =>
        !searchQuery || tag.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

  const handleCreateTag = async () => {
    if (!newTagName.trim()) return;

    try {
      await createTag.mutateAsync({
        name: newTagName.trim(),
        type: newTagType,
      });
      setIsCreateOpen(false);
      setNewTagName("");
    } catch {
      // Error handled by mutation
    }
  };

  const handleEditTag = async () => {
    if (!editingTag || !editName.trim()) return;

    try {
      await updateTag.mutateAsync({
        id: editingTag.id,
        data: { name: editName.trim(), type: editType },
      });
      setEditingTag(null);
    } catch {
      // Error handled by mutation
    }
  };

  const handleDeleteTag = async () => {
    if (!deletingTag) return;

    try {
      await deleteTag.mutateAsync(deletingTag.id);
      setDeletingTag(null);
    } catch {
      // Error handled by mutation
    }
  };

  const handleMergeTags = async () => {
    if (!sourceTagId || !targetTagId || sourceTagId === targetTagId) return;

    try {
      await mergeTags.mutateAsync({
        source_tag_id: sourceTagId,
        target_tag_id: targetTagId,
      });
      setIsMergeOpen(false);
      setSourceTagId("");
      setTargetTagId("");
    } catch {
      // Error handled by mutation
    }
  };

  const openEditDialog = (tag: Tag) => {
    setEditingTag(tag);
    setEditName(tag.name);
    setEditType(tag.type);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Settings className="h-6 w-6" />
        <h1 className="text-2xl font-bold">Admin</h1>
      </div>

      {/* Tag Management Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <TagIcon className="h-5 w-5" />
                Tag Management
              </CardTitle>
              <CardDescription>
                Create, edit, and organize structured tags
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setIsMergeOpen(true)}>
                <Merge className="mr-2 h-4 w-4" />
                Merge Tags
              </Button>
              <Button onClick={() => setIsCreateOpen(true)}>
                <TagIcon className="mr-2 h-4 w-4" />
                Add Tag
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filters */}
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search tags..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Select
              value={filterType}
              onValueChange={(v) => setFilterType(v as TagType | "all")}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="technology">Technology</SelectItem>
                <SelectItem value="domain">Domain</SelectItem>
                <SelectItem value="test_type">Test Type</SelectItem>
                <SelectItem value="freeform">Custom</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Tags list */}
          {isLoading ? (
            <div className="flex items-center justify-center gap-2 py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="text-muted-foreground">Loading tags...</span>
            </div>
          ) : filteredTags.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              No tags found
            </div>
          ) : (
            <div className="grid gap-2">
              {filteredTags.map((tag) => (
                <div
                  key={tag.id}
                  className="flex items-center justify-between rounded-md border p-3"
                >
                  <div className="flex items-center gap-3">
                    <Badge
                      variant="outline"
                      className={cn(tagTypeColors[tag.type])}
                    >
                      {tagTypeLabels[tag.type]}
                    </Badge>
                    <span className="font-medium">{tag.name}</span>
                    <span className="text-xs text-muted-foreground">
                      ({usageMap.get(tag.id) ?? 0} projects)
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(tag)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeletingTag(tag)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Sync Conflicts Section */}
      <ConflictCard />

      {/* Auto-Resolution Rules Section */}
      <AutoResolutionCard />

      {/* Sync Queue Section */}
      <SyncQueueCard />

      {/* Document Processing Queue Section */}
      <DocumentQueueCard />

      {/* Monday.com Integration Section */}
      <MondayConfigCard />

      {/* Create Tag Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Tag</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="tag-name">Name</Label>
              <Input
                id="tag-name"
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                placeholder="Enter tag name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tag-type">Type</Label>
              <Select value={newTagType} onValueChange={(v) => setNewTagType(v as TagType)}>
                <SelectTrigger id="tag-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="technology">Technology</SelectItem>
                  <SelectItem value="domain">Domain</SelectItem>
                  <SelectItem value="test_type">Test Type</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateTag}
              disabled={!newTagName.trim() || createTag.isPending}
            >
              {createTag.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Tag Dialog */}
      <Dialog open={!!editingTag} onOpenChange={(open) => !open && setEditingTag(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Tag</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Name</Label>
              <Input
                id="edit-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-type">Type</Label>
              <Select value={editType} onValueChange={(v) => setEditType(v as TagType)}>
                <SelectTrigger id="edit-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="technology">Technology</SelectItem>
                  <SelectItem value="domain">Domain</SelectItem>
                  <SelectItem value="test_type">Test Type</SelectItem>
                  <SelectItem value="freeform">Custom</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingTag(null)}>
              Cancel
            </Button>
            <Button
              onClick={handleEditTag}
              disabled={!editName.trim() || updateTag.isPending}
            >
              {updateTag.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Tag Dialog */}
      <Dialog open={!!deletingTag} onOpenChange={(open) => !open && setDeletingTag(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Tag</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>
              Are you sure you want to delete the tag{" "}
              <strong>"{deletingTag?.name}"</strong>?
            </p>
            {isLoadingUsage ? (
              <p className="mt-2 text-muted-foreground">
                Loading usage information...
              </p>
            ) : deletingTagUsage && deletingTagUsage.usage_count > 0 ? (
              <p className="mt-2 text-destructive">
                This will remove the tag from {deletingTagUsage.usage_count}{" "}
                project{deletingTagUsage.usage_count !== 1 ? "s" : ""}.
              </p>
            ) : (
              <p className="mt-2 text-muted-foreground">
                This tag is not used by any projects.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeletingTag(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteTag}
              disabled={deleteTag.isPending || isLoadingUsage}
            >
              {deleteTag.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Merge Tags Dialog */}
      <Dialog open={isMergeOpen} onOpenChange={setIsMergeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Merge Tags</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p className="text-sm text-muted-foreground">
              Merge one tag into another. All projects with the source tag will be
              updated to use the target tag. The source tag will be deleted.
            </p>
            <div className="space-y-2">
              <Label>Source Tag (will be deleted)</Label>
              <Select value={sourceTagId} onValueChange={setSourceTagId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select source tag" />
                </SelectTrigger>
                <SelectContent>
                  {allTags.map((tag) => (
                    <SelectItem key={tag.id} value={tag.id}>
                      {tag.name} ({tagTypeLabels[tag.type]})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Target Tag (will be kept)</Label>
              <Select value={targetTagId} onValueChange={setTargetTagId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select target tag" />
                </SelectTrigger>
                <SelectContent>
                  {allTags
                    .filter((tag) => tag.id !== sourceTagId)
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
            <Button variant="outline" onClick={() => setIsMergeOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleMergeTags}
              disabled={
                !sourceTagId ||
                !targetTagId ||
                sourceTagId === targetTagId ||
                mergeTags.isPending
              }
            >
              {mergeTags.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Merge
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
