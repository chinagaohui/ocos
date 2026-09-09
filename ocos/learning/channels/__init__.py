"""Learning channels — 多渠道学习获取层.

三个渠道:
    - web_researcher: 网络搜索调研（SearchOps）
    - llm_tutor:       LLM 知识库问答（TextGenerator）
    - experience_extractor: 任务经验提取适配层（FailureDiagnoser）

每个渠道的 output 都是 IngestArtifact → 喂给 UnifiedIngestor.
"""

from .web_researcher import WebResearcher, ResearchArtifact
from .llm_tutor import LLMTutor, QAResult
from .experience_extractor import ExperienceExtractor, ExperienceArtifact

__all__ = [
    "WebResearcher", "ResearchArtifact",
    "LLMTutor", "QAResult",
    "ExperienceExtractor", "ExperienceArtifact",
]
