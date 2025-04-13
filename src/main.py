#!/usr/bin/env python3
"""
GitHub Repository Analyzer
A tool for analyzing GitHub repositories using FAISS and RAG.
"""
import os
import sys
import json
import argparse
import logging
import traceback
import requests
import webbrowser
import threading
import time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('github_repo_analyzer')

# Print startup message
print("Starting GitHub Repository Analyzer...")

try:
    print("Importing modules...")
    from config import Config
    from github.repo import GitHubRepo
    from indexer.parser import CodeParser
    from indexer.vectorizer import CodeVectorizer
    from indexer.structure import analyze_repository
    from indexer.dependencies import analyze_dependencies
    from indexer.incremental import IncrementalIndexer
    from retriever.faiss_index import FAISSIndex
    from retriever.hybrid_search import HybridSearch
    from generator.llm import LLMGenerator
    from generator.code_generator import CodeGenerator
    from utils.progress import get_operation_status, get_all_operations, start_operation, update_progress, complete_operation
    print("All modules imported successfully")
except Exception as e:
    print(f"Error importing modules: {e}")
    traceback.print_exc()
    sys.exit(1)

# Initialize Flask app
print("Initializing Flask app...")
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), "ui", "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "ui", "static"))

# Global variables
print("Initializing configuration...")
try:
    config = Config()
    print(f"Configuration initialized successfully. Data directory: {config.data_dir}")
except Exception as e:
    print(f"Error initializing configuration: {e}")
    traceback.print_exc()
    sys.exit(1)

# Set the port for the application
PORT = getattr(config, 'PORT', 5000)

repo_handler = None
code_parser = None
vectorizer = None
faiss_index = None
llm_generator = None
code_generator = None
hybrid_search = None
incremental_indexer = None
code_structure = None
dependency_data = None
state_file = os.path.join(config.data_dir, "app_state.json")


def save_app_state():
    """Save application state to disk."""
    if repo_handler is None:
        return
    
    state = {
        "repo_url": repo_handler.repo_url,
        "repo_name": repo_handler.repo_name,
        "index_exists": faiss_index is not None,
        "last_updated": datetime.now().isoformat()
    }
    
    try:
        with open(state_file, 'w') as f:
            json.dump(state, f)
        logger.info(f"Application state saved to {state_file}")
    except Exception as e:
        logger.error(f"Error saving application state: {e}")


def load_app_state():
    """Load application state from disk."""
    global repo_handler, faiss_index, vectorizer, code_structure, hybrid_search, incremental_indexer
    
    if not os.path.exists(state_file):
        logger.info("No saved state found")
        return False
    
    try:
        with open(state_file, 'r') as f:
            state = json.load(f)
        
        logger.info(f"Loaded saved state: {state}")
        
        # Restore repository handler
        if "repo_url" in state:
            repo_handler = GitHubRepo(state["repo_url"], config.repos_dir, None)
            logger.info(f"Restored repository handler for {state['repo_url']}")
        
        # Restore FAISS index if it exists
        if state.get("index_exists", False):
            # Initialize vectorizer
            logger.info("Initializing vectorizer for saved state")
            vectorizer = CodeVectorizer(config.model_name)
            
            # Load FAISS index
            logger.info("Loading FAISS index from saved state")
            faiss_index = FAISSIndex(config.index_dir, config.dimension)
            if not faiss_index.load_index():
                logger.warning("Failed to load FAISS index from saved state")
                faiss_index = None
                return False
            else:
                logger.info("FAISS index loaded successfully")
                
                # Initialize hybrid search
                hybrid_search = HybridSearch(faiss_index, vectorizer)
                
                # Initialize incremental indexer
                incremental_indexer = IncrementalIndexer(str(repo_handler.repo_path), config.index_dir)
                incremental_indexer.initialize()
                
                # Load code structure if repo exists
                if repo_handler and repo_handler.repo_path.exists():
                    try:
                        code_structure = analyze_repository(str(repo_handler.repo_path))
                    except Exception as e:
                        logger.error(f"Error analyzing repository structure: {e}")
                
                return True
    except Exception as e:
        logger.error(f"Error loading application state: {e}")
        traceback.print_exc()
        return False


def check_model_exists(model_name, is_llm=False):
    """Check if a model exists in the local cache."""
    if is_llm:
        # Check for LLM model (GGUF file)
        model_path = os.path.expanduser("~/.cache/huggingface/hub/models--TheBloke--Llama-2-7B-Chat-GGUF/snapshots/")
        if os.path.exists(model_path):
            dirs = [d for d in os.listdir(model_path) if os.path.isdir(os.path.join(model_path, d))]
            if dirs:
                latest_dir = sorted(dirs)[-1]
                model_dir = os.path.join(model_path, latest_dir)
                gguf_files = [f for f in os.listdir(model_dir) if f.endswith('.gguf')]
                return len(gguf_files) > 0
        return False
    else:
        # Check for Transformer model
        model_path = os.path.expanduser(f"~/.cache/huggingface/hub")
        # Since we don't know the exact path structure for all models, we'll just check
        # if the directory exists and contains files
        return os.path.exists(model_path) and len(os.listdir(model_path)) > 0


@app.route('/')
def index():
    logger.info("Rendering index page")
    return render_template('index.html')


@app.route('/visualization')
def visualization():
    logger.info("Rendering visualization page")
    return render_template('visualization.html')


@app.route('/api/system-status', methods=['GET'])
def get_system_status():
    """Get the status of system components."""
    vectorizer_model_exists = check_model_exists(config.model_name, is_llm=False)
    llm_model_exists = check_model_exists(config.llm_model, is_llm=True)
    
    # Check if we have an indexed repository
    repo_indexed = faiss_index is not None
    repository_info = None
    
    if repo_handler:
        repository_info = {
            "url": repo_handler.repo_url,
            "name": repo_handler.repo_name,
            "path": str(repo_handler.repo_path),
            "indexed": repo_indexed
        }
    
    return jsonify({
        "vectorizer": {
            "exists": vectorizer_model_exists,
            "name": config.model_name
        },
        "llm": {
            "exists": llm_model_exists,
            "name": config.llm_model
        },
        "repository": repository_info,
        "features": {
            "hybrid_search": hybrid_search is not None,
            "incremental_indexing": incremental_indexer is not None,
            "code_generation": code_generator is not None
        }
    })


@app.route('/api/setup', methods=['POST'])
def setup_system():
    """Download all required models."""
    global vectorizer, llm_generator, code_generator
    
    start_operation("setup", "Setting up system components")
    update_progress("setup", 0.1, "Initializing vectorizer...")
    
    try:
        # Initialize vectorizer to trigger download
        if vectorizer is None:
            vectorizer = CodeVectorizer(config.model_name)
        
        # Force model loading to download if needed
        update_progress("setup", 0.3, "Loading vectorizer model...")
        vectorizer._load_model()
        
        update_progress("setup", 0.5, "Initializing LLM...")
        
        # Initialize LLM generator to trigger download
        if llm_generator is None:
            llm_generator = LLMGenerator(config.llm_model)
        
        # Force model loading to download if needed
        update_progress("setup", 0.7, "Loading LLM model...")
        llm_generator._load_model()
        
        # Initialize code generator
        update_progress("setup", 0.9, "Initializing code generator...")
        if code_generator is None:
            code_generator = CodeGenerator(llm_generator)
        
        update_progress("setup", 0.95, "Finalizing setup...")
        complete_operation("setup", True, "System setup completed successfully")
        
        return jsonify({
            "status": "success",
            "message": "System setup completed successfully"
        })
    except Exception as e:
        logger.error(f"Error setting up system: {e}")
        traceback.print_exc()
        complete_operation("setup", False, f"Error setting up system: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error setting up system: {str(e)}"
        })


@app.route('/api/clone', methods=['POST'])
def clone_repo():
    """Clone a repository and automatically index it."""
    logger.info("Clone repository API called")
    data = request.get_json()
    repo_url = data.get('repo_url')
    github_token = data.get('token')
    incremental = data.get('incremental', True)  # Default to incremental indexing
    logger.info(f"Repository URL: {repo_url}")
    
    global repo_handler, code_parser, vectorizer, faiss_index, code_structure, hybrid_search, incremental_indexer, dependency_data
    
    start_operation("repo_processing", "Processing repository")
    update_progress("repo_processing", 0.1, "Initializing repository clone...")
    
    try:
        # If using GitHub API, validate the repo exists
        if github_token:
            update_progress("repo_processing", 0.15, "Validating repository using GitHub API...")
            if not validate_github_repo(repo_url, github_token):
                complete_operation("repo_processing", False, "Repository not found or not accessible")
                return jsonify({
                    "status": "error",
                    "message": "Repository not found or not accessible with the provided token"
                })
        
        # Clone repository
        logger.info("Creating repository handler...")
        repo_handler = GitHubRepo(repo_url, config.repos_dir, github_token)
        
        logger.info("Cloning repository...")
        update_progress("repo_processing", 0.2, "Cloning repository...")
        repo_path = repo_handler.clone()
        logger.info(f"Repository cloned successfully to {repo_path}")
        
        # Initialize code parser
        logger.info("Initializing code parser...")
        code_parser = CodeParser()
        
        # Initialize vectorizer if needed
        if vectorizer is None:
            logger.info(f"Initializing vectorizer with model {config.model_name}...")
            update_progress("repo_processing", 0.3, "Setting up vectorizer...")
            vectorizer = CodeVectorizer(config.model_name)
        
        # Get code files
        logger.info("Getting code files...")
        update_progress("repo_processing", 0.4, "Reading code files...")
        code_files = repo_handler.get_code_files()
        logger.info(f"Found {len(code_files)} code files")
        
        # Check if we should use incremental indexing
        if incremental and faiss_index is not None:
            # Initialize incremental indexer if not already initialized
            if incremental_indexer is None:
                logger.info("Initializing incremental indexer...")
                update_progress("repo_processing", 0.45, "Setting up incremental indexing...")
                incremental_indexer = IncrementalIndexer(str(repo_path), config.index_dir)
                incremental_indexer.initialize()
            
            # Try incremental update
            logger.info("Attempting incremental index update...")
            update_progress("repo_processing", 0.5, "Performing incremental indexing...")
            
            if incremental_indexer.update_faiss_index(faiss_index, vectorizer, code_parser, code_files):
                logger.info("Incremental index update successful")
                update_progress("repo_processing", 0.7, "Incremental indexing completed")
            else:
                # Fallback to full indexing
                logger.info("Incremental update not possible, falling back to full indexing")
                update_progress("repo_processing", 0.5, "Falling back to full indexing...")
                
                # Parse files
                logger.info("Parsing files...")
                update_progress("repo_processing", 0.55, f"Parsing {len(code_files)} code files...")
                parsed_files = code_parser.parse_files(code_files)
                logger.info(f"Parsed into {len(parsed_files)} chunks")
                
                # Vectorize and create FAISS index
                logger.info("Vectorizing code chunks...")
                update_progress("repo_processing", 0.7, f"Vectorizing {len(parsed_files)} code chunks...")
                vectors = vectorizer.vectorize_code(parsed_files)
                
                logger.info("Creating FAISS index...")
                update_progress("repo_processing", 0.8, "Creating FAISS index...")
                faiss_index = FAISSIndex(config.index_dir, config.dimension)
                faiss_index.create_index(vectors, parsed_files)
                logger.info("FAISS index created successfully")
        else:
            # Full indexing
            logger.info("Performing full indexing...")
            update_progress("repo_processing", 0.5, "Performing full indexing...")
            
            # Parse files
            logger.info("Parsing files...")
            update_progress("repo_processing", 0.55, f"Parsing {len(code_files)} code files...")
            parsed_files = code_parser.parse_files(code_files)
            logger.info(f"Parsed into {len(parsed_files)} chunks")
            
            # Vectorize and create FAISS index
            logger.info("Vectorizing code chunks...")
            update_progress("repo_processing", 0.7, f"Vectorizing {len(parsed_files)} code chunks...")
            vectors = vectorizer.vectorize_code(parsed_files)
            
            logger.info("Creating FAISS index...")
            update_progress("repo_processing", 0.8, "Creating FAISS index...")
            faiss_index = FAISSIndex(config.index_dir, config.dimension)
            faiss_index.create_index(vectors, parsed_files)
            logger.info("FAISS index created successfully")
        
        # Initialize hybrid search
        logger.info("Initializing hybrid search...")
        update_progress("repo_processing", 0.85, "Setting up hybrid search...")
        hybrid_search = HybridSearch(faiss_index, vectorizer)
        
        # Analyze code structure
        logger.info("Analyzing code structure...")
        update_progress("repo_processing", 0.9, "Analyzing code structure...")
        try:
            code_structure = analyze_repository(str(repo_path))
            logger.info("Code structure analysis complete")
        except Exception as e:
            logger.error(f"Error analyzing code structure: {e}")
            code_structure = None
        
        # Analyze dependencies
        logger.info("Analyzing dependencies...")
        update_progress("repo_processing", 0.95, "Analyzing dependencies...")
        try:
            dependency_data = analyze_dependencies(str(repo_path))
            logger.info("Dependency analysis complete")
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}")
            dependency_data = None
        
        # Save application state
        save_app_state()
        
        update_progress("repo_processing", 1.0, "Repository processing complete")
        complete_operation("repo_processing", True, "Repository cloned and indexed successfully")
        
        return jsonify({
            "status": "success", 
            "message": "Repository cloned and indexed successfully",
            "repo_name": repo_handler.repo_name
        })
    except Exception as e:
        logger.error(f"Error processing repository: {e}")
        traceback.print_exc()
        complete_operation("repo_processing", False, f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})


@app.route('/api/code-structure', methods=['GET'])
def get_code_structure():
    """Get the code structure of the current repository."""
    global code_structure, repo_handler
    
    if not code_structure and repo_handler and repo_handler.repo_path.exists():
        try:
            code_structure = analyze_repository(str(repo_handler.repo_path))
        except Exception as e:
            logger.error(f"Error analyzing code structure: {e}")
            return jsonify({
                "status": "error",
                "message": f"Error analyzing code structure: {str(e)}"
            })
    
    if code_structure:
        return jsonify({
            "status": "success",
            "structure": code_structure["file_tree"]
        })
    else:
        return jsonify({
            "status": "error",
            "message": "No repository loaded or structure not available"
        })


@app.route('/api/dependency-data', methods=['GET'])
def get_dependency_data():
    """Get the dependency data of the current repository."""
    global dependency_data, repo_handler
    
    if not dependency_data and repo_handler and repo_handler.repo_path.exists():
        try:
            dependency_data = analyze_dependencies(str(repo_handler.repo_path))
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}")
            return jsonify({
                "status": "error",
                "message": f"Error analyzing dependencies: {str(e)}"
            })
    
    if dependency_data:
        return jsonify({
            "status": "success",
            "data": dependency_data
        })
    else:
        return jsonify({
            "status": "error",
            "message": "No repository loaded or dependency data not available"
        })


@app.route('/api/file-content', methods=['GET'])
def get_file_content():
    """Get the content of a specific file."""
    file_path = request.args.get('path')
    
    if not file_path or not repo_handler:
        return jsonify({
            "status": "error",
            "message": "No file path or repository specified"
        })
    
    try:
        full_path = os.path.join(repo_handler.repo_path, file_path)
        
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return jsonify({
                "status": "error",
                "message": f"File {file_path} not found"
            })
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            "status": "success",
            "path": file_path,
            "content": content,
            "language": os.path.splitext(file_path)[1].lstrip('.')
        })
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Error reading file: {str(e)}"
        })


@app.route('/api/ask', methods=['POST'])
def ask_question():
    logger.info("Ask question API called")
    global faiss_index, llm_generator, vectorizer, hybrid_search
    
    data = request.get_json()
    question = data.get('question')
    use_hybrid = data.get('hybrid_search', True)  # Default to using hybrid search
    semantic_weight = data.get('semantic_weight', 0.7)  # Weight for semantic search
    logger.info(f"Question: {question}")
    
    if not faiss_index:
        logger.error("No indexed repository available")
        # Check if we should try to load it from saved state
        if os.path.exists(state_file) and repo_handler and not vectorizer:
            logger.info("Attempting to load vectorizer and index from saved state")
            vectorizer = CodeVectorizer(config.model_name)
            temp_faiss_index = FAISSIndex(config.index_dir, config.dimension)
            if temp_faiss_index.load_index():
                logger.info("Successfully loaded index from saved state")
                faiss_index = temp_faiss_index
                hybrid_search = HybridSearch(faiss_index, vectorizer)
            else:
                return jsonify({
                    "status": "error", 
                    "message": "No indexed repository available. Please index the repository first."
                })
        else:
            return jsonify({
                "status": "error", 
                "message": "No indexed repository available. Please index the repository first."
            })
    
    try:
        start_operation("question_answering", "Processing question")
        update_progress("question_answering", 0.1, "Preparing to answer question...")
        
        if not llm_generator:
            logger.info(f"Initializing LLM generator with model {config.llm_model}...")
            update_progress("question_answering", 0.2, "Initializing LLM...")
            llm_generator = LLMGenerator(config.llm_model)
        
        # Retrieve relevant code snippets
        logger.info("Searching for relevant code...")
        update_progress("question_answering", 0.3, "Finding relevant code...")
        
        if use_hybrid and hybrid_search:
            # Use hybrid search
            logger.info("Using hybrid search")
            results = hybrid_search.search(question, k=5, semantic_weight=semantic_weight)
        else:
            # Use regular semantic search
            logger.info("Using semantic search")
            query_vector = vectorizer.encode_query(question)
            results = faiss_index.search(query_vector, k=5)
            
        logger.info(f"Found {len(results)} relevant code snippets")
        
        # Enhance context with code structure information if available
        if code_structure and any(keyword in question.lower() for keyword in ['structure', 'organization', 'architecture', 'design']):
            logger.info("Adding code structure information to context")
            update_progress("question_answering", 0.4, "Enhancing context with code structure...")
            
            # Add a special context item with repository structure information
            structure_context = {
                'path': '_structure_overview_',
                'content': f"Repository Structure Overview:\n{json.dumps(code_structure['modules'], indent=2)}",
                'start_line': 0,
                'end_line': 0,
                'metadata': {
                    'file': '_structure_overview_',
                    'language': 'JSON'
                },
                'score': 0.9
            }
            
            results.append(structure_context)
        
        # Generate answer with RAG
        logger.info("Generating answer...")
        update_progress("question_answering", 0.5, "Generating answer...")
        answer = llm_generator.generate(question, results)
        logger.info("Answer generated successfully")
        
        update_progress("question_answering", 1.0, "Answer generation complete")
        complete_operation("question_answering", True, "Answer generated successfully")
        
        return jsonify({
            "status": "success", 
            "answer": answer,
            "context": results,
            "search_type": "hybrid" if use_hybrid and hybrid_search else "semantic"
        })
    except Exception as e:
        logger.error(f"Error generating answer: {e}")
        traceback.print_exc()
        complete_operation("question_answering", False, f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})


@app.route('/api/generate-tests', methods=['POST'])
def generate_tests():
    """Generate tests for a specific file."""
    global code_generator, llm_generator
    
    data = request.get_json()
    file_path = data.get('path')
    
    if not file_path or not repo_handler:
        return jsonify({
            "status": "error",
            "message": "No file path or repository specified"
        })
    
    try:
        # Initialize code generator if needed
        if code_generator is None:
            if llm_generator is None:
                llm_generator = LLMGenerator(config.llm_model)
            code_generator = CodeGenerator(llm_generator)
        
        # Get file content
        full_path = os.path.join(repo_handler.repo_path, file_path)
        
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return jsonify({
                "status": "error",
                "message": f"File {file_path} not found"
            })
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Start operation
        operation_id = "code_generation"
        start_operation(operation_id, f"Generating tests for {file_path}")
        update_progress(operation_id, 0.2, "Analyzing code...")
        
        # Generate tests
        update_progress(operation_id, 0.4, "Generating tests...")
        tests = code_generator.generate_tests(content, file_path)
        
        complete_operation(operation_id, True, "Tests generated successfully")
        
        return jsonify({
            "status": "success",
            "path": file_path,
            "tests": tests
        })
    except Exception as e:
        logger.error(f"Error generating tests: {e}")
        if operation_id:
            complete_operation(operation_id, False, f"Error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error generating tests: {str(e)}"
        })


@app.route('/api/generate-docs', methods=['POST'])
def generate_docs():
    """Generate documentation for a specific file."""
    global code_generator, llm_generator
    
    data = request.get_json()
    file_path = data.get('path')
    
    if not file_path or not repo_handler:
        return jsonify({
            "status": "error",
            "message": "No file path or repository specified"
        })
    
    try:
        # Initialize code generator if needed
        if code_generator is None:
            if llm_generator is None:
                llm_generator = LLMGenerator(config.llm_model)
            code_generator = CodeGenerator(llm_generator)
        
        # Get file content
        full_path = os.path.join(repo_handler.repo_path, file_path)
        
        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            return jsonify({
                "status": "error",
                "message": f"File {file_path} not found"
            })
        
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Start operation
        operation_id = "code_generation"
        start_operation(operation_id, f"Generating documentation for {file_path}")
        update_progress(operation_id, 0.2, "Analyzing code...")
        
        # Generate documentation
        update_progress(operation_id, 0.4, "Generating documentation...")
        docs = code_generator.generate_documentation(content, file_path)
        
        complete_operation(operation_id, True, "Documentation generated successfully")
        
        return jsonify({
            "status": "success",
            "path": file_path,
            "documentation": docs
        })
    except Exception as e:
        logger.error(f"Error generating documentation: {e}")
        if operation_id:
            complete_operation(operation_id, False, f"Error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error generating documentation: {str(e)}"
        })


@app.route('/api/explain-code', methods=['POST'])
def explain_code():
    """Generate an explanation of a specific file or code snippet."""
    global code_generator, llm_generator
    
    data = request.get_json()
    file_path = data.get('path')
    code_snippet = data.get('code')
    
    if not file_path and not code_snippet:
        return jsonify({
            "status": "error",
            "message": "No file path or code snippet provided"
        })
    
    try:
        # Initialize code generator if needed
        if code_generator is None:
            if llm_generator is None:
                llm_generator = LLMGenerator(config.llm_model)
            code_generator = CodeGenerator(llm_generator)
        
        # Start operation
        operation_id = "code_explanation"
        start_operation(operation_id, f"Generating explanation")
        
        if file_path and repo_handler:
            # Get file content
            full_path = os.path.join(repo_handler.repo_path, file_path)
            
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                complete_operation(operation_id, False, f"File {file_path} not found")
                return jsonify({
                    "status": "error",
                    "message": f"File {file_path} not found"
                })
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            update_progress(operation_id, 0.3, f"Analyzing {file_path}...")
            explanation = code_generator.generate_code_explanation(content, file_path)
        else:
            # Use provided code snippet
            update_progress(operation_id, 0.3, "Analyzing code snippet...")
            explanation = code_generator.generate_code_explanation(
                code_snippet, 
                "code_snippet.txt",
                language=data.get('language', 'text')
            )
        
        complete_operation(operation_id, True, "Explanation generated successfully")
        
        return jsonify({
            "status": "success",
            "explanation": explanation
        })
    except Exception as e:
        logger.error(f"Error generating explanation: {e}")
        if operation_id:
            complete_operation(operation_id, False, f"Error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error generating explanation: {str(e)}"
        })


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get progress information for all operations."""
    operations = get_all_operations()
    return jsonify({"operations": operations})


@app.route('/api/progress/<operation_id>', methods=['GET'])
def get_operation_progress(operation_id):
    """Get progress information for a specific operation."""
    status = get_operation_status(operation_id)
    return jsonify({"operation": status})


def validate_github_repo(repo_url, token):
    """Validate that a GitHub repository exists and is accessible."""
    try:
        # Extract owner and repo from URL
        parts = repo_url.strip('/').split('/')
        if 'github.com' in parts:
            idx = parts.index('github.com')
            if len(parts) >= idx + 3:
                owner = parts[idx + 1]
                repo = parts[idx + 2]
                
                # Make API request to check if repo exists
                api_url = f"https://api.github.com/repos/{owner}/{repo}"
                headers = {"Authorization": f"token {token}"} if token else {}
                
                response = requests.get(api_url, headers=headers)
                return response.status_code == 200
        
        return False
    except Exception as e:
        logger.error(f"Error validating GitHub repository: {e}")
        return False


def open_browser():
    """Open the browser after a delay"""
    def _open_browser():
        time.sleep(1.5)  # Wait for the server to start
        url = f"http://127.0.0.1:{PORT}"
        print(f"Opening browser at {url}")
        webbrowser.open(url)
    
    browser_thread = threading.Thread(target=_open_browser)
    browser_thread.daemon = True
    browser_thread.start()


def main():
    parser = argparse.ArgumentParser(description='GitHub Repository Analyzer')
    parser.add_argument('--host', default='127.0.0.1', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=PORT, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--no-browser', action='store_true', help='Do not open browser automatically')
    
    args = parser.parse_args()
    
    # Create necessary directories
    print("Creating necessary directories...")
    os.makedirs(config.repos_dir, exist_ok=True)
    os.makedirs(config.index_dir, exist_ok=True)
    os.makedirs(config.models_dir, exist_ok=True)
    os.makedirs(config.data_dir, exist_ok=True)
    
    # Load saved application state
    print("Loading saved application state...")
    load_app_state()
    
    # Open browser automatically unless --no-browser was specified
    if not args.no_browser:
        open_browser()
    
    # Run the Flask app
    print(f"Starting Flask app on {args.host}:{args.port}...")
    print(f"You can access the application at http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)