"""
RAG Retriever Module

Re-export from knowledge_base for backward compatibility.
"""

from src.rag.knowledge_base import ContextRetriever, KnowledgeBase, RetrievalResult

__all__ = ["ContextRetriever", "KnowledgeBase", "RetrievalResult"]
