"""
Code vectorization module for embedding code chunks.
"""
from typing import List, Dict, Any
import logging
import threading
import time
import os

import numpy as np
import torch

from utils.progress import start_operation, update_progress, complete_operation

logger = logging.getLogger('github_repo_analyzer')

class DownloadProgressCallback:
    """Callback for tracking Hugging Face download progress."""
    def __init__(self, operation_id):
        self.operation_id = operation_id
        self.last_percent = 0
        self.total = 0
        self.downloaded = 0
        
    def __call__(self, progress):
        """Called during downloads to report progress."""
        # For transformers downloads, the format is different than huggingface_hub
        if hasattr(progress, 'total'):
            # This is a file being downloaded
            if progress.total:
                self.total = progress.total
                percent = min(progress.n / progress.total, 1.0)
                self.downloaded = progress.n
                
                # Only update if the percentage has changed significantly
                if int(percent * 100) > self.last_percent:
                    self.last_percent = int(percent * 100)
                    size_mb = self.total / (1024 * 1024)
                    downloaded_mb = self.downloaded / (1024 * 1024)
                    update_progress(
                        self.operation_id, 
                        0.1 + percent * 0.6,  # Scale to leave room for post-download processing
                        f"Downloading model: {downloaded_mb:.1f}MB / {size_mb:.1f}MB"
                    )


class CodeVectorizer:
    def __init__(self, model_name: str):
        """
        Initialize the code vectorizer with the specified model.
        
        Args:
            model_name: Name of the pre-trained model to use
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.device = None
        self.model_loading = False
        self.model_loaded = False
        self.model_loading_lock = threading.Lock()
        self.operation_id = "vectorizer_model_loading"
        logger.info(f"CodeVectorizer initialized with model name: {model_name}")
        
    def _patch_transformers_progress(self):
        """Patch transformers to use our progress callback."""
        try:
            import transformers.utils.hub
            
            # Save original download method
            original_download = transformers.utils.hub.cached_file
            
            # Progress callback
            callback = DownloadProgressCallback(self.operation_id)
            
            # Create a wrapper that adds our callback
            def patched_download(*args, **kwargs):
                # Add our progress bar
                kwargs['progress_callback'] = callback
                return original_download(*args, **kwargs)
            
            # Replace the download method
            transformers.utils.hub.cached_file = patched_download
            
            # Also patch the progress callback to handle no total size
            from tqdm.auto import tqdm
            original_tqdm = tqdm
            
            def patched_tqdm(*args, **kwargs):
                # Call the original constructor
                bar = original_tqdm(*args, **kwargs)
                # Call our callback with the bar
                if kwargs.get('desc', '').startswith('Download'):
                    callback(bar)
                return bar
            
            # Replace tqdm
            transformers.utils.hub.tqdm = patched_tqdm
            
        except Exception as e:
            logger.warning(f"Could not patch transformers progress: {e}")
    
    def _load_model(self):
        """Lazy load the model only when needed"""
        # Return immediately if model is already loaded
        if self.model is not None:
            return
            
        # Use a lock to prevent multiple threads from loading the model simultaneously
        with self.model_loading_lock:
            # Check again after acquiring the lock in case another thread loaded the model
            if self.model is not None:
                return
                
            if self.model_loading:
                # Wait for model to be loaded by another thread
                logger.info("Waiting for vectorizer model to be loaded by another thread...")
                while self.model_loading and not self.model_loaded:
                    time.sleep(0.1)
                return
                
            # Mark that we're loading the model
            self.model_loading = True
            start_operation(self.operation_id, "Loading vectorizer model")
            
            try:
                update_progress(self.operation_id, 0.1, "Initializing model loading...")
                
                # Try to patch transformers progress reporting
                self._patch_transformers_progress()
                
                logger.info(f"Loading tokenizer for model: {self.model_name}")
                update_progress(self.operation_id, 0.15, "Loading tokenizer...")
                
                # Import here to avoid slow startup
                from transformers import AutoTokenizer, AutoModel
                
                # Progress will be reported by our patch
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.model_name, 
                    use_fast=True
                )
                
                logger.info(f"Loading model: {self.model_name}")
                update_progress(self.operation_id, 0.7, "Loading model weights...")
                
                # Load model with progress reporting
                self.model = AutoModel.from_pretrained(
                    self.model_name,
                    from_tf=False
                )
                
                logger.info("Setting up device (CPU/GPU)")
                update_progress(self.operation_id, 0.9, "Setting up compute device...")
                self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                logger.info(f"Using device: {self.device}")
                
                self.model.to(self.device)
                logger.info("Model loaded successfully")
                
                self.model_loaded = True
                complete_operation(self.operation_id, True, "Vectorizer model loaded successfully")
            except Exception as e:
                logger.error(f"Error loading vectorizer model: {e}")
                complete_operation(self.operation_id, False, f"Error loading model: {str(e)}")
                raise
            finally:
                self.model_loading = False
        
    def vectorize_code(self, code_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Convert code chunks to vector embeddings.
        
        Args:
            code_chunks: List of code chunks to vectorize
            
        Returns:
            Dictionary with embeddings and metadata
        """
        logger.info(f"Vectorizing {len(code_chunks)} code chunks")
        
        # Start vectorization operation
        operation_id = "code_vectorization"
        start_operation(operation_id, "Vectorizing code")
        update_progress(operation_id, 0.1, f"Processing {len(code_chunks)} code chunks")
        
        try:
            texts = [chunk['content'] for chunk in code_chunks]
            metadata = code_chunks
            
            # Get embeddings
            logger.info("Computing embeddings")
            update_progress(operation_id, 0.2, "Computing embeddings...")
            embeddings = self._get_embeddings(texts, operation_id)
            logger.info(f"Embeddings computed, shape: {embeddings.shape}")
            
            update_progress(operation_id, 0.95, "Finalizing vectorization...")
            complete_operation(operation_id, True, "Code vectorization complete")
            
            return {
                'embeddings': embeddings,
                'metadata': metadata
            }
        except Exception as e:
            logger.error(f"Error vectorizing code: {e}")
            complete_operation(operation_id, False, f"Error vectorizing code: {str(e)}")
            raise
    
    def encode_query(self, query: str) -> np.ndarray:
        """
        Encode a query string to a vector embedding.
        
        Args:
            query: Query string
            
        Returns:
            Vector embedding of the query
        """
        logger.info(f"Encoding query: {query[:50]}...")
        
        # Start query encoding operation
        operation_id = "query_encoding"
        start_operation(operation_id, "Encoding query")
        
        try:
            update_progress(operation_id, 0.3, "Computing embedding...")
            embedding = self._get_embeddings([query])[0]
            complete_operation(operation_id, True, "Query encoded successfully")
            return embedding
        except Exception as e:
            logger.error(f"Error encoding query: {e}")
            complete_operation(operation_id, False, f"Error encoding query: {str(e)}")
            raise
    
    def _get_embeddings(self, texts: List[str], operation_id: str = None) -> np.ndarray:
        """
        Get embeddings for a list of texts.
        
        Args:
            texts: List of text strings
            operation_id: Optional ID for progress tracking
            
        Returns:
            NumPy array of embeddings
        """
        self._load_model()  # Ensure model is loaded
        
        embeddings = []
        
        # Process in batches to avoid memory issues
        batch_size = 8
        logger.info(f"Processing {len(texts)} texts in batches of {batch_size}")
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(texts) - 1) // batch_size + 1
            
            logger.info(f"Processing batch {batch_num}/{total_batches}")
            
            if operation_id:
                # Update progress based on batch progress
                progress = 0.2 + (0.7 * (batch_num / total_batches))
                update_progress(
                    operation_id, 
                    progress, 
                    f"Processing batch {batch_num}/{total_batches}"
                )
            
            # Tokenize and prepare inputs
            inputs = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            ).to(self.device)
            
            # Get embeddings
            with torch.no_grad():
                outputs = self.model(**inputs)
                
            # Use mean pooling to get a single vector per text
            attention_mask = inputs['attention_mask']
            token_embeddings = outputs.last_hidden_state
            
            # Mean pooling
            input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
            sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
            sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
            batch_embeddings = (sum_embeddings / sum_mask).cpu().numpy()
            
            embeddings.extend(batch_embeddings)
        
        logger.info(f"All embeddings computed, total: {len(embeddings)}")
        return np.array(embeddings)