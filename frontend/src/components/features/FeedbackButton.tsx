/**
 * Feedback trigger button component.
 */

import { Button } from "@/components/ui/button";
import { MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

interface FeedbackButtonProps {
  onClick: () => void;
  className?: string;
}

export function FeedbackButton({ onClick, className }: FeedbackButtonProps) {
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onClick}
      title="Submit Feedback"
      aria-label="Submit Feedback"
      className={cn(className)}
    >
      <MessageSquare className="h-5 w-5" />
    </Button>
  );
}
