import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.models import ChatMessage
from ai_workspace_api.infrastructure.llm import LLMGateway, RetrievedContext

@pytest.fixture
def settings():
    return Settings(
        default_llm_provider="openai",
        openai_api_key="sk-testkey",
    )

@pytest.fixture
def contexts():
    return [
        RetrievedContext(
            path="src/main.py",
            start_line=1,
            end_line=5,
            content="def hello():\n    print('world')",
            score=0.9,
        )
    ]

@pytest.mark.asyncio
async def test_answer_code_question(settings, contexts):
    gateway = LLMGateway(settings)
    
    mock_response = MagicMock()
    mock_response.content = "To say hello, call hello()"
    
    with patch.object(gateway._chat_model, 'ainvoke', new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = mock_response
        
        history = [ChatMessage(role="user", content="Hi", citations=[])]
        answer = await gateway.answer_code_question("How to say hello?", contexts, history)
        
        assert answer == "To say hello, call hello()"
        mock_ainvoke.assert_called_once()
        
        # Verify history was injected
        messages = mock_ainvoke.call_args[0][0]
        assert len(messages) == 3 # System, History(user), Question(user)
        assert messages[0].content.startswith("You are a Staff Software Engineer")
        assert "def hello():" in messages[0].content
        assert messages[1].content == "Hi"
        assert messages[2].content == "How to say hello?"

@pytest.mark.asyncio
async def test_generate_tests(settings, contexts):
    gateway = LLMGateway(settings)
    
    mock_response = MagicMock()
    mock_response.content = "def test_hello():\n    assert True"
    
    with patch.object(gateway._chat_model, 'ainvoke', new_callable=AsyncMock) as mock_ainvoke:
        mock_ainvoke.return_value = mock_response
        
        tests = await gateway.generate_tests("src/main.py", contexts)
        
        assert tests == "def test_hello():\n    assert True"
        mock_ainvoke.assert_called_once()
        messages = mock_ainvoke.call_args[0][0]
        assert messages[1].content == "Target: src/main.py"

@pytest.mark.asyncio
async def test_detect_bugs(settings, contexts):
    gateway = LLMGateway(settings)
    
    mock_finding = MagicMock()
    mock_finding.path = "src/main.py"
    mock_finding.severity = "high"
    mock_finding.message = "Missing auth"
    mock_finding.model_dump.return_value = {"path": "src/main.py", "severity": "high", "message": "Missing auth"}
    
    mock_report = MagicMock()
    mock_report.findings = [mock_finding]
    
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_report)
    
    with patch.object(gateway._chat_model, 'with_structured_output', return_value=mock_structured_llm):
        findings = await gateway.detect_bugs(contexts)
        
        assert len(findings) == 1
        assert findings[0]["severity"] == "high"
        mock_structured_llm.ainvoke.assert_called_once()

def test_create_chat_model_fallback():
    settings = Settings(
        default_llm_provider="openai",
        openai_api_key="sk-openai",
        gemini_api_key="sk-gemini",
    )
    gateway = LLMGateway(settings)
    assert gateway._chat_model is not None
    # LangChain's FallbackRunnable wraps the primary model
    assert hasattr(gateway._chat_model, "fallbacks")
    assert len(gateway._chat_model.fallbacks) == 1
    
    settings_single = Settings(
        default_llm_provider="openai",
        openai_api_key="sk-openai",
        gemini_api_key=None,
    )
    gateway_single = LLMGateway(settings_single)
    assert gateway_single._chat_model is not None
    assert not hasattr(gateway_single._chat_model, "fallbacks")
