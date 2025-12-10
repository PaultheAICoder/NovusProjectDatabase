/**
 * Feedback types matching backend Pydantic schemas.
 */

export type FeedbackType = "bug" | "feature";

export type FeedbackStep =
  | "select-type"
  | "describe"
  | "clarify"
  | "submitting"
  | "success"
  | "error";

export interface FeedbackClarifyRequest {
  feedback_type: FeedbackType;
  description: string;
}

export interface FeedbackClarifyResponse {
  questions: string[];
}

export interface FeedbackSubmitRequest {
  feedback_type: FeedbackType;
  title: string;
  description: string;
  clarifying_answers: string[];
}

export interface FeedbackSubmitResponse {
  feedback_id: string;
  github_issue_number: number;
  github_issue_url: string;
  message: string;
}
