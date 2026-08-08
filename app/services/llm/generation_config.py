from dataclasses import dataclass
from typing import Optional, List

@dataclass(slots=True)
class GenerationConfig:
    """
    Lightweight, provider-agnostic configuration for response generation parameters.
    """
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    stop: Optional[List[str]] = None
    seed: Optional[int] = None
