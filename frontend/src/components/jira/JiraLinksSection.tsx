/**
 * JiraLinksSection - Complete Jira links management for project detail page.
 */

import { useState } from "react";
import {
  RefreshCw,
  Plus,
  Loader2,
  AlertCircle,
  Link as LinkIcon,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { JiraLinkCard } from "./JiraLinkCard";
import {
  useJiraLinks,
  useCreateJiraLink,
  useDeleteJiraLink,
  useRefreshJiraLinks,
} from "@/hooks/useJiraLinks";
import type { JiraLink } from "@/types/jira";

interface JiraLinksSectionProps {
  projectId: string;
}

export function JiraLinksSection({ projectId }: JiraLinksSectionProps) {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newUrl, setNewUrl] = useState("");
  const [urlError, setUrlError] = useState<string | null>(null);
  const [deleteConfirmLink, setDeleteConfirmLink] = useState<JiraLink | null>(
    null
  );

  const { data: links, isLoading, isError } = useJiraLinks(projectId);
  const createLink = useCreateJiraLink(projectId);
  const deleteLink = useDeleteJiraLink(projectId);
  const refreshLinks = useRefreshJiraLinks(projectId);

  const handleAddLink = async () => {
    setUrlError(null);

    // Basic URL validation
    if (!newUrl.trim()) {
      setUrlError("URL is required");
      return;
    }

    // Simple Jira URL pattern check
    const jiraUrlPattern = /^https?:\/\/[^/]+\/browse\/[A-Z][A-Z0-9]*-\d+$/i;
    if (!jiraUrlPattern.test(newUrl.trim())) {
      setUrlError(
        "Invalid Jira URL. Expected format: https://company.atlassian.net/browse/PROJ-123"
      );
      return;
    }

    try {
      await createLink.mutateAsync({ url: newUrl.trim() });
      setNewUrl("");
      setIsAddOpen(false);
    } catch (err) {
      if (err instanceof Error) {
        setUrlError(err.message);
      } else {
        setUrlError("Failed to add Jira link");
      }
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirmLink) return;

    try {
      await deleteLink.mutateAsync(deleteConfirmLink.id);
      setDeleteConfirmLink(null);
    } catch {
      // Error handled by mutation
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  const hasLinks = links && links.length > 0;

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <LinkIcon className="h-5 w-5" />
                Jira Links
              </CardTitle>
              <CardDescription>
                Linked Jira issues for this project
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {hasLinks && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refreshLinks.mutate()}
                  disabled={refreshLinks.isPending}
                  title="Refresh status from Jira"
                >
                  {refreshLinks.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </Button>
              )}
              <Button size="sm" onClick={() => setIsAddOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Add Link
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>Failed to load Jira links</AlertDescription>
            </Alert>
          ) : !hasLinks ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No Jira issues linked yet
            </p>
          ) : (
            <div className="space-y-2">
              {links.map((link) => (
                <JiraLinkCard
                  key={link.id}
                  link={link}
                  onDelete={() => setDeleteConfirmLink(link)}
                  isDeleting={deleteLink.isPending}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Link Dialog */}
      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Jira Link</DialogTitle>
            <DialogDescription>
              Enter a Jira issue URL to link to this project
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <Input
              placeholder="https://company.atlassian.net/browse/PROJ-123"
              value={newUrl}
              onChange={(e) => {
                setNewUrl(e.target.value);
                setUrlError(null);
              }}
              autoFocus
            />
            {urlError && (
              <p className="text-sm text-destructive">{urlError}</p>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsAddOpen(false);
                setNewUrl("");
                setUrlError(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddLink}
              disabled={createLink.isPending || !newUrl.trim()}
            >
              {createLink.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Add Link
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={!!deleteConfirmLink}
        onOpenChange={(open) => !open && setDeleteConfirmLink(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove Jira Link</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove the link to{" "}
              <strong>{deleteConfirmLink?.issue_key}</strong>? This will not
              affect the issue in Jira.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteConfirmLink(null)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteLink.isPending}
            >
              {deleteLink.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
