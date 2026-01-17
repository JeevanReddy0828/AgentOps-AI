"""
RAG Knowledge Base Module

Vector-indexed knowledge base for IT documentation, runbooks, and historical
tickets. Provides context-aware retrieval with reranking for agent decision making.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path
import hashlib
import structlog
from pydantic import BaseModel, Field

# Updated imports for newer langchain versions
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
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
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        self.persist_directory = persist_directory
        self._collections = {}
        
        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Lazy initialization of ChromaDB and embeddings
        self._client = None
        self._embeddings = None
        
        logger.info("knowledge_base_initialized", persist_dir=persist_directory)
    
    def _get_client(self):
        """Lazy load ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                from chromadb.config import Settings
                
                self._client = chromadb.Client(Settings(
                    persist_directory=self.persist_directory,
                    anonymized_telemetry=False
                ))
                self._initialize_collections()
            except ImportError:
                logger.warning("chromadb_not_installed")
                self._client = None
            except Exception as e:
                logger.warning("chromadb_init_failed", error=str(e))
                self._client = None
        return self._client
    
    def _get_embeddings(self):
        """Lazy load embeddings model."""
        if self._embeddings is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embeddings = SentenceTransformer('all-MiniLM-L6-v2')
            except ImportError:
                logger.warning("sentence_transformers_not_installed")
                self._embeddings = None
            except Exception as e:
                logger.warning("embeddings_init_failed", error=str(e))
                self._embeddings = None
        return self._embeddings
    
    def _initialize_collections(self):
        """Initialize or get existing collections."""
        if self._client is None:
            return
            
        for doc_type, collection_name in self.COLLECTION_NAMES.items():
            try:
                self._collections[doc_type] = self._client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.warning("collection_init_failed", collection=collection_name, error=str(e))
    
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
        """Index documents from a directory."""
        source = Path(source_path)
        if not source.exists():
            logger.warning("source_path_not_found", path=source_path)
            return 0
        
        client = self._get_client()
        embeddings = self._get_embeddings()
        
        if client is None or embeddings is None:
            logger.warning("indexing_skipped_no_backend")
            return 0
        
        collection = self._collections.get(doc_type)
        if not collection:
            logger.warning("unknown_doc_type", doc_type=doc_type)
            return 0
        
        indexed_count = 0
        
        for file_path in source.glob("**/*"):
            if file_path.is_file() and file_path.suffix in [".md", ".txt", ".html"]:
                try:
                    content = file_path.read_text(encoding="utf-8")
                    chunks = self.text_splitter.split_text(content)
                    
                    for i, chunk in enumerate(chunks):
                        doc_id = self._generate_doc_id(chunk, str(file_path))
                        embedding = embeddings.encode(chunk).tolist()
                        
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
        
        logger.info("indexing_completed", doc_type=doc_type, count=indexed_count)
        return indexed_count
    
    async def index_tickets(
        self,
        tickets: List[Dict[str, Any]],
        extract_solutions: bool = True
    ) -> int:
        """Index historical tickets for pattern learning."""
        client = self._get_client()
        embeddings = self._get_embeddings()
        
        if client is None or embeddings is None:
            logger.warning("ticket_indexing_skipped_no_backend")
            return 0
        
        collection = self._collections.get("historical_ticket")
        if not collection:
            return 0
        
        indexed_count = 0
        
        for ticket in tickets:
            if ticket.get("status") != "resolved":
                continue
            
            content_parts = [
                f"Title: {ticket.get('title', '')}",
                f"Description: {ticket.get('description', '')}",
            ]
            
            if extract_solutions and ticket.get("resolution_notes"):
                content_parts.append(f"Resolution: {ticket['resolution_notes']}")
            
            content = "\n".join(content_parts)
            doc_id = self._generate_doc_id(content, ticket.get("ticket_id", ""))
            
            try:
                embedding = embeddings.encode(content).tolist()
                
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
        
        logger.info("tickets_indexed", count=indexed_count)
        return indexed_count
    
    async def search(
        self,
        query: str,
        doc_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[RetrievalResult]:
        """Search the knowledge base."""
        client = self._get_client()
        embeddings = self._get_embeddings()
        
        if client is None or embeddings is None:
            logger.debug("search_skipped_no_backend")
            return []
        
        query_embedding = embeddings.encode(query).tolist()
        results = []
        
        collections_to_search = (
            [self._collections[doc_type]] if doc_type and doc_type in self._collections
            else list(self._collections.values())
        )
        
        where_filter = None
        if filters:
            where_filter = {
                "$and": [{k: v} for k, v in filters.items()]
            } if len(filters) > 1 else filters
        
        for collection in collections_to_search:
            if collection is None:
                continue
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
                            relevance_score=1 - search_results["distances"][0][i],
                            metadata=search_results["metadatas"][0][i]
                        ))
            except Exception as e:
                logger.error("search_failed", error=str(e))
        
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]
    
    async def delete_document(self, doc_id: str, doc_type: str) -> bool:
        """Delete a document from the knowledge base."""
        collection = self._collections.get(doc_type)
        if not collection:
            return False
        
        try:
            collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            logger.error("delete_failed", doc_id=doc_id, error=str(e))
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        stats = {}
        for doc_type, collection in self._collections.items():
            if collection is not None:
                try:
                    stats[doc_type] = {
                        "count": collection.count(),
                        "collection_name": collection.name
                    }
                except:
                    stats[doc_type] = {"count": 0, "collection_name": "N/A"}
        return stats


class ContextRetriever:
    """
    High-level retriever with reranking and context assembly.
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
        """Retrieve relevant context for a query."""
        k = top_k or self.top_k
        
        results = await self.kb.search(
            query=query,
            doc_type=doc_type,
            filters=filters,
            top_k=k * 2
        )
        
        results = [r for r in results if r.relevance_score >= self.min_relevance_score]
        
        if self.rerank and len(results) > 1:
            results = await self._rerank_results(query, results)
        
        results = self._trim_to_context_window(results)
        
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
        """Rerank results using term overlap heuristic."""
        query_terms = set(query.lower().split())
        
        for result in results:
            content_terms = set(result.content.lower().split())
            term_overlap = len(query_terms & content_terms) / len(query_terms) if query_terms else 0
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
        """Retrieve context considering conversation history."""
        history_context = " ".join([
            msg.get("content", "")
            for msg in conversation_history[-3:]
        ])
        
        enhanced_query = f"{query} {history_context}"
        
        return await self.retrieve(query=enhanced_query, **kwargs)