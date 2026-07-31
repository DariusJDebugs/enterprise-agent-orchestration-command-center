from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .connectors import ConnectorRegistry, RiskSignalsConnector, VendorRegistryConnector
from .database import Database
from .embeddings import HashEmbeddingModel
from .evaluation import EvaluationService
from .governance import GovernanceEngine
from .llm import DeterministicProvider, LLMProvider, OpenAICompatibleProvider
from .orchestrator import Orchestrator
from .rag import RAGService
from .repository import Repository
from .security import PromptInjectionDetector
from .tools import ToolRegistry


@dataclass(slots=True)
class Services:
    settings: Settings
    database: Database
    repository: Repository
    embeddings: HashEmbeddingModel
    security: PromptInjectionDetector
    evaluation: EvaluationService
    governance: GovernanceEngine
    rag: RAGService
    connectors: ConnectorRegistry
    tools: ToolRegistry
    llm: LLMProvider
    orchestrator: Orchestrator


def build_services(settings: Settings) -> Services:
    settings.ensure_directories()
    database = Database(settings.database_path)
    repository = Repository(database, settings.audit_hmac_secret)
    embeddings = HashEmbeddingModel(settings.embedding_dimensions)
    security = PromptInjectionDetector()
    evaluation = EvaluationService()
    governance = GovernanceEngine()
    rag = RAGService(
        repository,
        embeddings,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        injection_detector=security,
    )
    connectors = ConnectorRegistry()
    connectors.register(VendorRegistryConnector())
    connectors.register(RiskSignalsConnector())
    tools = ToolRegistry(rag, connectors, repository, governance)
    if settings.llm_mode == "openai-compatible" and settings.llm_base_url and settings.llm_model:
        llm: LLMProvider = OpenAICompatibleProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    else:
        llm = DeterministicProvider()
    orchestrator = Orchestrator(
        repository,
        tools,
        llm,
        evaluation,
        step_delay_ms=settings.agent_step_delay_ms,
        max_retries=settings.max_agent_retries,
        approval_risk_levels=set(settings.approval_risk_levels),
    )
    return Services(
        settings, database, repository, embeddings, security, evaluation,
        governance, rag, connectors, tools, llm, orchestrator,
    )
