"""
RAG Knowledge Base Module

Vector-indexed knowledge base for IT documentation, runbooks, and historical
tickets. Provides context-aware retrieval with reranking for agent decision making.
"""

from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import hashlib
import structlog
from pydantic import BaseModel, Field

import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter


logger = structlog.get_logger(__name__)


class Document(BaseModel):
    """Represents a document in the knowledge base."""
    id: str
    content: str
    doc_type: str  # runbook, faq, historical_ticket, policy
    category: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """Result from knowledge retrieval."""
    document_id: str
    content: str
    relevance_score: float
    metadata: Dict[str, Any]


class KnowledgeBase:
    """
    ChromaDB-backed knowledge base for IT operations.
    
    Features:
    - Multi-collection support (runbooks, tickets, policies)
    - Automatic chunking for long documents
    - Metadata filtering
    - Incremental updates
    
    Example:
        kb = KnowledgeBase()
        kb.index_documents("./runbooks/", doc_type="runbook")
        results = await kb.search("VPN connection issues", top_k=5)
    """
    
    COLLECTION_NAMES = {
        "runbook": "it_runbooks",
        "faq": "it_faqs",
        "historical_ticket": "historical_tickets",
        "policy": "it_policies"
    }
    
    def __init__(
        self,
        persist_directory: str = "./data/chroma",
        embedding_model: str = "text-embedding-3-small"
    ):
        self.persist_directory = persist_directory
        
        # Initialize ChromaDB client
        self.client = chromadb.Client(Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        
        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Initialize collections
        self._collections = {}
        self._initialize_collections()
        
        logger.info("knowledge_base_initialized", persist_dir=persist_directory)
    
    def _initialize_collections(self):
        """Initialize or get existing collections."""
        for doc_type, collection_name in self.COLLECTION_NAMES.items():
            self._collections[doc_type] = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
    
    def _generate_doc_id(self, content: str, source: str) -> str:
        """Generate unique document ID."""
        hash_input = f"{source}:{content[:500]}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    async def index_documents(
        self,
        source_path: str,
        doc_type: str,
        category: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Index documents from a directory.
        
        Args:
            source_path: Path to directory containing documents
            doc_type: Type of documents (runbook, faq, etc.)
            category: Optional category for filtering
            metadata: Additional metadata to attach
            
        Returns:
            Number of documents indexed
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source path not found: {source_path}")
        
        collection = self._collections.get(doc_type)
        if not collection:
            raise ValueError(f"Unknown document type: {doc_type}")
        
        indexed_count = 0
        
        for file_path in source.glob("**/*"):
            if file_path.is_file() and file_path.suffix in [".md", ".txt", ".html"]:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    
                    # Chunk the document
                    chunks = self.text_splitter.split_text(content)
                    
                    for i, chunk in enumerate(chunks):
                        doc_id = self._generate_doc_id(chunk, str(file_path))
                        
                        # Generate embedding
                        embedding = await self.embeddings.aembed_query(chunk)
                        
                        # Prepare metadata
                        doc_metadata = {
                            "source": str(file_path),
                            "title": file_path.stem,
                            "doc_type": doc_type,
                            "category": category or "general",
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                            "indexed_at": datetime.utcnow().isoformat(),
                            **(metadata or {})
                        }
                        
                        # Add to collection
                        collection.add(
                            ids=[doc_id],
                            embeddings=[embedding],
                            documents=[chunk],
                            metadatas=[doc_metadata]
                        )
                        
                        indexed_count += 1
                    
                    logger.debug("document_indexed", path=str(file_path), chunks=len(chunks))
                    
                except Exception as e:
                    logger.error("indexing_failed", path=str(file_path), error=str(e))
        
        # Persist changes
        self.client.persist()
        
        logger.info("indexing_completed", doc_type=doc_type, count=indexed_count)
        return indexed_count
    
    async def index_tickets(
        self,
        tickets: List[Dict[str, Any]],
        extract_solutions: bool = True
    ) -> int:
        """
        Index historical tickets for pattern learning.
        
        Args:
            tickets: List of ticket dictionaries
            extract_solutions: Whether to extract solution patterns
            
        Returns:
            Number of tickets indexed
        """
        collection = self._collections["historical_ticket"]
        indexed_count = 0
        
        for ticket in tickets:
            if ticket.get("status") != "resolved":
                continue
            
            # Build indexable content
            content_parts = [
                f"Title: {ticket.get('title', '')}",
                f"Description: {ticket.get('description', '')}",
            ]
            
            if extract_solutions and ticket.get("resolution_notes"):
                content_parts.append(f"Resolution: {ticket['resolution_notes']}")
            
            content = "\n".join(content_parts)
            
            doc_id = self._generate_doc_id(content, ticket.get("ticket_id", ""))
            
            try:
                embedding = await self.embeddings.aembed_query(content)
                
                metadata = {
                    "ticket_id": ticket.get("ticket_id"),
                    "category": ticket.get("category", "other"),
                    "priority": ticket.get("priority", "medium"),
                    "resolution_time_minutes": ticket.get("resolution_time_minutes"),
                    "resolution_summary": ticket.get("resolution_notes", "")[:200],
                    "status": "resolved",
                    "indexed_at": datetime.utcnow().isoformat()
                }
                
                collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[metadata]
                )
                
                indexed_count += 1
                
            except Exception as e:
                logger.error("ticket_indexing_failed", ticket_id=ticket.get("ticket_id"), error=str(e))
        
        self.client.persist()
        
        logger.info("tickets_indexed", count=indexed_count)
        return indexed_count
    
    async def search(
        self,
        query: str,
        doc_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[RetrievalResult]:
        """
        Search the knowledge base.
        
        Args:
            query: Search query
            doc_type: Limit to specific document type
            filters: Metadata filters
            top_k: Number of results to return
            
        Returns:
            List of retrieval results sorted by relevance
        """
        query_embedding = await self.embeddings.aembed_query(query)
        
        results = []
        
        # Determine which collections to search
        collections_to_search = (
            [self._collections[doc_type]] if doc_type
            else list(self._collections.values())
        )
        
        # Build where filter
        where_filter = None
        if filters:
            where_filter = {
                "$and": [{k: v} for k, v in filters.items()]
            } if len(filters) > 1 else filters
        
        for collection in collections_to_search:
            try:
                search_results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    where=where_filter
                )
                
                if search_results and search_results["ids"]:
                    for i, doc_id in enumerate(search_results["ids"][0]):
                        results.append(RetrievalResult(
                            document_id=doc_id,
                            content=search_results["documents"][0][i],
                            relevance_score=1 - search_results["distances"][0][i],  # Convert distance to similarity
                            metadata=search_results["metadatas"][0][i]
                        ))
            except Exception as e:
                logger.error("search_failed", collection=collection.name, error=str(e))
        
        # Sort by relevance and take top_k
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]
    
    async def delete_document(self, doc_id: str, doc_type: str) -> bool:
        """Delete a document from the knowledge base."""
        collection = self._collections.get(doc_type)
        if not collection:
            return False
        
        try:
            collection.delete(ids=[doc_id])
            self.client.persist()
            return True
        except Exception as e:
            logger.error("delete_failed", doc_id=doc_id, error=str(e))
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        stats = {}
        for doc_type, collection in self._collections.items():
            stats[doc_type] = {
                "count": collection.count(),
                "collection_name": collection.name
            }
        return stats


class ContextRetriever:
    """
    High-level retriever with reranking and context assembly.
    
    Provides intelligent context retrieval for agent decision making,
    with support for:
    - Multi-collection search
    - Result reranking
    - Context window management
    - Relevance filtering
    
    Example:
        retriever = ContextRetriever(min_relevance=0.7)
        context = await retriever.retrieve(
            query="VPN timeout errors",
            filters={"category": "network"}
        )
    """
    
    def __init__(
        self,
        knowledge_base: Optional[KnowledgeBase] = None,
        top_k: int = 10,
        min_relevance_score: float = 0.5,
        max_context_tokens: int = 4000,
        rerank: bool = True
    ):
        self.kb = knowledge_base or KnowledgeBase()
        self.top_k = top_k
        self.min_relevance_score = min_relevance_score
        self.max_context_tokens = max_context_tokens
        self.rerank = rerank
    
    async def retrieve(
        self,
        query: str,
        doc_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a query.
        
        Args:
            query: The search query
            doc_type: Optional document type filter
            filters: Additional metadata filters
            top_k: Override default top_k
            
        Returns:
            List of relevant documents with metadata
        """
        k = top_k or self.top_k
        
        # Get initial results
        results = await self.kb.search(
            query=query,
            doc_type=doc_type,
            filters=filters,
            top_k=k * 2  # Retrieve more for reranking
        )
        
        # Filter by minimum relevance
        results = [r for r in results if r.relevance_score >= self.min_relevance_score]
        
        # Rerank if enabled
        if self.rerank and len(results) > 1:
            results = await self._rerank_results(query, results)
        
        # Trim to context window
        results = self._trim_to_context_window(results)
        
        # Convert to dict format for agents
        return [
            {
                "content": r.content,
                "metadata": r.metadata,
                "relevance_score": r.relevance_score
            }
            for r in results[:k]
        ]
    
    async def _rerank_results(
        self,
        query: str,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Rerank results using cross-encoder or LLM."""
        # In production, use a cross-encoder model or LLM-based reranking
        # For now, apply simple heuristics
        
        query_terms = set(query.lower().split())
        
        for result in results:
            content_terms = set(result.content.lower().split())
            term_overlap = len(query_terms & content_terms) / len(query_terms)
            
            # Boost based on term overlap
            result.relevance_score = result.relevance_score * 0.7 + term_overlap * 0.3
        
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results
    
    def _trim_to_context_window(
        self,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Trim results to fit within context window."""
        trimmed = []
        total_tokens = 0
        
        for result in results:
            # Rough token estimate (4 chars per token)
            doc_tokens = len(result.content) // 4
            
            if total_tokens + doc_tokens <= self.max_context_tokens:
                trimmed.append(result)
                total_tokens += doc_tokens
            else:
                break
        
        return trimmed
    
    async def retrieve_with_history(
        self,
        query: str,
        conversation_history: List[Dict[str, str]],
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Retrieve context considering conversation history.
        
        Extracts key terms from recent conversation to improve retrieval.
        """
        # Build enhanced query from history
        history_context = " ".join([
            msg.get("content", "")
            for msg in conversation_history[-3:]
        ])
        
        enhanced_query = f"{query} {history_context}"
        
        return await self.retrieve(query=enhanced_query, **kwargs)
