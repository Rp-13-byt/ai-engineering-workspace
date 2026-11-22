from collections import defaultdict
from dataclasses import dataclass, field
import datetime
from typing import Any


@dataclass(frozen=True)
class FileChurnStats:
    file_path: str
    commit_count: int
    lines_added: int
    lines_deleted: int
    unique_authors: int
    last_modified: datetime.datetime | None = None
    churn_score: float = 0.0  # 0.0 to 1.0 normalized score


@dataclass(frozen=True)
class CoModificationPair:
    file_a: str
    file_b: str
    co_change_count: int
    support_ratio: float  # Fraction of file_a commits that also changed file_b


@dataclass(frozen=True)
class HistoryAnalysisResult:
    target_files: list[str]
    file_churn: dict[str, FileChurnStats]
    frequently_co_changed_files: list[CoModificationPair]
    historical_commits_examined: int
    is_shallow_history: bool
    history_confidence: float  # 0.0 to 1.0
    history_risk_score: float  # 0 to 15 points
    assumptions_and_unknowns: list[str] = field(default_factory=list)


class GitHistoryAnalyzer:
    """Analyzes recent commit churn, file co-modifications, and history confidence."""

    def __init__(
        self,
        max_commits: int = 50,
        min_co_change_support: float = 0.3,
        min_commits_for_confidence: int = 10,
    ) -> None:
        self.max_commits = max_commits
        self.min_co_change_support = min_co_change_support
        self.min_commits_for_confidence = min_commits_for_confidence

    def analyze_history(
        self,
        target_files: list[str],
        commit_history: list[dict[str, Any]] | None = None,
        is_shallow: bool = False,
    ) -> HistoryAnalysisResult:
        if not commit_history:
            return HistoryAnalysisResult(
                target_files=target_files,
                file_churn={},
                frequently_co_changed_files=[],
                historical_commits_examined=0,
                is_shallow_history=True,
                history_confidence=0.1,
                history_risk_score=5.0,  # Conservative baseline under unknown history
                assumptions_and_unknowns=[
                    "No git history available; historical churn and co-modifications cannot be computed.",
                    "Assuming neutral baseline history risk due to missing commit history.",
                ],
            )

        commits_window = commit_history[: self.max_commits]
        total_examined = len(commits_window)
        unknowns: list[str] = []

        # Determine history confidence
        if is_shallow or total_examined < self.min_commits_for_confidence:
            is_shallow_flag = True
            confidence = round(max(0.2, total_examined / self.min_commits_for_confidence * 0.6), 2)
            unknowns.append(
                f"Shallow commit history detected ({total_examined} commits in window < "
                f"{self.min_commits_for_confidence} required); co-change confidence dampened."
            )
        else:
            is_shallow_flag = False
            confidence = 0.95

        # Compute per-file churn
        file_commit_counts: dict[str, int] = defaultdict(int)
        file_lines_added: dict[str, int] = defaultdict(int)
        file_lines_deleted: dict[str, int] = defaultdict(int)
        file_authors: dict[str, set[str]] = defaultdict(set)
        file_last_date: dict[str, datetime.datetime | None] = {}

        # Co-modification tracking
        co_occurrence: dict[tuple[str, str], int] = defaultdict(int)

        for commit in commits_window:
            author = str(commit.get("author", "unknown"))
            commit_date = commit.get("date")
            files_in_commit = commit.get("files", [])

            changed_in_this_commit: set[str] = set()
            for f in files_in_commit:
                if isinstance(f, dict):
                    f_path = f.get("path", "")
                    added = int(f.get("added", 0))
                    deleted = int(f.get("deleted", 0))
                else:
                    f_path = str(f)
                    added = 0
                    deleted = 0

                if f_path:
                    changed_in_this_commit.add(f_path)
                    file_commit_counts[f_path] += 1
                    file_lines_added[f_path] += added
                    file_lines_deleted[f_path] += deleted
                    file_authors[f_path].add(author)
                    if f_path not in file_last_date and isinstance(commit_date, datetime.datetime):
                        file_last_date[f_path] = commit_date

            # Record pairwise co-occurrence
            changed_list = sorted(changed_in_this_commit)
            for i, fa in enumerate(changed_list):
                for fb in changed_list[i + 1 :]:
                    co_occurrence[(fa, fb)] += 1
                    co_occurrence[(fb, fa)] += 1

        # Build stats for target files
        churn_stats: dict[str, FileChurnStats] = {}
        for target in target_files:
            c_count = file_commit_counts.get(target, 0)
            added = file_lines_added.get(target, 0)
            deleted = file_lines_deleted.get(target, 0)
            auth_count = len(file_authors.get(target, set()))

            # Churn score: high change frequency in window increases churn
            # Normalized against window (5+ commits = 1.0)
            c_score = min(1.0, round(c_count / 5.0, 2)) if total_examined > 0 else 0.0

            churn_stats[target] = FileChurnStats(
                file_path=target,
                commit_count=c_count,
                lines_added=added,
                lines_deleted=deleted,
                unique_authors=auth_count,
                last_modified=file_last_date.get(target),
                churn_score=c_score,
            )

        # Detect co-modification pairs for target files
        co_mod_pairs: list[CoModificationPair] = []
        for target in target_files:
            target_commits = file_commit_counts.get(target, 0)
            if target_commits == 0:
                continue

            for (fa, fb), count in co_occurrence.items():
                if fa == target and count >= 2:
                    ratio = round(count / target_commits, 2)
                    if ratio >= self.min_co_change_support:
                        co_mod_pairs.append(
                            CoModificationPair(
                                file_a=fa,
                                file_b=fb,
                                co_change_count=count,
                                support_ratio=ratio,
                            )
                        )

        # Sort co-modifications by support ratio descending
        co_mod_pairs.sort(key=lambda p: (p.support_ratio, p.co_change_count), reverse=True)

        # Compute history risk score (0 to 15 points)
        # Factor A: high churn files (> 3 commits in window)
        high_churn_count = sum(1 for s in churn_stats.values() if s.commit_count >= 3)
        # Factor B: co-modified files not in target set (hidden coupled dependencies)
        coupled_non_targets = {
            p.file_b for p in co_mod_pairs if p.file_b not in target_files
        }

        raw_risk = (high_churn_count * 3.5) + (len(coupled_non_targets) * 2.5)
        # Scale by confidence
        scaled_risk = raw_risk * confidence
        final_risk = min(15.0, round(scaled_risk, 2))

        return HistoryAnalysisResult(
            target_files=target_files,
            file_churn=churn_stats,
            frequently_co_changed_files=co_mod_pairs,
            historical_commits_examined=total_examined,
            is_shallow_history=is_shallow_flag,
            history_confidence=confidence,
            history_risk_score=final_risk,
            assumptions_and_unknowns=unknowns,
        )
