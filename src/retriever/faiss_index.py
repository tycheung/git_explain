"""
FAISS index module for vector similarity search.
"""
import os
import pickle
from typing import List, Dict, Any, Tuple

import numpy as np
import faiss


class FAISSIndex:
    def __init__(self, index_dir: str, dimension: int = 384):
        """
        Initialize the FAISS index.
        
        Args:
            index_dir: Directory to store the index
            dimension: Dimension of the embeddings
        """
        self.index_dir = index_dir
        self.dimension = dimension
        self.index = None
        self.metadata = None
        
    def create_index(self, vectors: Dict[str, Any], metadata: List[Dict[str, Any]]) -> None:
        """
        Create a new FAISS index from the given vectors.
        
        Args:
            vectors: Dictionary containing embeddings and metadata
            metadata: List of metadata for the indexed items
        """
        embeddings = vectors['embeddings']
        self.metadata = metadata
        
        # Create a new index
        self.index = faiss.IndexFlatL2(self.dimension)
        
        # Add vectors to the index
        self.index.add(np.array(embeddings).astype('float32'))
        
        # Save the index and metadata
        self._save_index()
        
    def load_index(self) -> bool:
        """
        Load a saved FAISS index.
        
        Returns:
            True if the index was loaded successfully, False otherwise
        """
        index_path = os.path.join(self.index_dir, 'faiss_index.bin')
        metadata_path = os.path.join(self.index_dir, 'metadata.pkl')
        
        if not os.path.exists(index_path) or not os.path.exists(metadata_path):
            return False
        
        try:
            self.index = faiss.read_index(index_path)
            
            with open(metadata_path, 'rb') as f:
                self.metadata = pickle.load(f)
                
            return True
        except Exception as e:
            print(f"Error loading index: {e}")
            return False
            
    def search(self, query_vector: np.ndarray, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in the index.
        
        Args:
            query_vector: Query vector
            k: Number of results to return
            
        Returns:
            List of the most similar items with their metadata
        """
        if self.index is None:
            if not self.load_index():
                raise ValueError("No index available. Please create or load an index first.")
        
        # Ensure the query vector has the right shape and type
        query_vector = np.array(query_vector).reshape(1, -1).astype('float32')
        
        # Search the index
        distances, indices = self.index.search(query_vector, k)
        
        # Prepare results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1 and idx < len(self.metadata):  # -1 means no result
                result = self.metadata[idx].copy()
                result['score'] = float(1.0 / (1.0 + distances[0][i]))  # Convert distance to a score
                results.append(result)
        
        return results
    
    def _save_index(self) -> None:
        """Save the index and metadata to disk."""
        os.makedirs(self.index_dir, exist_ok=True)
        
        index_path = os.path.join(self.index_dir, 'faiss_index.bin')
        metadata_path = os.path.join(self.index_dir, 'metadata.pkl')
        
        # Save the FAISS index
        faiss.write_index(self.index, index_path)
        
        # Save the metadata
        with open(metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)