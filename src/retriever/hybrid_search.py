"""
Hybrid search module for combining semantic search with keyword search.
"""
import os
import re
import json
import math
import logging
from typing import List, Dict, Any, Tuple, Set
import numpy as np
from pathlib import Path

logger = logging.getLogger('github_repo_analyzer')

class HybridSearch:
    def __init__(self, faiss_index, vectorizer):
        """
        Initialize the hybrid search.
        
        Args:
            faiss_index: FAISS index for semantic search
            vectorizer: Vectorizer for encoding queries
        """
        self.faiss_index = faiss_index
        self.vectorizer = vectorizer
        self.keyword_index = None
        self.tfidf_index = None
    
    def build_keyword_index(self):
        """Build a keyword index for faster keyword search."""
        logger.info("Building keyword index")
        
        if not self.faiss_index or not self.faiss_index.metadata:
            logger.warning("FAISS index or metadata not available")
            return
        
        # Build an inverted index for keywords
        keyword_index = {}
        
        for i, doc in enumerate(self.faiss_index.metadata):
            content = doc.get('content', '')
            path = doc.get('path', '')
            
            # Tokenize the content
            tokens = self._tokenize(content)
            
            # Add each token to the inverted index
            for token in tokens:
                if token not in keyword_index:
                    keyword_index[token] = []
                keyword_index[token].append(i)
        
        self.keyword_index = keyword_index
        logger.info(f"Keyword index built with {len(keyword_index)} unique tokens")
        
        # Build TF-IDF index
        self._build_tfidf_index()
    
    def _build_tfidf_index(self):
        """Build a TF-IDF index for improved keyword search."""
        if not self.faiss_index or not self.faiss_index.metadata:
            return
        
        logger.info("Building TF-IDF index")
        
        # Calculate document frequencies
        doc_freqs = {}
        total_docs = len(self.faiss_index.metadata)
        
        for token, doc_indices in self.keyword_index.items():
            doc_freqs[token] = len(set(doc_indices))
        
        # Calculate TF-IDF for each document
        tfidf_index = {}
        
        for i, doc in enumerate(self.faiss_index.metadata):
            content = doc.get('content', '')
            
            # Tokenize the content
            tokens = self._tokenize(content)
            
            # Count term frequencies
            term_freqs = {}
            for token in tokens:
                if token not in term_freqs:
                    term_freqs[token] = 0
                term_freqs[token] += 1
            
            # Calculate TF-IDF
            tfidf = {}
            for token, freq in term_freqs.items():
                if token in doc_freqs and doc_freqs[token] > 0:
                    tf = freq / len(tokens)
                    idf = math.log(total_docs / doc_freqs[token])
                    tfidf[token] = tf * idf
            
            tfidf_index[i] = tfidf
        
        self.tfidf_index = tfidf_index
        logger.info("TF-IDF index built successfully")
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into meaningful keywords.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        # Convert to lowercase
        text = text.lower()
        
        # Replace non-alphanumeric with spaces
        text = re.sub(r'[^a-z0-9_]', ' ', text)
        
        # Split by whitespace
        tokens = text.split()
        
        # Remove short tokens
        tokens = [token for token in tokens if len(token) >= 2]
        
        # Remove common programming keywords
        stop_words = {
            'if', 'else', 'for', 'while', 'return', 'def', 'class', 'import',
            'from', 'self', 'this', 'function', 'var', 'let', 'const', 'int',
            'float', 'string', 'bool', 'true', 'false', 'none', 'null', 'and',
            'or', 'not', 'in', 'is', 'as', 'with', 'try', 'except', 'finally'
        }
        tokens = [token for token in tokens if token not in stop_words]
        
        return tokens
    
    def search(self, query: str, k: int = 5, semantic_weight: float = 0.7) -> List[Dict[str, Any]]:
        """
        Perform a hybrid search combining semantic and keyword search.
        
        Args:
            query: Search query
            k: Number of results to return
            semantic_weight: Weight for semantic search (0.0 to 1.0)
            
        Returns:
            List of search results with scores
        """
        logger.info(f"Performing hybrid search for query: {query}")
        
        # Ensure the keyword index is built
        if not self.keyword_index:
            self.build_keyword_index()
        
        # Perform semantic search
        semantic_results = self._semantic_search(query, k=k*2)
        
        # Perform keyword search
        keyword_results = self._keyword_search(query, k=k*2)
        
        # Combine results
        combined_results = self._combine_results(
            semantic_results, 
            keyword_results, 
            k=k, 
            semantic_weight=semantic_weight
        )
        
        return combined_results
    
    def _semantic_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform semantic search using FAISS.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of search results with scores
        """
        try:
            # Encode query
            query_vector = self.vectorizer.encode_query(query)
            
            # Search FAISS index
            results = self.faiss_index.search(query_vector, k=k)
            
            # Normalize scores to [0, 1]
            max_score = max(result['score'] for result in results) if results else 1.0
            for result in results:
                result['semantic_score'] = result['score'] / max_score
            
            return results
        
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    def _keyword_search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Perform keyword search using the keyword index.
        
        Args:
            query: Search query
            k: Number of results to return
            
        Returns:
            List of search results with scores
        """
        if not self.keyword_index or not self.tfidf_index:
            logger.warning("Keyword index not available")
            return []
        
        try:
            # Tokenize query
            query_tokens = self._tokenize(query)
            
            # Find documents containing query tokens
            doc_scores = {}
            
            for token in query_tokens:
                if token in self.keyword_index:
                    for doc_idx in self.keyword_index[token]:
                        if doc_idx not in doc_scores:
                            doc_scores[doc_idx] = 0.0
                        
                        # Use TF-IDF score if available
                        if doc_idx in self.tfidf_index and token in self.tfidf_index[doc_idx]:
                            doc_scores[doc_idx] += self.tfidf_index[doc_idx][token]
                        else:
                            doc_scores[doc_idx] += 1.0
            
            # Sort documents by score
            sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
            
            # Get top k results
            top_docs = sorted_docs[:k]
            
            # Convert to list of results
            results = []
            
            # Normalize scores to [0, 1]
            max_score = max(score for _, score in top_docs) if top_docs else 1.0
            
            for doc_idx, score in top_docs:
                if doc_idx < len(self.faiss_index.metadata):
                    result = self.faiss_index.metadata[doc_idx].copy()
                    result['keyword_score'] = score / max_score
                    results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            return []
    
    def _combine_results(
        self, 
        semantic_results: List[Dict[str, Any]], 
        keyword_results: List[Dict[str, Any]], 
        k: int = 5, 
        semantic_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Combine semantic and keyword search results.
        
        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            k: Number of results to return
            semantic_weight: Weight for semantic search (0.0 to 1.0)
            
        Returns:
            Combined search results
        """
        # Create a mapping of path to result
        combined_map = {}
        
        # Add semantic results
        for result in semantic_results:
            path = result['path']
            if path not in combined_map:
                combined_map[path] = result.copy()
                combined_map[path]['combined_score'] = result['semantic_score'] * semantic_weight
            else:
                combined_map[path]['semantic_score'] = result['semantic_score']
                combined_map[path]['combined_score'] += result['semantic_score'] * semantic_weight
        
        # Add keyword results
        for result in keyword_results:
            path = result['path']
            if path not in combined_map:
                combined_map[path] = result.copy()
                combined_map[path]['keyword_score'] = result.get('keyword_score', 0.0)
                combined_map[path]['combined_score'] = result.get('keyword_score', 0.0) * (1 - semantic_weight)
            else:
                combined_map[path]['keyword_score'] = result.get('keyword_score', 0.0)
                combined_map[path]['combined_score'] += result.get('keyword_score', 0.0) * (1 - semantic_weight)
        
        # Convert to list and sort by combined score
        combined_results = list(combined_map.values())
        combined_results.sort(key=lambda x: x.get('combined_score', 0.0), reverse=True)
        
        # Set the score field to be the combined score
        for result in combined_results:
            result['score'] = result.get('combined_score', 0.0)
        
        return combined_results[:k]