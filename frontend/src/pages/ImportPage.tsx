/**
 * Import page for bulk project import.
 */

import { useState } from "react";
import { FileSpreadsheet, ArrowLeft, CheckCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ImportUpload } from "@/components/forms/ImportUpload";
import { ImportPreview } from "@/components/tables/ImportPreview";
import { useImportPreview, useImportCommit } from "@/hooks/useImport";
import { useAuth } from "@/hooks/useAuth";
import type { ImportPreviewResponse, ImportRowUpdate } from "@/types/import";

type ImportStep = "upload" | "preview" | "complete";

export function ImportPage() {
  const { user } = useAuth();
  const [step, setStep] = useState<ImportStep>("upload");
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [commitRows, setCommitRows] = useState<ImportRowUpdate[]>([]);
  const [successCount, setSuccessCount] = useState(0);

  const previewMutation = useImportPreview();
  const commitMutation = useImportCommit();

  const isAdmin = user?.is_admin ?? false;

  if (!isAdmin) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold">Access Denied</h1>
        <p className="mt-2 text-muted-foreground">
          You need administrator privileges to access the import feature.
        </p>
      </div>
    );
  }

  const handleFileSelect = async (file: File) => {
    try {
      const result = await previewMutation.mutateAsync({
        file,
        includeSuggestions: true,
      });
      setPreviewData(result);
      setStep("preview");
    } catch {
      // Error handled by mutation
    }
  };

  const handleCommit = async () => {
    if (!commitRows.length) return;

    try {
      const result = await commitMutation.mutateAsync({
        rows: commitRows,
        skip_invalid: true,
      });
      setSuccessCount(result.successful);
      setStep("complete");
    } catch {
      // Error handled by mutation
    }
  };

  const handleStartOver = () => {
    setStep("upload");
    setPreviewData(null);
    setCommitRows([]);
    setSuccessCount(0);
    previewMutation.reset();
    commitMutation.reset();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        {step !== "upload" && (
          <Button variant="ghost" size="sm" onClick={handleStartOver}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Start Over
          </Button>
        )}
        <div className="flex items-center gap-2">
          <FileSpreadsheet className="h-6 w-6" />
          <h1 className="text-2xl font-bold">Import Projects</h1>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-4">
        <div
          className={`flex items-center gap-2 ${
            step === "upload" ? "text-primary" : "text-muted-foreground"
          }`}
        >
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-full ${
              step === "upload" ? "bg-primary text-primary-foreground" : "bg-muted"
            }`}
          >
            1
          </div>
          <span>Upload</span>
        </div>
        <div className="h-px w-8 bg-border" />
        <div
          className={`flex items-center gap-2 ${
            step === "preview" ? "text-primary" : "text-muted-foreground"
          }`}
        >
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-full ${
              step === "preview" ? "bg-primary text-primary-foreground" : "bg-muted"
            }`}
          >
            2
          </div>
          <span>Review</span>
        </div>
        <div className="h-px w-8 bg-border" />
        <div
          className={`flex items-center gap-2 ${
            step === "complete" ? "text-primary" : "text-muted-foreground"
          }`}
        >
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-full ${
              step === "complete" ? "bg-primary text-primary-foreground" : "bg-muted"
            }`}
          >
            3
          </div>
          <span>Complete</span>
        </div>
      </div>

      {/* Upload step */}
      {step === "upload" && (
        <Card>
          <CardHeader>
            <CardTitle>Upload CSV File</CardTitle>
            <CardDescription>
              Upload a CSV file containing project data. The file should include
              columns like: name, organization, description, start_date, location,
              status, tags.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ImportUpload
              onFileSelect={handleFileSelect}
              isLoading={previewMutation.isPending}
            />
            {previewMutation.isError && (
              <p className="mt-4 text-sm text-destructive">
                {previewMutation.error?.message || "Failed to process file"}
              </p>
            )}

            {/* Example format */}
            <div className="mt-6">
              <h4 className="text-sm font-medium mb-2">Expected columns:</h4>
              <div className="rounded-md bg-muted p-4 text-sm font-mono overflow-x-auto">
                <table className="text-xs">
                  <thead>
                    <tr className="text-muted-foreground">
                      <th className="pr-4">name</th>
                      <th className="pr-4">organization</th>
                      <th className="pr-4">description</th>
                      <th className="pr-4">start_date</th>
                      <th className="pr-4">location</th>
                      <th className="pr-4">status</th>
                      <th className="pr-4">tags</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className="pr-4">Project Alpha</td>
                      <td className="pr-4">Acme Corp</td>
                      <td className="pr-4">Security audit</td>
                      <td className="pr-4">2025-01-15</td>
                      <td className="pr-4">New York</td>
                      <td className="pr-4">active</td>
                      <td className="pr-4">web, security</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Preview step */}
      {step === "preview" && previewData && (
        <Card>
          <CardHeader>
            <CardTitle>Review Import</CardTitle>
            <CardDescription>
              Review and edit the data before importing. Fix any errors and apply
              AI suggestions as needed.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ImportPreview
              rows={previewData.rows}
              onRowsChange={setCommitRows}
              onCommit={handleCommit}
              isCommitting={commitMutation.isPending}
            />
            {commitMutation.isError && (
              <p className="mt-4 text-sm text-destructive">
                {commitMutation.error?.message || "Failed to import projects"}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Complete step */}
      {step === "complete" && (
        <Card>
          <CardContent className="flex flex-col items-center py-12">
            <CheckCircle className="h-16 w-16 text-green-600 mb-4" />
            <h2 className="text-2xl font-bold mb-2">Import Complete!</h2>
            <p className="text-muted-foreground mb-6">
              Successfully imported {successCount} project
              {successCount !== 1 ? "s" : ""}.
            </p>
            <div className="flex gap-4">
              <Button variant="outline" onClick={handleStartOver}>
                Import More
              </Button>
              <Link to="/projects">
                <Button>View Projects</Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
