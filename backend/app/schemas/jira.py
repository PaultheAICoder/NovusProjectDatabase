"""Jira integration Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JiraUser(BaseModel):
    """Jira user information."""

    account_id: str | None = Field(None, description="Atlassian account ID")
    display_name: str | None = Field(None, description="User display name")
    email_address: str | None = Field(None, description="User email")

    model_config = ConfigDict(extra="ignore")


class JiraIssueType(BaseModel):
    """Jira issue type."""

    id: str = Field(..., description="Issue type ID")
    name: str = Field(..., description="Issue type name (Bug, Story, Epic, etc.)")

    model_config = ConfigDict(extra="ignore")


class JiraStatus(BaseModel):
    """Jira issue status."""

    id: str = Field(..., description="Status ID")
    name: str = Field(..., description="Status name (To Do, In Progress, Done, etc.)")
    category_key: str | None = Field(None, description="Status category key")

    model_config = ConfigDict(extra="ignore")


class JiraIssue(BaseModel):
    """Jira issue details."""

    id: str = Field(..., description="Jira issue ID")
    key: str = Field(..., description="Issue key (e.g., PROJ-123)")
    summary: str = Field(..., description="Issue summary/title")
    status: JiraStatus = Field(..., description="Current status")
    issue_type: JiraIssueType = Field(..., description="Issue type")
    assignee: JiraUser | None = Field(None, description="Assigned user")
    reporter: JiraUser | None = Field(None, description="Issue reporter")
    created: datetime | None = Field(None, description="Creation timestamp")
    updated: datetime | None = Field(None, description="Last update timestamp")
    url: str | None = Field(None, description="Browser URL for this issue")

    model_config = ConfigDict(extra="ignore")


class JiraProject(BaseModel):
    """Jira project details."""

    id: str = Field(..., description="Jira project ID")
    key: str = Field(..., description="Project key (e.g., PROJ)")
    name: str = Field(..., description="Project name")

    model_config = ConfigDict(extra="ignore")


class JiraConnectionStatus(BaseModel):
    """Result from connection validation."""

    is_connected: bool = Field(..., description="Whether connection succeeded")
    user_display_name: str | None = Field(None, description="Authenticated user name")
    server_info: str | None = Field(None, description="Jira server version/info")
    error: str | None = Field(None, description="Error message if connection failed")


class JiraParsedUrl(BaseModel):
    """Parsed components from a Jira URL."""

    base_url: str = Field(..., description="Jira instance base URL")
    project_key: str = Field(..., description="Project key extracted from URL")
    issue_key: str | None = Field(
        None, description="Issue key if URL points to specific issue"
    )


__all__ = [
    "JiraUser",
    "JiraIssueType",
    "JiraStatus",
    "JiraIssue",
    "JiraProject",
    "JiraConnectionStatus",
    "JiraParsedUrl",
]
