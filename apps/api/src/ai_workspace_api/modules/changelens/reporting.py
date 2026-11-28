"""GitHub Check Run & PR summary reporting for ChangeLens."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class CheckConclusion(str, enum.Enum):
    SUCCESS = "success"
    NEUTRAL = "neutral"
    ACTION_REQUIRED = "action_required"
    FAILURE = "failure"


class AnnotationLevel(str, enum.Enum):
    NOTICE = "notice"
    WARNING = "warning"
    FAILURE = "failure"


@dataclass(frozen=True)
class CheckAnnotation:
    path: str
    start_line: int
    end_line: int
    annotation_level: AnnotationLevel
    message: str
    title: str | None = None

    def to_github_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "start_line": max(1, self.start_line),
            "end_line": max(1, self.end_line),
            "annotation_level": self.annotation_level.value,
            "message": self.message,
        }
        if self.title:
            payload["title"] = self.title
        return payload


@dataclass(frozen=True)
class CheckRunPayload:
    name: str
    head_sha: str
    conclusion: CheckConclusion
    output_title: str
    output_summary: str
    output_text: str = ""
    status: str = "completed"
    annotations: list[CheckAnnotation] = field(default_factory=list)

    def to_github_dict(self) -> dict[str, Any]:
        # GitHub Check Runs API accepts at most 50 annotations per request
        output: dict[str, Any] = {
            "title": self.output_title,
            "summary": self.output_summary,
        }
        if self.output_text:
            output["text"] = self.output_text
        if self.annotations:
            output["annotations"] = [a.to_github_dict() for a in self.annotations[:50]]

        return {
            "name": self.name,
            "head_sha": self.head_sha,
            "status": self.status,
            "conclusion": self.conclusion.value,
            "output": output,
        }
