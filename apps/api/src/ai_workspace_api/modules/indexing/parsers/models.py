from dataclasses import dataclass


@dataclass(frozen=True)
class CodeSymbol:
    name: str
    symbol_type: str  # "class", "method", "function", "interface", "type_alias", "import"
    parent_scope: str | None
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ParsedChunk:
    start_line: int
    end_line: int
    content: str
    symbol: str | None = None
    symbol_type: str | None = None
    parent_scope: str | None = None
