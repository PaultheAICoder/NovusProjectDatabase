/**
 * SynonymManagementCard - Admin card for managing tag synonym relationships.
 */

import { useState, useCallback } from "react";
import {
  AlertTriangle,
  CheckCircle,
  FileText,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  Upload,
  X,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SynonymTable } from "./SynonymTable";
import {
  useSynonyms,
  useCreateSynonym,
  useDeleteSynonym,
  useAllTags,
  useImportSynonyms,
} from "@/hooks/useTags";
import type { TagSynonymDetail, TagType, Tag } from "@/types/tag";

const tagTypeLabels: Record<TagType, string> = {
  technology: "Technology",
  domain: "Domain",
  test_type: "Test Type",
  freeform: "Custom",
};

type ImportStep = "input" | "preview" | "result";

interface ParsedSynonymRow {
  rowNumber: number;
  primaryTagName: string;
  synonymTagName: string;
  primaryTagId: string | null;
  synonymTagId: string | null;
  valid: boolean;
  error?: string;
}

interface ImportResult {
  total_requested: number;
  created: number;
  skipped: number;
}

export function SynonymManagementCard() {
  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  // Dialog states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedTagId, setSelectedTagId] = useState<string>("");
  const [selectedSynonymTagId, setSelectedSynonymTagId] = useState<string>("");
  const [deletingItem, setDeletingItem] = useState<TagSynonymDetail | null>(
    null,
  );

  // Import dialog states
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [importStep, setImportStep] = useState<ImportStep>("input");
  const [csvInput, setCsvInput] = useState("");
  const [parsedSynonyms, setParsedSynonyms] = useState<ParsedSynonymRow[]>([]);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

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
  const importSynonyms = useImportSynonyms();

  // CSV Parsing function
  const parseCSV = useCallback(
    (csvText: string): ParsedSynonymRow[] => {
      const lines = csvText.trim().split("\n");
      const results: ParsedSynonymRow[] = [];

      lines.forEach((line, index) => {
        const trimmedLine = line.trim();
        if (!trimmedLine) return; // Skip empty lines

        const parts = trimmedLine.split(",").map((p) => p.trim());

        if (parts.length !== 2) {
          results.push({
            rowNumber: index + 1,
            primaryTagName: parts[0] || "",
            synonymTagName: parts[1] || "",
            primaryTagId: null,
            synonymTagId: null,
            valid: false,
            error: "Expected 2 columns (tag1,tag2)",
          });
          return;
        }

        const primaryName = parts[0] ?? "";
        const synonymName = parts[1] ?? "";
        const primaryTag = allTags?.find(
          (t: Tag) => t.name.toLowerCase() === primaryName.toLowerCase(),
        );
        const synonymTag = allTags?.find(
          (t: Tag) => t.name.toLowerCase() === synonymName.toLowerCase(),
        );

        let error: string | undefined;
        if (!primaryTag) {
          error = `Primary tag "${primaryName}" not found`;
        } else if (!synonymTag) {
          error = `Synonym tag "${synonymName}" not found`;
        } else if (primaryTag.id === synonymTag.id) {
          error = "Cannot create synonym with the same tag";
        }

        results.push({
          rowNumber: index + 1,
          primaryTagName: primaryName,
          synonymTagName: synonymName,
          primaryTagId: primaryTag?.id ?? null,
          synonymTagId: synonymTag?.id ?? null,
          valid: !error,
          error,
        });
      });

      return results;
    },
    [allTags],
  );

  // Import handlers
  const handleParse = () => {
    const parsed = parseCSV(csvInput);
    setParsedSynonyms(parsed);
    setImportStep("preview");
  };

  const handleImport = async () => {
    const validRows = parsedSynonyms.filter((row) => row.valid);
    if (validRows.length === 0) return;

    setImportError(null);

    try {
      const synonymsToImport = validRows.map((row) => ({
        tag_id: row.primaryTagId!,
        synonym_tag_id: row.synonymTagId!,
        confidence: 1.0,
      }));

      const result = await importSynonyms.mutateAsync({
        synonyms: synonymsToImport,
      });

      setImportResult(result);
      setImportStep("result");
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "Failed to import synonyms";
      setImportError(errorMsg);
    }
  };

  const handleCloseImport = () => {
    setIsImportOpen(false);
    setImportStep("input");
    setCsvInput("");
    setParsedSynonyms([]);
    setImportResult(null);
    setImportError(null);
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      setCsvInput(content);
    };
    reader.readAsText(file);
  };

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
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsImportOpen(true)}
              >
                <Upload className="mr-2 h-4 w-4" />
                Import
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
              Create a synonym relationship between two tags. When users search
              for one tag, results with the other will also be included.
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
              This will remove the link between these tags. Search results will
              no longer include one tag when searching for the other.
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

      {/* Import Synonyms Dialog */}
      <Dialog
        open={isImportOpen}
        onOpenChange={(open) => !open && handleCloseImport()}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Import Synonyms
            </DialogTitle>
          </DialogHeader>

          {/* Step: Input */}
          {importStep === "input" && (
            <div className="space-y-4 py-4">
              <p className="text-sm text-muted-foreground">
                Import synonym relationships from a CSV file. Each line should
                contain two tag names separated by a comma:{" "}
                <code>tag1,tag2</code>
              </p>

              <Tabs defaultValue="paste" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="paste">
                    <FileText className="mr-2 h-4 w-4" />
                    Paste Text
                  </TabsTrigger>
                  <TabsTrigger value="file">
                    <Upload className="mr-2 h-4 w-4" />
                    Upload File
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="paste" className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="csv-input">CSV Content</Label>
                    <Textarea
                      id="csv-input"
                      placeholder="BLE,Bluetooth Low Energy&#10;Python,Python3&#10;ML,Machine Learning"
                      value={csvInput}
                      onChange={(e) => setCsvInput(e.target.value)}
                      className="min-h-[200px] font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground">
                      One synonym pair per line: primaryTag,synonymTag
                    </p>
                  </div>
                </TabsContent>

                <TabsContent value="file" className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="csv-file">CSV File</Label>
                    <div className="flex items-center gap-4">
                      <input
                        id="csv-file"
                        type="file"
                        accept=".csv,.txt"
                        onChange={handleFileUpload}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </div>
                    {csvInput && (
                      <div className="mt-2 rounded-md border bg-muted/50 p-3">
                        <p className="text-sm font-medium">File loaded:</p>
                        <p className="text-xs text-muted-foreground">
                          {csvInput.split("\n").filter((l) => l.trim()).length}{" "}
                          lines detected
                        </p>
                      </div>
                    )}
                  </div>
                </TabsContent>
              </Tabs>

              <DialogFooter>
                <Button variant="outline" onClick={handleCloseImport}>
                  Cancel
                </Button>
                <Button onClick={handleParse} disabled={!csvInput.trim()}>
                  Parse & Preview
                </Button>
              </DialogFooter>
            </div>
          )}

          {/* Step: Preview */}
          {importStep === "preview" && (
            <div className="space-y-4 py-4">
              {importError && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{importError}</AlertDescription>
                </Alert>
              )}

              <div className="flex items-center justify-between text-sm">
                <span>
                  <strong>
                    {parsedSynonyms.filter((r) => r.valid).length}
                  </strong>{" "}
                  valid rows,{" "}
                  <strong>
                    {parsedSynonyms.filter((r) => !r.valid).length}
                  </strong>{" "}
                  invalid rows
                </span>
                {parsedSynonyms.some((r) => !r.valid) && (
                  <Badge variant="outline" className="text-amber-600">
                    <AlertTriangle className="mr-1 h-3 w-3" />
                    Some rows have errors
                  </Badge>
                )}
              </div>

              <div className="max-h-[300px] overflow-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead>Primary Tag</TableHead>
                      <TableHead>Synonym Tag</TableHead>
                      <TableHead className="w-24">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {parsedSynonyms.map((row) => (
                      <TableRow
                        key={row.rowNumber}
                        className={!row.valid ? "bg-red-50" : ""}
                      >
                        <TableCell className="font-mono text-xs">
                          {row.rowNumber}
                        </TableCell>
                        <TableCell>{row.primaryTagName}</TableCell>
                        <TableCell>{row.synonymTagName}</TableCell>
                        <TableCell>
                          {row.valid ? (
                            <Badge
                              variant="outline"
                              className="border-green-200 text-green-600"
                            >
                              <CheckCircle className="mr-1 h-3 w-3" />
                              Valid
                            </Badge>
                          ) : (
                            <Badge
                              variant="outline"
                              className="border-red-200 text-red-600"
                              title={row.error}
                            >
                              <X className="mr-1 h-3 w-3" />
                              Error
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {parsedSynonyms.some((r) => !r.valid) && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
                  <p className="text-sm font-medium text-amber-800">
                    Invalid rows will be skipped:
                  </p>
                  <ul className="mt-1 list-inside list-disc text-xs text-amber-700">
                    {parsedSynonyms
                      .filter((r) => !r.valid)
                      .slice(0, 5)
                      .map((row) => (
                        <li key={row.rowNumber}>
                          Row {row.rowNumber}: {row.error}
                        </li>
                      ))}
                    {parsedSynonyms.filter((r) => !r.valid).length > 5 && (
                      <li>
                        ...and{" "}
                        {parsedSynonyms.filter((r) => !r.valid).length - 5} more
                      </li>
                    )}
                  </ul>
                </div>
              )}

              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setImportStep("input");
                    setParsedSynonyms([]);
                  }}
                >
                  Back
                </Button>
                <Button
                  onClick={handleImport}
                  disabled={
                    parsedSynonyms.filter((r) => r.valid).length === 0 ||
                    importSynonyms.isPending
                  }
                >
                  {importSynonyms.isPending && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Import {parsedSynonyms.filter((r) => r.valid).length} Synonyms
                </Button>
              </DialogFooter>
            </div>
          )}

          {/* Step: Result */}
          {importStep === "result" && importResult && (
            <div className="space-y-4 py-4">
              <Alert className="border-green-200 bg-green-50">
                <CheckCircle className="h-4 w-4 text-green-600" />
                <AlertDescription className="text-green-800">
                  Import completed successfully!
                </AlertDescription>
              </Alert>

              <div className="grid grid-cols-3 gap-4 rounded-md border p-4">
                <div className="text-center">
                  <p className="text-2xl font-bold">
                    {importResult.total_requested}
                  </p>
                  <p className="text-sm text-muted-foreground">Requested</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-600">
                    {importResult.created}
                  </p>
                  <p className="text-sm text-muted-foreground">Created</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-amber-600">
                    {importResult.skipped}
                  </p>
                  <p className="text-sm text-muted-foreground">Skipped</p>
                </div>
              </div>

              {importResult.skipped > 0 && (
                <p className="text-sm text-muted-foreground">
                  Skipped synonyms may already exist in the database.
                </p>
              )}

              <DialogFooter>
                <Button onClick={handleCloseImport}>Done</Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
