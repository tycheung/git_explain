#!/usr/bin/env python3
"""
GPU setup and detection utility for GitHub Repository Analyzer.
This script helps detect and configure GPU support at runtime.
"""

import os
import sys
import logging
import subprocess
import platform
import importlib
import importlib.util

logger = logging.getLogger(__name__)

def is_gpu_available():
    """
    Check if a CUDA-compatible GPU is available.
    Returns True if a GPU is available, False otherwise.
    """
    # First check environment variable (set by app_launcher.py)
    if os.environ.get("GITHUB_ANALYZER_GPU_AVAILABLE") == "1":
        return True
    
    # Then try to detect with PyTorch
    try:
        import torch
        if torch.cuda.is_available():
            logger.info(f"GPU available via PyTorch: {torch.cuda.get_device_name(0)}")
            return True
    except ImportError:
        logger.warning("PyTorch not available for GPU check")
    except Exception as e:
        logger.warning(f"Error checking PyTorch GPU: {e}")
    
    # Try llama-cpp-python CUDA support as a fallback
    try:
        import llama_cpp
        has_cublas = getattr(llama_cpp, "has_cublas", False)
        if has_cublas:
            logger.info("llama-cpp-python has CUDA support")
            return True
    except ImportError:
        logger.warning("llama-cpp-python not available for GPU check")
    except Exception as e:
        logger.warning(f"Error checking llama-cpp GPU support: {e}")
    
    return False

def import_faiss():
    """
    Dynamically import the appropriate FAISS module based on GPU availability.
    Returns the faiss module.
    """
    if is_gpu_available():
        # Try to import GPU version first
        try:
            logger.info("Attempting to import FAISS GPU")
            import faiss.swigfaiss_gpu as faiss_module
            logger.info("Successfully imported FAISS GPU")
            return faiss_module
        except ImportError:
            logger.warning("Failed to import FAISS GPU, falling back to CPU")
            import faiss.swigfaiss as faiss_module
            return faiss_module
        except Exception as e:
            logger.warning(f"Error importing FAISS GPU: {e}")
            logger.warning("Falling back to CPU version")
            import faiss.swigfaiss as faiss_module
            return faiss_module
    else:
        # CPU version
        try:
            logger.info("Importing FAISS CPU")
            import faiss.swigfaiss as faiss_module
            return faiss_module
        except ImportError as e:
            logger.error(f"Failed to import FAISS CPU: {e}")
            raise

def setup_gpu():
    """
    Set up GPU support for the application.
    This function installs GPU-specific dependencies if a GPU is available.
    """
    if not is_gpu_available():
        logger.info("No GPU detected, skipping GPU setup")
        return False
    
    logger.info("GPU detected, setting up GPU support")
    
    try:
        # Install PyTorch with CUDA
        logger.info("Installing PyTorch with CUDA support...")
        if platform.system() == "Windows":
            torch_cmd = "pip install torch --extra-index-url https://download.pytorch.org/whl/cu118/"
        else:
            torch_cmd = "pip install torch --extra-index-url https://download.pytorch.org/whl/cu118/"
            
        subprocess.run(torch_cmd.split(), check=True)
        
        # Install FAISS GPU
        logger.info("Installing FAISS GPU...")
        subprocess.run(["pip", "install", "faiss-gpu", "--force-reinstall"], check=True)
        
        # Install llama-cpp-python with CUDA
        logger.info("Installing llama-cpp-python with CUDA...")
        env = os.environ.copy()
        env["CMAKE_ARGS"] = "-DLLAMA_CUBLAS=on"
        
        if platform.system() == "Windows":
            # Windows needs a different approach
            os.environ["CMAKE_ARGS"] = "-DLLAMA_CUBLAS=on"
            subprocess.run(["pip", "install", "--force-reinstall", "llama-cpp-python"], check=True)
        else:
            subprocess.run(["pip", "install", "--force-reinstall", "llama-cpp-python"], env=env, check=True)
        
        logger.info("GPU dependencies installed successfully")
        return True
    except Exception as e:
        logger.error(f"Error installing GPU dependencies: {e}")
        return False

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 50)
    print("GPU Setup Utility for GitHub Repository Analyzer")
    print("=" * 50)
    
    if is_gpu_available():
        print("✓ GPU detected!")
        if setup_gpu():
            print("✓ GPU support successfully configured")
        else:
            print("✗ Failed to set up GPU support")
    else:
        print("✗ No GPU detected, will use CPU only")
    
    print("\nYou can run this utility again at any time to check or reconfigure GPU support.")