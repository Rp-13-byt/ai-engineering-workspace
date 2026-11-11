from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class GitHubRepository:
    owner: str
    name: str
    default_branch: str
    clone_url: str
    private: bool


class GitHubClient:
    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def get_repository(self, owner: str, name: str) -> GitHubRepository:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{name}",
                headers=self._headers(),
            )
            response.raise_for_status()
        payload = response.json()
        return GitHubRepository(
            owner=payload["owner"]["login"],
            name=payload["name"],
            default_branch=payload["default_branch"],
            clone_url=payload["clone_url"],
            private=payload["private"],
        )

    async def get_tree(self, owner: str, name: str, branch: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=30) as client:
            branch_response = await client.get(
                f"https://api.github.com/repos/{owner}/{name}/branches/{branch}",
                headers=self._headers(),
            )
            branch_response.raise_for_status()
            sha = branch_response.json()["commit"]["commit"]["tree"]["sha"]
            tree_response = await client.get(
                f"https://api.github.com/repos/{owner}/{name}/git/trees/{sha}?recursive=1",
                headers=self._headers(),
            )
            tree_response.raise_for_status()
        return tree_response.json().get("tree", [])

    async def get_file_content(self, owner: str, name: str, path: str, ref: str) -> str:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"https://raw.githubusercontent.com/{owner}/{name}/{ref}/{path}",
                headers=self._headers(),
            )
            response.raise_for_status()
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
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"https://api.github.com/repos/{owner}/{name}/pulls",
                headers=self._headers(),
                json={"title": title, "body": body, "head": head, "base": base},
            )
            response.raise_for_status()
        return str(response.json()["html_url"])
