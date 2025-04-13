"""
Configuration settings for the GitHub Repository Analyzer.
"""
import os
from pathlib import Path


class Config:
    def __init__(self):
        # Base directories
        self.base_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
        self.data_dir = self.base_dir / ".data"
        
        # Specific directories
        self.repos_dir = self.data_dir / "repos"
        self.index_dir = self.data_dir / "indexes"
        self.models_dir = self.data_dir / "models"
        
        # Model configuration
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"  # For embeddings
        self.llm_model = "TheBloke/Llama-2-7B-Chat-GGUF"  # For text generation
        self.llm_file = "llama-2-7b-chat.Q4_K_M.gguf"  # Specific GGUF file
        
        # FAISS configuration
        self.dimension = 384  # Dimension of embeddings from the model
        
        # Initialize directories
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.repos_dir, exist_ok=True)
        os.makedirs(self.index_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)