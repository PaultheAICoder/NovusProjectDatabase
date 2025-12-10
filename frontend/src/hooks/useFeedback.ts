/**
 * Feedback hooks with TanStack Query.
 */

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  FeedbackClarifyRequest,
  FeedbackClarifyResponse,
  FeedbackSubmitRequest,
  FeedbackSubmitResponse,
} from "@/types/feedback";

export function useClarifyQuestions() {
  return useMutation({
    mutationFn: (data: FeedbackClarifyRequest) =>
      api.post<FeedbackClarifyResponse>("/feedback/clarify", data),
  });
}

export function useSubmitFeedback() {
  return useMutation({
    mutationFn: (data: FeedbackSubmitRequest) =>
      api.post<FeedbackSubmitResponse>("/feedback", data),
  });
}
