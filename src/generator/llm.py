"""
LLM (Large Language Model) module for generating responses using either 
Transformers or llama.cpp.
"""
import os
import logging
import threading
import time
import tempfile
import httpx
from typing import List, Dict, Any
from pathlib import Path

from utils.progress import start_operation, update_progress, complete_operation

logger = logging.getLogger('github_repo_analyzer')

class LLMGenerator:
    def __init__(self, model_name: str, use_llama_cpp: bool = True):
        """
        Initialize the LLM generator.
        
        Args:
            model_name: Name or path of the model to use
            use_llama_cpp: Whether to use llama.cpp for inference
        """
        self.model_name = model_name
        self.use_llama_cpp = use_llama_cpp
        self.model = None
        self.tokenizer = None
        self.model_loading = False
        self.model_loaded = False
        self.model_loading_lock = threading.Lock()
        self.operation_id = "llm_model_loading"
        logger.info(f"LLMGenerator initialized with model name: {model_name}, using llama.cpp: {use_llama_cpp}")
    
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
                logger.info("Waiting for LLM model to be loaded by another thread...")
                while self.model_loading and not self.model_loaded:
                    time.sleep(0.1)
                return
                
            # Mark that we're loading the model
            self.model_loading = True
            start_operation(self.operation_id, "Loading LLM model")
            
            try:
                logger.info("Loading LLM model...")
                update_progress(self.operation_id, 0.1, "Initializing model loading...")
                
                if self.use_llama_cpp:
                    logger.info("Initializing llama.cpp model")
                    update_progress(self.operation_id, 0.2, "Setting up llama.cpp...")
                    self.model = self._initialize_llama_cpp()
                    logger.info("llama.cpp model initialized successfully")
                else:
                    logger.info("Initializing Transformers model")
                    update_progress(self.operation_id, 0.2, "Loading tokenizer...")
                    from transformers import AutoTokenizer, AutoModelForCausalLM
                    self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                    
                    update_progress(self.operation_id, 0.4, "Loading model weights...")
                    self.model = AutoModelForCausalLM.from_pretrained(self.model_name)
                    logger.info("Transformers model initialized successfully")
                
                self.model_loaded = True
                complete_operation(self.operation_id, True, "LLM model loaded successfully")
            except Exception as e:
                logger.error(f"Error loading LLM model: {e}")
                complete_operation(self.operation_id, False, f"Error loading model: {str(e)}")
                raise
            finally:
                self.model_loading = False
    
    def _download_file_with_progress(self, url, target_path):
        """Download a file with progress reporting."""
        total_size = 0
        downloaded = 0
        temp_file = None
        
        try:
            # First, make a HEAD request to get the content size
            with httpx.Client() as client:
                head_response = client.head(url)
                if 'content-length' in head_response.headers:
                    total_size = int(head_response.headers['content-length'])
                    logger.info(f"File size: {total_size / 1024 / 1024:.1f} MB")
                    update_progress(self.operation_id, 0.25, f"Starting download: {total_size / 1024 / 1024:.1f} MB")
            
            # Download the file with streaming and progress reporting
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            with httpx.Client() as client:
                with client.stream('GET', url) as response:
                    response.raise_for_status()
                    
                    # If we didn't get the size from HEAD request, try to get it now
                    if total_size == 0 and 'content-length' in response.headers:
                        total_size = int(response.headers['content-length'])
                    
                    # Download the file in chunks, reporting progress
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):  # 1MB chunks
                        temp_file.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0:
                            progress = min(downloaded / total_size, 0.95)  # Cap at 95% to leave room for post-processing
                            update_progress(
                                self.operation_id,
                                0.3 + progress * 0.6,
                                f"Downloading: {downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB"
                            )
                        else:
                            update_progress(
                                self.operation_id,
                                0.5,
                                f"Downloading: {downloaded / 1024 / 1024:.1f}MB (total size unknown)"
                            )
            
            # Close the temp file and move it to the target path
            temp_file.close()
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            os.replace(temp_file.name, target_path)
            return target_path
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            if temp_file:
                temp_file.close()
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
            raise
    
    def _initialize_llama_cpp(self):
        """Initialize the llama.cpp model."""
        logger.info("Looking for available GGUF models...")
        update_progress(self.operation_id, 0.3, "Looking for local GGUF models...")
        
        # Look for available GGUF models
        model_path = os.path.expanduser("~/.cache/huggingface/hub/models--TheBloke--Llama-2-7B-Chat-GGUF/snapshots/")
        
        # Find the latest snapshot directory
        if os.path.exists(model_path):
            logger.info(f"Looking in local cache: {model_path}")
            snapshot_dirs = [d for d in os.listdir(model_path) if os.path.isdir(os.path.join(model_path, d))]
            if snapshot_dirs:
                latest_dir = sorted(snapshot_dirs)[-1]
                model_path = os.path.join(model_path, latest_dir)
                logger.info(f"Found latest snapshot: {latest_dir}")
                update_progress(self.operation_id, 0.4, f"Found local model snapshot: {latest_dir}")
                
                # Find the GGUF file
                gguf_files = [f for f in os.listdir(model_path) if f.endswith('.gguf')]
                if gguf_files:
                    # Prefer smaller quantized models for efficiency
                    preferred_models = [f for f in gguf_files if 'Q4' in f]
                    if preferred_models:
                        model_file = preferred_models[0]
                    else:
                        model_file = gguf_files[0]
                    
                    model_path = os.path.join(model_path, model_file)
                    logger.info(f"Using local model file: {model_file}")
                    update_progress(self.operation_id, 0.5, f"Using local model file: {model_file}")
                    
                    # Initialize the Llama model
                    logger.info("Initializing Llama model from local file")
                    update_progress(self.operation_id, 0.6, "Loading model into memory...")
                    from llama_cpp import Llama
                    llm = Llama(
                        model_path=model_path,
                        n_ctx=4096,  # Context window size
                        n_gpu_layers=-1  # Use GPU if available
                    )
                    update_progress(self.operation_id, 0.9, "Model loaded into memory")
                    return llm
        
        # Fallback to downloading the model if not found locally
        logger.info("No local model found, downloading from Hugging Face Hub")
        update_progress(self.operation_id, 0.2, "No local model found, preparing to download...")
        
        try:
            # Try to use huggingface_hub if available
            from huggingface_hub import hf_hub_download
            
            # First try with modern style
            try:
                logger.info("Using huggingface_hub to download the model")
                model_file = "llama-2-7b-chat.Q4_K_M.gguf"
                
                # Get direct link from Hugging Face API
                repo_id = "TheBloke/Llama-2-7B-Chat-GGUF"
                api_url = f"https://huggingface.co/api/models/{repo_id}/resolve/main/{model_file}"
                
                # Get the cache directory to create the same directory structure as HF
                cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
                model_subdir = os.path.join(
                    cache_dir, 
                    "models--TheBloke--Llama-2-7B-Chat-GGUF",
                    "snapshots",
                    "latest",
                    model_file
                )
                
                # Download with progress
                update_progress(self.operation_id, 0.25, f"Downloading {model_file}...")
                model_path = self._download_file_with_progress(api_url, model_subdir)
                
            except Exception as e:
                logger.error(f"Error with direct download: {e}")
                # Fall back to using hf_hub_download
                logger.info(f"Falling back to hf_hub_download")
                update_progress(self.operation_id, 0.3, "Attempting download via huggingface_hub...")
                
                # Try to get progress, but this depends on HF version
                model_path = hf_hub_download(
                    repo_id="TheBloke/Llama-2-7B-Chat-GGUF",
                    filename="llama-2-7b-chat.Q4_K_M.gguf",
                    local_dir=None,  # Use default cache dir
                    local_dir_use_symlinks=False
                )
            
            logger.info(f"Model downloaded to: {model_path}")
            update_progress(self.operation_id, 0.8, "Download complete, loading model...")
            
            from llama_cpp import Llama
            llm = Llama(
                model_path=model_path,
                n_ctx=4096,
                n_gpu_layers=-1
            )
            
            update_progress(self.operation_id, 0.95, "Model loaded into memory")
            return llm
            
        except Exception as e:
            logger.error(f"Error downloading model: {e}")
            complete_operation(self.operation_id, False, f"Error downloading model: {str(e)}")
            raise
    
    def generate(self, question: str, context: List[Dict[str, Any]]) -> str:
        """
        Generate a response to the given question using the provided context.
        
        Args:
            question: The user's question
            context: List of context items from FAISS search
            
        Returns:
            Generated response
        """
        # Lazy load the model when needed
        self._load_model()
        
        # Prepare the prompt with context
        logger.info("Creating prompt with context")
        prompt = self._create_prompt(question, context)
        
        # Start generation operation
        generation_id = "llm_generation"
        start_operation(generation_id, "Generating answer")
        update_progress(generation_id, 0.1, "Processing question...")
        
        try:
            # Generate response
            if self.use_llama_cpp:
                logger.info("Generating response with llama.cpp")
                update_progress(generation_id, 0.3, "Generating response with LLaMA...")
                response = self._generate_with_llama_cpp(prompt)
            else:
                logger.info("Generating response with Transformers")
                update_progress(generation_id, 0.3, "Generating response with Transformers...")
                response = self._generate_with_transformers(prompt)
                
            logger.info(f"Generated response of length: {len(response)}")
            update_progress(generation_id, 0.9, "Post-processing response...")
            complete_operation(generation_id, True, "Response generated successfully")
            return response
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            complete_operation(generation_id, False, f"Error generating response: {str(e)}")
            raise
    
    def _create_prompt(self, question: str, context: List[Dict[str, Any]]) -> str:
        """Create a prompt with the question and context."""
        context_text = ""
        for i, ctx in enumerate(context):
            context_text += f"Context {i+1}:\n"
            context_text += f"File: {ctx['path']} (Lines {ctx['start_line']}-{ctx['end_line']})\n"
            context_text += f"Code:\n{ctx['content']}\n\n"
        
        prompt = f"""You are an AI assistant that answers questions about GitHub repositories. 
You have been provided with the following code context:

{context_text}

Based only on the context above, please answer the following question:
{question}

If the context doesn't contain enough information to answer the question, 
please say so rather than making up information.

Answer:
"""
        return prompt
    
    def _generate_with_llama_cpp(self, prompt: str) -> str:
        """Generate a response using llama.cpp."""
        response = self.model(
            prompt,
            max_tokens=2048,
            temperature=0.1,
            top_p=0.9,
            top_k=40,
            stop=["</s>", "User:", "Question:"],
            echo=False
        )
        
        return response['choices'][0]['text'].strip()
    
    def _generate_with_transformers(self, prompt: str) -> str:
        """Generate a response using Transformers."""
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.model.generate(
            inputs["input_ids"],
            max_length=len(inputs["input_ids"][0]) + 2048,
            temperature=0.1,
            top_p=0.9,
            top_k=40,
            num_return_sequences=1,
            pad_token_id=self.tokenizer.eos_token_id
        )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        response = response[len(prompt):]  # Remove the prompt from the response
        
        return response.strip()