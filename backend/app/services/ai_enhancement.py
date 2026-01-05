"""AI enhancement service for feedback clarification and issue generation.

Provides AI-powered features:
- Generate clarifying questions for bug/feature submissions
- Enhance issue descriptions using Claude Code CLI (with API fallback)
"""

import asyncio
import json
import re
import shutil
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Safety limits for Claude Code execution
CLAUDE_CODE_TIMEOUT_SECONDS = 60
MAX_OUTPUT_SIZE = 100_000  # 100KB max output


@dataclass
class ClarifyingQuestionsResult:
    """Result of generating clarifying questions."""

    questions: list[str]
    error: str | None = None


@dataclass
class EnhanceIssueResult:
    """Result of enhancing an issue with AI."""

    success: bool
    title: str
    body: str
    error: str | None = None


class AIEnhancementService:
    """Service for AI-powered feedback enhancement."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def _get_fallback_questions(self, feedback_type: str) -> list[str]:
        """Get fallback questions if API unavailable."""
        if feedback_type == "bug":
            return [
                "What steps can we follow to reproduce this issue?",
                "What did you expect to happen instead?",
                "When did you first notice this problem?",
            ]
        else:
            return [
                "What problem would this feature solve for you?",
                "How would you ideally use this feature?",
                "How important is this feature to your workflow?",
            ]

    async def generate_clarifying_questions(
        self,
        feedback_type: str,
        description: str,
    ) -> ClarifyingQuestionsResult:
        """Generate 3 clarifying questions for a feedback submission.

        Args:
            feedback_type: Either 'bug' or 'feature'
            description: User's description of the issue/feature

        Returns:
            ClarifyingQuestionsResult with questions or fallback
        """
        fallback_questions = self._get_fallback_questions(feedback_type)

        if not self.settings.is_ai_configured:
            logger.info("ai_not_configured", using="fallback_questions")
            return ClarifyingQuestionsResult(questions=fallback_questions)

        try:
            system_prompt = self._build_questions_system_prompt(feedback_type)
            user_message = f"{feedback_type.title()} Report: {description}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 300,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_message}],
                    },
                )
                response.raise_for_status()
                data = response.json()

            # Extract text from response
            content = data.get("content", [])
            text_block = next(
                (block for block in content if block.get("type") == "text"),
                None,
            )

            if not text_block:
                return ClarifyingQuestionsResult(questions=fallback_questions)

            # Parse questions from response (one per line)
            text = text_block.get("text", "")
            questions = [
                q.strip()
                for q in text.split("\n")
                if q.strip() and len(q.strip()) < 150
            ][:3]

            # Ensure we have exactly 3 questions
            if len(questions) < 3:
                return ClarifyingQuestionsResult(questions=fallback_questions)

            logger.info(
                "clarifying_questions_generated",
                feedback_type=feedback_type,
                question_count=len(questions),
            )

            return ClarifyingQuestionsResult(questions=questions)

        except httpx.HTTPError as e:
            logger.warning(
                "clarifying_questions_api_error",
                error=str(e),
                using="fallback_questions",
            )
            return ClarifyingQuestionsResult(
                questions=fallback_questions,
                error=str(e),
            )
        except Exception as e:
            logger.error(
                "clarifying_questions_error",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return ClarifyingQuestionsResult(
                questions=fallback_questions,
                error=str(e),
            )

    def _build_questions_system_prompt(self, feedback_type: str) -> str:
        """Build system prompt for generating questions."""
        if feedback_type == "bug":
            return (
                "You are helping gather information about a software bug report. "
                "Based on the user's initial description, generate exactly 3 specific, "
                "targeted clarifying questions that would help developers understand and "
                "fix the issue. Focus on: reproduction steps, expected vs actual behavior, "
                "and environment/context. Each question should be concise (under 100 "
                "characters). Return ONLY the 3 questions, one per line, without "
                "numbering or bullets."
            )
        else:
            return (
                "You are helping gather information about a software feature request. "
                "Based on the user's initial description, generate exactly 3 specific, "
                "targeted clarifying questions that would help developers understand and "
                "implement the feature. Focus on: use cases, expected behavior, and "
                "priority/importance. Each question should be concise (under 100 "
                "characters). Return ONLY the 3 questions, one per line, without "
                "numbering or bullets."
            )

    async def enhance_issue(
        self,
        feedback_type: str,
        description: str,
        answers: list[str],
    ) -> EnhanceIssueResult:
        """Enhance a feedback submission into a well-structured GitHub issue.

        Attempts to use Claude Code CLI first, falls back to API if unavailable.

        Args:
            feedback_type: Either 'bug' or 'feature'
            description: User's description
            answers: Answers to clarifying questions

        Returns:
            EnhanceIssueResult with title and body
        """
        # Try Claude Code CLI first
        claude_path = shutil.which(self.settings.claude_code_path)

        if claude_path:
            try:
                result = await self._enhance_with_claude_code(
                    feedback_type, description, answers
                )
                if result.success:
                    return result
            except TimeoutError as e:
                logger.warning(
                    "claude_code_timeout",
                    error=str(e),
                    falling_back_to="api",
                    exc_info=True,
                )
            except RuntimeError as e:
                logger.warning(
                    "claude_code_process_error",
                    error=str(e),
                    falling_back_to="api",
                    exc_info=True,
                )
            except Exception as e:
                logger.warning(
                    "claude_code_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    falling_back_to="api",
                    exc_info=True,
                )

        # Fall back to API
        if self.settings.is_ai_configured:
            try:
                return await self._enhance_with_api(feedback_type, description, answers)
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "enhance_api_http_error",
                    status_code=e.response.status_code,
                    error=str(e),
                    falling_back_to="simple_format",
                    exc_info=True,
                )
            except httpx.TimeoutException as e:
                logger.warning(
                    "enhance_api_timeout",
                    error=str(e),
                    falling_back_to="simple_format",
                    exc_info=True,
                )
            except httpx.RequestError as e:
                logger.warning(
                    "enhance_api_connection_error",
                    error=str(e),
                    error_type=type(e).__name__,
                    falling_back_to="simple_format",
                    exc_info=True,
                )

        # Final fallback to simple formatting
        return self._format_fallback_issue(feedback_type, description, answers)

    async def _enhance_with_claude_code(
        self,
        feedback_type: str,
        description: str,
        answers: list[str],
    ) -> EnhanceIssueResult:
        """Enhance issue using Claude Code CLI."""
        user_context = self._build_user_context(feedback_type, description, answers)
        system_prompt = self._build_enhance_system_prompt(feedback_type)

        claude_path = self.settings.claude_code_path
        args = [
            claude_path,
            "-p",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
            "--system-prompt",
            system_prompt,
            user_context,
        ]

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=CLAUDE_CODE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            process.kill()
            raise TimeoutError("Claude Code execution timed out")

        if process.returncode != 0:
            raise RuntimeError(
                f"Claude Code exited with code {process.returncode}: {stderr.decode()}"
            )

        output = stdout.decode()
        if len(output) > MAX_OUTPUT_SIZE:
            raise ValueError("Output size limit exceeded")

        return self._parse_claude_output(output, feedback_type, description, answers)

    async def _enhance_with_api(
        self,
        feedback_type: str,
        description: str,
        answers: list[str],
    ) -> EnhanceIssueResult:
        """Enhance issue using Anthropic API."""
        user_context = self._build_user_context(feedback_type, description, answers)
        system_prompt = self._build_enhance_system_prompt(feedback_type)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2000,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_context}],
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data.get("content", [])
        text_block = next(
            (block for block in content if block.get("type") == "text"),
            None,
        )

        if not text_block:
            return self._format_fallback_issue(feedback_type, description, answers)

        text = text_block.get("text", "")

        # Try to extract JSON from response
        try:
            json_match = json.loads(text)
            if "title" in json_match and "body" in json_match:
                return EnhanceIssueResult(
                    success=True,
                    title=json_match["title"][:80],
                    body=json_match["body"],
                )
        except json.JSONDecodeError:
            # Try to find JSON in text
            match = re.search(r'\{[\s\S]*"title"[\s\S]*"body"[\s\S]*\}', text)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    return EnhanceIssueResult(
                        success=True,
                        title=parsed["title"][:80],
                        body=parsed["body"],
                    )
                except json.JSONDecodeError:
                    pass

        return self._format_fallback_issue(feedback_type, description, answers)

    def _build_user_context(
        self,
        feedback_type: str,
        description: str,
        answers: list[str],
    ) -> str:
        """Build user context for AI enhancement."""
        label = "Bug Report" if feedback_type == "bug" else "Feature Request"
        fallback = self._get_fallback_questions(feedback_type)

        return f"""{label}:

Description: {description}

Clarifying Questions and Answers:
Q1: {fallback[0]}
A1: {answers[0] if len(answers) > 0 else 'Not provided'}

Q2: {fallback[1]}
A2: {answers[1] if len(answers) > 1 else 'Not provided'}

Q3: {fallback[2]}
A3: {answers[2] if len(answers) > 2 else 'Not provided'}"""

    def _build_enhance_system_prompt(self, feedback_type: str) -> str:
        """Build system prompt for issue enhancement."""
        if feedback_type == "bug":
            return """You are creating a GitHub issue for a bug report. Based on the user's feedback, generate:
1. A clear, concise title (max 80 characters)
2. A comprehensive issue body following this format:

## Reported Issue
**What's broken**: <summarize the issue>
**Expected behavior**: <from user's answer>
**Severity**: <Critical/High/Medium/Low based on impact>

## How to Reproduce
<Based on user's steps, format as numbered list>

## Investigation Notes
- Error pattern detected: <your analysis>
- Likely affected components: <your analysis>

## Next Steps
- Investigate root cause (not just symptom)
- Add regression test to prevent recurrence

Respond with JSON: {"title": "...", "body": "..."}"""
        else:
            return """You are creating a GitHub issue for a feature request. Based on the user's feedback, generate:
1. A clear, concise title (max 80 characters)
2. A comprehensive issue body following this format:

## Feature Description
<summarize what the user wants>

## User Stories
**As a** user
**I want to** <action from description>
**So that** <benefit from user's answer>

## Requirements
- [ ] <specific capability>
- [ ] <workflow requirement>

## Acceptance Criteria
- [ ] Feature works as described
- [ ] No TypeScript/Python errors
- [ ] All tests passing

Respond with JSON: {"title": "...", "body": "..."}"""

    def _parse_claude_output(
        self,
        output: str,
        feedback_type: str,
        description: str,
        answers: list[str],
    ) -> EnhanceIssueResult:
        """Parse Claude Code JSON output."""
        try:
            parsed = json.loads(output)

            text_result = None
            if isinstance(parsed.get("result"), str):
                text_result = parsed["result"]
            elif isinstance(parsed.get("content"), list):
                text_block = next(
                    (b for b in parsed["content"] if b.get("type") == "text"),
                    None,
                )
                if text_block:
                    text_result = text_block.get("text")

            if text_result:
                json_match = re.search(
                    r'\{[\s\S]*"title"[\s\S]*"body"[\s\S]*\}', text_result
                )
                if json_match:
                    inner = json.loads(json_match.group(0))
                    if inner.get("title") and inner.get("body"):
                        return EnhanceIssueResult(
                            success=True,
                            title=inner["title"][:80],
                            body=inner["body"],
                        )

            raise ValueError("Could not parse Claude Code output")

        except Exception as e:
            logger.warning("claude_output_parse_failed", error=str(e))
            return self._format_fallback_issue(feedback_type, description, answers)

    def _format_fallback_issue(
        self,
        feedback_type: str,
        description: str,
        answers: list[str],
    ) -> EnhanceIssueResult:
        """Format a simple fallback issue without AI enhancement."""
        title = description[:77] + "..." if len(description) > 80 else description
        fallback_q = self._get_fallback_questions(feedback_type)

        if feedback_type == "bug":
            body = f"""## Reported Issue
**What's broken**: {description}
**Expected behavior**: {answers[1] if len(answers) > 1 else 'Not specified'}
**Severity**: Medium

## Clarifying Questions & Answers
**Q1**: {fallback_q[0]}
**A1**: {answers[0] if len(answers) > 0 else 'Not provided'}

**Q2**: {fallback_q[1]}
**A2**: {answers[1] if len(answers) > 1 else 'Not provided'}

**Q3**: {fallback_q[2]}
**A3**: {answers[2] if len(answers) > 2 else 'Not provided'}

## Next Steps
- Investigate root cause (not just symptom)
- Add regression test to prevent recurrence"""
        else:
            body = f"""## Feature Description
{description}

## User Stories
**As a** user
**I want to** {description.lower()}
**So that** {answers[0] if len(answers) > 0 else 'it improves my workflow'}

## Clarifying Questions & Answers
**Q1**: {fallback_q[0]}
**A1**: {answers[0] if len(answers) > 0 else 'Not provided'}

**Q2**: {fallback_q[1]}
**A2**: {answers[1] if len(answers) > 1 else 'Not provided'}

**Q3**: {fallback_q[2]}
**A3**: {answers[2] if len(answers) > 2 else 'Not provided'}

## Acceptance Criteria
- [ ] Feature works as described
- [ ] No TypeScript/Python errors
- [ ] All tests passing"""

        return EnhanceIssueResult(
            success=False,
            title=title,
            body=body,
            error="Using fallback formatting",
        )
