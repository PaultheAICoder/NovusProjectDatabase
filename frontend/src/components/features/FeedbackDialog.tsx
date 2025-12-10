/**
 * Feedback dialog component with multi-step form flow.
 */

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Bug,
  Lightbulb,
  CheckCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { useClarifyQuestions, useSubmitFeedback } from "@/hooks/useFeedback";
import type { FeedbackType, FeedbackStep } from "@/types/feedback";

interface FeedbackDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function FeedbackDialog({ open, onOpenChange }: FeedbackDialogProps) {
  const [step, setStep] = useState<FeedbackStep>("select-type");
  const [error, setError] = useState<string | null>(null);

  const [feedbackType, setFeedbackType] = useState<FeedbackType | "">("");
  const [description, setDescription] = useState("");
  const [questions, setQuestions] = useState<string[]>([]);
  const [answers, setAnswers] = useState<string[]>(["", "", ""]);
  const [issueUrl, setIssueUrl] = useState("");

  const clarifyMutation = useClarifyQuestions();
  const submitMutation = useSubmitFeedback();

  // Reset form when dialog closes
  useEffect(() => {
    if (!open) {
      // Small delay to allow animation to complete
      const timer = setTimeout(() => {
        setStep("select-type");
        setFeedbackType("");
        setDescription("");
        setQuestions([]);
        setAnswers(["", "", ""]);
        setIssueUrl("");
        setError(null);
        clarifyMutation.reset();
        submitMutation.reset();
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [open, clarifyMutation, submitMutation]);

  const handleTypeSelect = (type: FeedbackType) => {
    setFeedbackType(type);
    setStep("describe");
  };

  const handleDescriptionSubmit = () => {
    if (description.length < 10) {
      setError("Please provide more detail (at least 10 characters)");
      return;
    }

    if (feedbackType === "") {
      setError("Please select a feedback type");
      return;
    }

    setError(null);
    clarifyMutation.mutate(
      {
        feedback_type: feedbackType,
        description,
      },
      {
        onSuccess: (data) => {
          setQuestions(data.questions);
          // Initialize answers array based on number of questions
          setAnswers(new Array(data.questions.length).fill(""));
          setStep("clarify");
        },
        onError: (err) => {
          setError(
            err instanceof Error ? err.message : "Failed to get clarifying questions"
          );
        },
      }
    );
  };

  const handleSubmit = () => {
    // Validate all answers provided
    if (answers.some((a) => a.trim().length === 0)) {
      setError("Please answer all questions");
      return;
    }

    if (feedbackType === "") {
      setError("Please select a feedback type");
      return;
    }

    setError(null);
    setStep("submitting");

    // Generate title from description (first 50 chars or first sentence)
    const title =
      description.length <= 50
        ? description
        : description.slice(0, 50).trim() + "...";

    submitMutation.mutate(
      {
        feedback_type: feedbackType,
        title,
        description,
        clarifying_answers: answers,
      },
      {
        onSuccess: (data) => {
          setIssueUrl(data.github_issue_url);
          setStep("success");
        },
        onError: (err) => {
          setError(
            err instanceof Error ? err.message : "Failed to submit feedback"
          );
          setStep("error");
        },
      }
    );
  };

  const handleBack = () => {
    if (step === "describe") {
      setStep("select-type");
      setFeedbackType("");
    } else if (step === "clarify") {
      setStep("describe");
    } else if (step === "error") {
      setStep("clarify");
    }
    setError(null);
  };

  const isLoading = clarifyMutation.isPending || submitMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        {/* Step 1: Select Type */}
        {step === "select-type" && (
          <>
            <DialogHeader>
              <DialogTitle>Submit Feedback</DialogTitle>
              <DialogDescription>
                Help us improve! What type of feedback do you have?
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-4">
              <button
                type="button"
                onClick={() => handleTypeSelect("bug")}
                className="flex items-center gap-4 rounded-lg border p-4 text-left hover:bg-muted transition-colors"
              >
                <Bug className="h-8 w-8 text-destructive" />
                <div>
                  <p className="font-medium">Report a Bug</p>
                  <p className="text-sm text-muted-foreground">
                    Something isn&apos;t working as expected
                  </p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => handleTypeSelect("feature")}
                className="flex items-center gap-4 rounded-lg border p-4 text-left hover:bg-muted transition-colors"
              >
                <Lightbulb className="h-8 w-8 text-yellow-500" />
                <div>
                  <p className="font-medium">Request a Feature</p>
                  <p className="text-sm text-muted-foreground">
                    Suggest a new feature or improvement
                  </p>
                </div>
              </button>
            </div>
          </>
        )}

        {/* Step 2: Describe Issue */}
        {step === "describe" && (
          <>
            <DialogHeader>
              <DialogTitle>
                {feedbackType === "bug"
                  ? "Describe the Bug"
                  : "Describe Your Feature Request"}
              </DialogTitle>
              <DialogDescription>
                {feedbackType === "bug"
                  ? "Tell us what went wrong. Be as specific as possible."
                  : "Tell us about the feature you'd like to see."}
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-4">
              {error && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}

              <div className="grid gap-2">
                <Label htmlFor="description">Description *</Label>
                <Textarea
                  id="description"
                  placeholder={
                    feedbackType === "bug"
                      ? "When I try to... the app shows... instead of..."
                      : "I would like to be able to..."
                  }
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="min-h-[120px]"
                />
                <p className="text-xs text-muted-foreground">
                  {description.length}/2000 characters (minimum 10)
                </p>
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleBack}>
                Back
              </Button>
              <Button
                type="button"
                onClick={handleDescriptionSubmit}
                disabled={isLoading || description.length < 10}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Getting Questions...
                  </>
                ) : (
                  "Continue"
                )}
              </Button>
            </DialogFooter>
          </>
        )}

        {/* Step 3: Answer Clarifying Questions */}
        {step === "clarify" && (
          <>
            <DialogHeader>
              <DialogTitle>A Few Quick Questions</DialogTitle>
              <DialogDescription>
                Help us understand your{" "}
                {feedbackType === "bug" ? "issue" : "request"} better.
              </DialogDescription>
            </DialogHeader>

            <div className="grid gap-4 py-4 max-h-[400px] overflow-y-auto">
              {error && (
                <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                  {error}
                </div>
              )}

              {questions.map((question, index) => (
                <div key={index} className="grid gap-2">
                  <Label htmlFor={`answer-${index}`} className="text-sm font-medium">
                    {question}
                  </Label>
                  <Textarea
                    id={`answer-${index}`}
                    placeholder="Your answer..."
                    value={answers[index] || ""}
                    onChange={(e) => {
                      const newAnswers = [...answers];
                      newAnswers[index] = e.target.value;
                      setAnswers(newAnswers);
                    }}
                    className="min-h-[80px]"
                  />
                </div>
              ))}
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={handleBack}>
                Back
              </Button>
              <Button
                type="button"
                onClick={handleSubmit}
                disabled={isLoading || answers.some((a) => a.trim().length === 0)}
              >
                Submit Feedback
              </Button>
            </DialogFooter>
          </>
        )}

        {/* Step 4: Submitting */}
        {step === "submitting" && (
          <>
            <DialogHeader>
              <DialogTitle>Submitting Feedback</DialogTitle>
              <DialogDescription>
                Creating your GitHub issue...
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col items-center justify-center py-8">
              <Loader2 className="h-12 w-12 animate-spin text-primary" />
              <p className="mt-4 text-sm text-muted-foreground">Please wait...</p>
            </div>
          </>
        )}

        {/* Step 5: Success */}
        {step === "success" && (
          <>
            <DialogHeader>
              <DialogTitle>Thank You!</DialogTitle>
              <DialogDescription>
                Your feedback has been submitted successfully.
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col items-center justify-center py-8">
              <CheckCircle className="h-12 w-12 text-green-500" />
              <p className="mt-4 text-center text-sm text-muted-foreground">
                A GitHub issue has been created for your feedback.
              </p>
              {issueUrl && (
                <a
                  href={issueUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 text-sm text-primary hover:underline"
                >
                  View Issue
                </a>
              )}
            </div>

            <DialogFooter>
              <Button type="button" onClick={() => onOpenChange(false)}>
                Close
              </Button>
            </DialogFooter>
          </>
        )}

        {/* Step 6: Error */}
        {step === "error" && (
          <>
            <DialogHeader>
              <DialogTitle>Submission Failed</DialogTitle>
              <DialogDescription>
                We couldn&apos;t submit your feedback.
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col items-center justify-center py-8">
              <AlertCircle className="h-12 w-12 text-destructive" />
              <p className="mt-4 text-center text-sm text-destructive">
                {error || "An unexpected error occurred. Please try again."}
              </p>
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="button" onClick={handleBack}>
                Try Again
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
