import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.models import ChatMessage
from ai_workspace_api.infrastructure.embedding import create_embedding_provider

try:
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_openai import ChatOpenAI
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    BaseChatModel = Any  # type: ignore
@dataclass(frozen=True)
class RetrievedContext:
    path: str
    start_line: int
    end_line: int
    content: str
    score: float


class BugFinding(BaseModel):
    path: str = Field(description="The file path where the issue was found")
    severity: str = Field(description="Severity of the issue: critical, high, medium, low")
    message: str = Field(description="Description of the bug or issue")


class BugReport(BaseModel):
    findings: list[BugFinding]


class LLMGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._embedding_provider = create_embedding_provider(settings)
        self._chat_model = self._create_chat_model(settings)

    def _create_chat_model(self, settings: Settings) -> "BaseChatModel | None":
        if not HAS_LANGCHAIN:
            return None
            
        openai_model = ChatOpenAI(model="gpt-4o", api_key=settings.openai_api_key.get_secret_value(), temperature=0.0) if settings.openai_api_key else None
        gemini_model = ChatGoogleGenerativeAI(model="gemini-1.5-pro", api_key=settings.gemini_api_key.get_secret_value(), temperature=0.0) if settings.gemini_api_key else None
        
        provider_name = settings.default_llm_provider.lower()
        primary = openai_model if provider_name == "openai" else gemini_model
        fallback = gemini_model if provider_name == "openai" else openai_model
        
        if not primary:
            primary, fallback = fallback, None
            
        if not primary:
            return None
            
        if fallback:
            return primary.with_fallbacks([fallback])
        return primary

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._embedding_provider.embed(texts)

    async def answer_code_question(self, question: str, contexts: list[RetrievedContext], history: list[ChatMessage] | None = None) -> str:
        if not contexts:
            return (
                "I could not find indexed context for that repository yet. "
                "Import and index the repository, then ask again."
            )
        if not self._chat_model:
            return "LLM integration is not configured. Please set OPENAI_API_KEY or GEMINI_API_KEY."

        system_prompt = (
            "You are a Staff Software Engineer at Google. "
            "You are answering questions about a codebase. "
            "Use the provided code context to answer the user's questions accurately. "
            "If the answer is not in the context, say you don't know based on the provided context.\\n\\n"
            "CONTEXT:\\n"
        )
        for ctx in contexts:
            system_prompt += f"--- {ctx.path}:{ctx.start_line}-{ctx.end_line} ---\\n{ctx.content}\\n\\n"

        messages: list[Any] = [SystemMessage(content=system_prompt)]
        
        if history:
            for msg in history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))

        messages.append(HumanMessage(content=question))
        response = await self._chat_model.ainvoke(messages)
        return str(response.content)

    async def generate_pull_request(self, instructions: str, contexts: list[RetrievedContext]) -> dict[str, str]:
        if not self._chat_model:
            return {"title": "Not Configured", "body": "LLM not configured.", "branch_name": "ai/error", "diff": ""}
            
        system_prompt = (
            "You are an AI automated coding agent. "
            "Given the user's instructions and the code contexts, generate a Pull Request to implement the change. "
            "Return ONLY a valid JSON object matching this schema:\\n"
            '{"title": "PR Title", "body": "Markdown body of PR", "branch_name": "suggested-branch-name", "diff": "Valid unified git diff of the proposed changes"}\\n\\n'
            "CONTEXT:\\n"
        )
        for ctx in contexts:
            system_prompt += f"--- {ctx.path}:{ctx.start_line}-{ctx.end_line} ---\\n{ctx.content}\\n\\n"

        response = await self._chat_model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=instructions)
        ])
        
        try:
            content = str(response.content)
            if content.startswith("```json"):
                content = content[7:-3]
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "title": f"AI change: {instructions[:72]}",
                "body": "Failed to parse JSON from LLM.\\n\\n" + str(response.content),
                "branch_name": "ai/workspace-generated-change",
                "diff": "",
            }

    async def generate_tests(self, target: str, contexts: list[RetrievedContext]) -> str:
        if not self._chat_model:
            return "LLM not configured."
            
        system_prompt = (
            "You are a Staff SDET. Generate comprehensive unit and integration tests for the specified target. "
            "Ensure you cover edge cases, error paths, and concurrency if applicable. "
            "Return only the test code, no markdown wrappers unless requested.\\n\\n"
            "CONTEXT:\\n"
        )
        for ctx in contexts:
            system_prompt += f"--- {ctx.path}:{ctx.start_line}-{ctx.end_line} ---\\n{ctx.content}\\n\\n"
            
        response = await self._chat_model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Target: {target}")
        ])
        return str(response.content)

    async def detect_bugs(self, contexts: list[RetrievedContext]) -> list[dict[str, str]]:
        if not self._chat_model:
            return []
            
        if not contexts:
            return []
            
        system_prompt = (
            "You are a security researcher and Staff Engineer reviewing code. "
            "Identify bugs, race conditions, security flaws, or unresolved TODOs in the provided context."
        )
        context_str = ""
        for ctx in contexts:
            context_str += f"--- {ctx.path}:{ctx.start_line}-{ctx.end_line} ---\\n{ctx.content}\\n\\n"
            
        try:
            # We use with_structured_output for guaranteed JSON schema matching
            structured_llm = self._chat_model.with_structured_output(BugReport)
            report: BugReport = await structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Review this code:\\n\\n{context_str}")
            ])
            return [finding.model_dump() for finding in report.findings]
        except Exception:
            return []

    async def generate_documentation(self, target: str, contexts: list[RetrievedContext]) -> str:
        if not self._chat_model:
            return "LLM not configured."
            
        system_prompt = (
            "You are an expert Technical Writer. Generate production-quality markdown documentation for the specified target based on the context. "
            "Include architecture overview, usage examples, and API references where applicable.\\n\\n"
            "CONTEXT:\\n"
        )
        for ctx in contexts:
            system_prompt += f"--- {ctx.path}:{ctx.start_line}-{ctx.end_line} ---\\n{ctx.content}\\n\\n"
            
        response = await self._chat_model.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Target: {target}")
        ])
        return str(response.content)

    def _deterministic_embedding(self, text: str) -> list[float]:  # deprecated
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(self.settings.embedding_dimensions)]
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def _sample_diff(self, instructions: str, contexts: list[RetrievedContext]) -> str:
        path = contexts[0].path if contexts else "README.md"
        return (
            f"diff --git a/{path} b/{path}\n"
            "--- a/{path}\n"
            "+++ b/{path}\n"
            "@@\n"
            f"+# AI-generated implementation note: {instructions}\n"
        )
