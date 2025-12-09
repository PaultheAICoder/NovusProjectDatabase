/**
 * Document list component.
 */

import { format } from "date-fns";
import { Download, FileText, Trash2, AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  useDocuments,
  useDeleteDocument,
  useReprocessDocument,
  getDocumentDownloadUrl,
} from "@/hooks/useDocuments";
import type { ProcessingStatus } from "@/types/document";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(mimeType: string): string {
  if (mimeType.includes("pdf")) return "PDF";
  if (mimeType.includes("wordprocessingml")) return "DOCX";
  if (mimeType.includes("spreadsheetml") || mimeType.includes("excel"))
    return "XLSX";
  if (mimeType.includes("csv")) return "CSV";
  return "TXT";
}

const statusConfig: Record<
  ProcessingStatus,
  { label: string; variant: "default" | "secondary" | "destructive" | "success" }
> = {
  pending: { label: "Processing...", variant: "secondary" },
  completed: { label: "Indexed", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
  skipped: { label: "Not indexed", variant: "default" },
};

interface DocumentListProps {
  projectId: string;
}

export function DocumentList({ projectId }: DocumentListProps) {
  const { data, isLoading, isError } = useDocuments(projectId);
  const deleteDocument = useDeleteDocument(projectId);
  const reprocessDocument = useReprocessDocument(projectId);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-4 text-destructive">
        <AlertCircle className="h-4 w-4" />
        <span>Failed to load documents</span>
      </div>
    );
  }

  if (!data || data.items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-md border border-dashed py-8">
        <FileText className="mb-2 h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          No documents uploaded yet
        </p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Size</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Uploaded</TableHead>
          <TableHead className="w-[100px]">Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.items.map((doc) => {
          const status = statusConfig[doc.processing_status];
          return (
            <TableRow key={doc.id}>
              <TableCell className="font-medium">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  {doc.display_name}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="outline">{getFileIcon(doc.mime_type)}</Badge>
              </TableCell>
              <TableCell>{formatFileSize(doc.file_size)}</TableCell>
              <TableCell>
                <div className="flex items-center gap-2">
                  {doc.processing_status === "pending" && (
                    <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                  )}
                  <Badge variant={status.variant}>{status.label}</Badge>
                </div>
                {doc.processing_status === "failed" && doc.processing_error && (
                  <p className="mt-1 text-xs text-destructive">
                    {doc.processing_error}
                  </p>
                )}
              </TableCell>
              <TableCell>
                {format(new Date(doc.uploaded_at), "MMM d, yyyy")}
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    asChild
                  >
                    <a
                      href={getDocumentDownloadUrl(projectId, doc.id)}
                      download
                      title="Download"
                    >
                      <Download className="h-4 w-4" />
                    </a>
                  </Button>

                  {doc.processing_status === "failed" && (
                    <Button
                      variant="ghost"
                      size="icon"
                      title="Retry processing"
                      onClick={() => reprocessDocument.mutate(doc.id)}
                      disabled={reprocessDocument.isPending}
                    >
                      {reprocessDocument.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4 text-primary" />
                      )}
                    </Button>
                  )}

                  <Dialog>
                    <DialogTrigger asChild>
                      <Button variant="ghost" size="icon" title="Delete">
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Delete Document</DialogTitle>
                        <DialogDescription>
                          Are you sure you want to delete "{doc.display_name}"?
                          This action cannot be undone.
                        </DialogDescription>
                      </DialogHeader>
                      <DialogFooter>
                        <Button
                          variant="destructive"
                          onClick={() => deleteDocument.mutate(doc.id)}
                          disabled={deleteDocument.isPending}
                        >
                          {deleteDocument.isPending ? "Deleting..." : "Delete"}
                        </Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </div>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
