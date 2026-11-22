import datetime

from ai_workspace_api.modules.changelens.history_analysis import (
    GitHistoryAnalyzer,
)


def test_empty_history_returns_dampened_confidence_and_conservative_risk() -> None:
    analyzer = GitHistoryAnalyzer()
    result = analyzer.analyze_history(target_files=["src/auth.py"], commit_history=[])

    assert result.is_shallow_history is True
    assert result.history_confidence <= 0.2
    assert result.history_risk_score == 5.0
    assert len(result.assumptions_and_unknowns) >= 1
    assert "No git history available" in result.assumptions_and_unknowns[0]


def test_file_churn_calculation_with_author_tracking() -> None:
    now = datetime.datetime.now(datetime.UTC)
    commits = [
        {
            "sha": "c1",
            "author": "Alice",
            "date": now,
            "files": [{"path": "src/auth.py", "added": 20, "deleted": 5}],
        },
        {
            "sha": "c2",
            "author": "Bob",
            "date": now,
            "files": [{"path": "src/auth.py", "added": 10, "deleted": 0}],
        },
        {
            "sha": "c3",
            "author": "Alice",
            "date": now,
            "files": [{"path": "src/auth.py", "added": 5, "deleted": 2}],
        },
    ]

    analyzer = GitHistoryAnalyzer(min_commits_for_confidence=3)
    result = analyzer.analyze_history(
        target_files=["src/auth.py"],
        commit_history=commits,
    )

    assert "src/auth.py" in result.file_churn
    stats = result.file_churn["src/auth.py"]
    assert stats.commit_count == 3
    assert stats.lines_added == 35
    assert stats.lines_deleted == 7
    assert stats.unique_authors == 2
    assert stats.churn_score == 0.6


def test_co_modification_detection_finds_coupled_files() -> None:
    now = datetime.datetime.now(datetime.UTC)
    commits = [
        {
            "sha": f"c{i}",
            "author": "Alice",
            "date": now,
            "files": [
                {"path": "src/auth.py", "added": 5, "deleted": 0},
                {"path": "src/models/user.py", "added": 2, "deleted": 0},
            ],
        }
        for i in range(4)
    ]
    # Add one commit where only auth.py changes
    commits.append(
        {
            "sha": "c5",
            "author": "Bob",
            "date": now,
            "files": [{"path": "src/auth.py", "added": 1, "deleted": 1}],
        }
    )

    analyzer = GitHistoryAnalyzer(min_commits_for_confidence=5, min_co_change_support=0.5)
    result = analyzer.analyze_history(
        target_files=["src/auth.py"],
        commit_history=commits,
    )

    assert len(result.frequently_co_changed_files) >= 1
    pair = result.frequently_co_changed_files[0]
    assert pair.file_a == "src/auth.py"
    assert pair.file_b == "src/models/user.py"
    assert pair.co_change_count == 4
    assert pair.support_ratio == 0.8  # 4 out of 5 commits


def test_shallow_history_dampens_confidence() -> None:
    commits = [
        {"sha": "c1", "author": "Alice", "files": [{"path": "src/api.py", "added": 10, "deleted": 0}]}
    ]

    analyzer = GitHistoryAnalyzer(min_commits_for_confidence=10)
    result = analyzer.analyze_history(target_files=["src/api.py"], commit_history=commits)

    assert result.is_shallow_history is True
    assert result.history_confidence < 0.5
    assert any("Shallow commit history" in u for u in result.assumptions_and_unknowns)
