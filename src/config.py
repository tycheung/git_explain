"""
Configuration settings for the GitHub Repository Analyzer.
"""
import os
from pathlib import Path

class Config:
    def __init__(self):
        # GPU configuration
        self.gpu_available = os.environ.get("GITHUB_ANALYZER_GPU_AVAILABLE", "0") == "1"
        self.gpu_info = None
        
        # Base directories
        # Check for environment variable first (set by app_launcher.py)
        env_data_dir = os.environ.get("GITHUB_ANALYZER_DATA_DIR")
        if env_data_dir:
            self.data_dir = Path(env_data_dir)
            self.repos_dir = self.data_dir / "repos"
            self.index_dir = self.data_dir / "indexes"
            self.models_dir = self.data_dir / "models"
        else:
            # Fall back to relative paths if environment variable not set
            self.base_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent
            self.data_dir = self.base_dir / ".data"
            self.repos_dir = self.data_dir / "repos"
            self.index_dir = self.data_dir / "indexes"
            self.models_dir = self.data_dir / "models"
        
        # Model configuration
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"  # For embeddings
        self.llm_model = "TheBloke/Llama-2-7B-Chat-GGUF"  # For text generation
        self.llm_file = "llama-2-7b-chat.Q4_K_M.gguf"  # Specific GGUF file
        
        # FAISS configuration
        self.dimension = 384  # Dimension of embeddings from the model
        
        # Port configuration
        self.PORT = 5000
        
        # Initialize directories
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.repos_dir, exist_ok=True)
        os.makedirs(self.index_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Log configuration at init
        print(f"Data directory: {self.data_dir}")
        print(f"GPU available: {self.gpu_available}")