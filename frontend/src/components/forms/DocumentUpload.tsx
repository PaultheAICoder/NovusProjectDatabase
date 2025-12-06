/**
 * Document upload component with drag-drop.
 */

import { useCallback, useState } from "react";
import { useDropzone, type FileRejection } from "react-dropzone";
import { Upload, X, FileText, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUploadDocument } from "@/hooks/useDocuments";
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

interface DocumentUploadProps {
  projectId: string;
  onSuccess?: () => void;
}

export function DocumentUpload({ projectId, onSuccess }: DocumentUploadProps) {
  const [uploadQueue, setUploadQueue] = useState<File[]>([]);
  const [errors, setErrors] = useState<string[]>([]);

  const uploadMutation = useUploadDocument(projectId);

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      // Handle rejected files
      const newErrors: string[] = [];
      rejectedFiles.forEach(({ file, errors }) => {
        errors.forEach((error) => {
          newErrors.push(`${file.name}: ${error.message}`);
        });
      });
      setErrors(newErrors);

      // Add accepted files to queue and start uploading
      if (acceptedFiles.length > 0) {
        setUploadQueue((prev) => [...prev, ...acceptedFiles]);

        // Upload files sequentially
        acceptedFiles.forEach(async (file) => {
          try {
            await uploadMutation.mutateAsync(file);
            setUploadQueue((prev) => prev.filter((f) => f !== file));
            onSuccess?.();
          } catch (error) {
            setErrors((prev) => [
              ...prev,
              `${file.name}: ${error instanceof Error ? error.message : "Upload failed"}`,
            ]);
            setUploadQueue((prev) => prev.filter((f) => f !== file));
          }
        });
      }
    },
    [uploadMutation, onSuccess],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    multiple: true,
  });

  const removeFromQueue = (file: File) => {
    setUploadQueue((prev) => prev.filter((f) => f !== file));
  };

  const clearErrors = () => {
    setErrors([]);
  };

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors",
          isDragActive
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-primary/50",
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

      {/* Upload queue */}
      {uploadQueue.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium">Uploading...</p>
          {uploadQueue.map((file) => (
            <div
              key={file.name}
              className="flex items-center gap-2 rounded-md bg-muted p-2"
            >
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="flex-1 truncate text-sm">{file.name}</span>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => removeFromQueue(file)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* Errors */}
      {errors.length > 0 && (
        <div className="rounded-md bg-destructive/10 p-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 h-4 w-4 text-destructive" />
            <div className="flex-1">
              <p className="text-sm font-medium text-destructive">
                Upload errors
              </p>
              <ul className="mt-1 list-inside list-disc text-sm text-destructive">
                {errors.map((error, i) => (
                  <li key={i}>{error}</li>
                ))}
              </ul>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={clearErrors}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
