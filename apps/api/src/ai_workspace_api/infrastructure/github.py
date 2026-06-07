import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitHubRepository:
    owner: str
    name: str
    default_branch: str
    clone_url: str
    private: bool


@dataclass(frozen=True)
class ChangedFile:
    filename: str
    status: Literal["added", "modified", "removed", "renamed", "copied", "changed", "unchanged"]


class GitHubClient:
    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token
        self._client: httpx.AsyncClient | None = None
        self._semaphore = asyncio.Semaphore(10)

    async def __aenter__(self) -> "GitHubClient":
        self._client = httpx.AsyncClient(timeout=30)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Execute request with exponential backoff for rate limits."""
        if not self._client:
            raise RuntimeError("GitHubClient must be used as an async context manager")

        retries = 3
        backoff = 1.0

        for attempt in range(retries + 1):
            async with self._semaphore:
                response = await self._client.request(method, url, headers=self._headers(), **kwargs)

            if response.status_code == 403 and "x-ratelimit-remaining" in response.headers:
                remaining = int(response.headers.get("x-ratelimit-remaining", "1"))
                if remaining == 0:
                    retry_after = int(response.headers.get("retry-after", "60"))
                    logger.warning(f"GitHub API rate limit exceeded. Waiting {retry_after}s.")
                    await asyncio.sleep(retry_after)
                    continue

            if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                import random
                jitter = random.uniform(0.1, 0.5)
                logger.warning(f"GitHub API transient error {response.status_code}. Retrying in {backoff + jitter:.2f}s.")
                await asyncio.sleep(backoff + jitter)
                backoff *= 2
                continue

            response.raise_for_status()
            return response
            
        raise httpx.HTTPStatusError("Max retries exceeded", request=response.request, response=response)

    async def get_repository(self, owner: str, name: str) -> GitHubRepository:
        response = await self._request("GET", f"https://api.github.com/repos/{owner}/{name}")
        payload = response.json()
        return GitHubRepository(
            owner=payload["owner"]["login"],
            name=payload["name"],
            default_branch=payload["default_branch"],
            clone_url=payload["clone_url"],
            private=payload["private"],
        )

    async def get_tree(self, owner: str, name: str, branch: str) -> list[dict]:
        branch_response = await self._request("GET", f"https://api.github.com/repos/{owner}/{name}/branches/{branch}")
        sha = branch_response.json()["commit"]["commit"]["tree"]["sha"]
        tree_response = await self._request("GET", f"https://api.github.com/repos/{owner}/{name}/git/trees/{sha}?recursive=1")
        return tree_response.json().get("tree", [])

    async def get_commit_sha(self, owner: str, name: str, branch: str) -> str:
        response = await self._request("GET", f"https://api.github.com/repos/{owner}/{name}/commits/{branch}")
        return response.json()["sha"]

    async def compare_commits(self, owner: str, name: str, base_sha: str, head_sha: str) -> list[ChangedFile]:
        response = await self._request("GET", f"https://api.github.com/repos/{owner}/{name}/compare/{base_sha}...{head_sha}")
        files = response.json().get("files", [])
        return [
            ChangedFile(
                filename=f["filename"],
                status=f["status"],
            )
            for f in files
        ]

    async def get_file_content(self, owner: str, name: str, path: str, ref: str) -> str:
        # Note: raw.githubusercontent.com doesn't use the standard API rate limit, but it has its own limits
        url = f"https://raw.githubusercontent.com/{owner}/{name}/{ref}/{path}"
        response = await self._request("GET", url)
        return response.text

    async def open_pull_request(
        self,
        owner: str,
        name: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> str:
        response = await self._request(
            "POST", 
            f"https://api.github.com/repos/{owner}/{name}/pulls",
            json={"title": title, "body": body, "head": head, "base": base},
        )
        return str(response.json()["html_url"])
