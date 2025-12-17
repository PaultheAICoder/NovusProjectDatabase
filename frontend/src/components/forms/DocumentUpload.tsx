/**
 * Document upload component with drag-drop and progress tracking.
 */

import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { Upload, FileText, AlertCircle, CheckCircle2 } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { useUploadDocument } from "@/hooks/useDocuments";
import { toast } from "@/hooks/useToast";
import { cn } from "@/lib/utils";

const ACCEPTED_FILE_TYPES = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
    ".docx",
  ],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
    ".xlsx",
  ],
  "application/vnd.ms-excel": [".xls"],
  "text/plain": [".txt"],
  "text/csv": [".csv"],
};

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

type UploadPhase = "uploading" | "scanning" | "processing" | "complete" | "error";

interface UploadProgress {
  file: File;
  progress: number;
  phase: UploadPhase;
  error?: string;
}

interface DocumentUploadProps {
  projectId: string;
  onSuccess?: () => void;
}

export function DocumentUpload({ projectId, onSuccess }: DocumentUploadProps) {
  const [uploads, setUploads] = useState<Map<string, UploadProgress>>(new Map());

  const uploadMutation = useUploadDocument(projectId);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      // Handle rejected files with toast
      rejectedFiles.forEach(({ file, errors }) => {
        const errorMsg = errors.map((e) => e.message).join(", ");
        toast({
          title: "Upload failed",
          description: `${file.name}: ${errorMsg}`,
          variant: "destructive",
        });
      });

      // Process accepted files
      acceptedFiles.forEach(async (file) => {
        const fileKey = `${file.name}-${Date.now()}`;

        // Initialize upload state
        setUploads((prev) => {
          const next = new Map(prev);
          next.set(fileKey, {
            file,
            progress: 0,
            phase: "uploading",
          });
          return next;
        });

        try {
          // Phase 1: Uploading with progress
          await uploadMutation.mutateAsync({
            file,
            onProgress: (progress) => {
              setUploads((prev) => {
                const next = new Map(prev);
                const current = next.get(fileKey);
                if (current) {
                  // During upload, show 0-70% progress
                  next.set(fileKey, {
                    ...current,
                    progress: Math.round(progress * 0.7),
                    phase: progress < 100 ? "uploading" : "scanning",
                  });
                }
                return next;
              });
            },
          });

          // Phase 2: Server-side processing (scanning/processing)
          setUploads((prev) => {
            const next = new Map(prev);
            const current = next.get(fileKey);
            if (current) {
              next.set(fileKey, {
                ...current,
                progress: 85,
                phase: "processing",
              });
            }
            return next;
          });

          // Brief delay to show processing state
          await new Promise((r) => setTimeout(r, 500));

          // Phase 3: Complete
          setUploads((prev) => {
            const next = new Map(prev);
            const current = next.get(fileKey);
            if (current) {
              next.set(fileKey, {
                ...current,
                progress: 100,
                phase: "complete",
              });
            }
            return next;
          });

          // Show success toast
          toast({
            title: "Upload complete",
            description: `${file.name} uploaded successfully`,
            variant: "success",
          });

          // Remove from queue after a short delay
          setTimeout(() => {
            setUploads((prev) => {
              const next = new Map(prev);
              next.delete(fileKey);
              return next;
            });
          }, 2000);

          onSuccess?.();
        } catch (error) {
          setUploads((prev) => {
            const next = new Map(prev);
            const current = next.get(fileKey);
            if (current) {
              next.set(fileKey, {
                ...current,
                phase: "error",
                error: error instanceof Error ? error.message : "Upload failed",
              });
            }
            return next;
          });

          toast({
            title: "Upload failed",
            description: `${file.name}: ${error instanceof Error ? error.message : "Upload failed"}`,
            variant: "destructive",
          });
        }
      });
    },
    [uploadMutation, onSuccess]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    multiple: true,
  });

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors",
          isDragActive
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-primary/50"
        )}
      >
        <input {...getInputProps()} />
        <Upload className="mb-2 h-8 w-8 text-muted-foreground" />
        {isDragActive ? (
          <p className="text-sm text-primary">Drop files here...</p>
        ) : (
          <>
            <p className="text-sm font-medium">
              Drag & drop files here, or click to select
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Supports PDF, DOCX, XLSX, XLS, TXT, CSV (max 50MB)
            </p>
          </>
        )}
      </div>

      {/* Upload progress display */}
      {uploads.size > 0 && (
        <div className="space-y-3">
          {Array.from(uploads.entries()).map(([key, upload]) => (
            <div
              key={key}
              className={cn(
                "rounded-md border p-3 transition-colors",
                upload.phase === "error"
                  ? "border-destructive bg-destructive/5"
                  : upload.phase === "complete"
                    ? "border-green-500 bg-green-50 dark:bg-green-950"
                    : "border-border bg-muted/50"
              )}
            >
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 flex-shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{upload.file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {upload.phase === "uploading" && "Uploading..."}
                    {upload.phase === "scanning" && "Scanning file..."}
                    {upload.phase === "processing" && "Processing document..."}
                    {upload.phase === "complete" && "Upload complete"}
                    {upload.phase === "error" && (upload.error || "Upload failed")}
                  </p>
                </div>
                {upload.phase === "complete" ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                ) : upload.phase === "error" ? (
                  <AlertCircle className="h-5 w-5 text-destructive" />
                ) : (
                  <span className="text-sm font-medium tabular-nums text-muted-foreground">
                    {upload.progress}%
                  </span>
                )}
              </div>
              {upload.phase !== "complete" && upload.phase !== "error" && (
                <Progress value={upload.progress} className="mt-2 h-1.5" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
