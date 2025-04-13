"""
Incremental indexing module for updating code index efficiently.
"""
import os
import time
import json
import pickle
import hashlib
from typing import Dict, List, Set, Any, Tuple
import logging
import numpy as np
from pathlib import Path

logger = logging.getLogger('github_repo_analyzer')

class IncrementalIndexer:
    def __init__(self, repo_path: str, index_dir: str):
        """
        Initialize the incremental indexer.
        
        Args:
            repo_path: Path to the repository
            index_dir: Directory to store index data
        """
        self.repo_path = Path(repo_path)
        self.index_dir = Path(index_dir)
        self.file_hashes_path = self.index_dir / "file_hashes.json"
        self.file_hashes = {}
        self.changed_files = set()
        self.new_files = set()
        self.deleted_files = set()
    
    def initialize(self):
        """Initialize the incremental indexer."""
        # Create index directory if it doesn't exist
        os.makedirs(self.index_dir, exist_ok=True)
        
        # Load existing file hashes if available
        if os.path.exists(self.file_hashes_path):
            try:
                with open(self.file_hashes_path, 'r') as f:
                    self.file_hashes = json.load(f)
                logger.info(f"Loaded hashes for {len(self.file_hashes)} files")
            except Exception as e:
                logger.error(f"Error loading file hashes: {e}")
                self.file_hashes = {}
    
    def detect_changes(self, code_files: List[Dict[str, Any]]) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Detect changes in the repository since the last indexing.
        
        Args:
            code_files: List of code files from the repository
            
        Returns:
            Tuple of (changed files, new files, deleted files)
        """
        logger.info("Detecting changes in repository")
        
        current_files = {}
        
        # Calculate hashes for current files
        for file in code_files:
            file_path = file['path']
            content = file['content']
            
            # Calculate hash of content
            content_hash = hashlib.md5(content.encode()).hexdigest()
            current_files[file_path] = content_hash
            
            # Check if file is new or changed
            if file_path not in self.file_hashes:
                self.new_files.add(file_path)
                logger.debug(f"New file: {file_path}")
            elif self.file_hashes[file_path] != content_hash:
                self.changed_files.add(file_path)
                logger.debug(f"Changed file: {file_path}")
        
        # Check for deleted files
        for file_path in self.file_hashes:
            if file_path not in current_files:
                self.deleted_files.add(file_path)
                logger.debug(f"Deleted file: {file_path}")
        
        # Update file hashes
        self.file_hashes = current_files
        
        # Save updated file hashes
        try:
            with open(self.file_hashes_path, 'w') as f:
                json.dump(self.file_hashes, f)
            logger.info(f"Saved hashes for {len(self.file_hashes)} files")
        except Exception as e:
            logger.error(f"Error saving file hashes: {e}")
        
        logger.info(f"Changes detected: {len(self.changed_files)} changed, {len(self.new_files)} new, {len(self.deleted_files)} deleted")
        
        return self.changed_files, self.new_files, self.deleted_files
    
    def filter_changed_files(self, code_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter the list of code files to include only changed and new files.
        
        Args:
            code_files: List of all code files
            
        Returns:
            List of changed and new code files
        """
        if not self.changed_files and not self.new_files:
            # No changes detected yet, detect changes
            self.detect_changes(code_files)
        
        # Filter files that need to be processed
        files_to_process = [
            file for file in code_files 
            if file['path'] in self.changed_files or file['path'] in self.new_files
        ]
        
        logger.info(f"Filtered {len(files_to_process)} files to process out of {len(code_files)} total files")
        
        return files_to_process
    
    def update_faiss_index(self, faiss_index, vectorizer, code_parser, code_files: List[Dict[str, Any]]) -> bool:
        """
        Update the FAISS index with changed and new files.
        
        Args:
            faiss_index: FAISS index object
            vectorizer: Vectorizer for encoding text
            code_parser: Code parser for parsing files
            code_files: List of all code files
            
        Returns:
            True if the index was updated, False otherwise
        """
        try:
            # Initialize if not already initialized
            self.initialize()
            
            # Detect changes
            changed_files, new_files, deleted_files = self.detect_changes(code_files)
            
            # If there are no changes, no need to update
            if not changed_files and not new_files and not deleted_files:
                logger.info("No changes detected, index is up to date")
                return False
            
            logger.info(f"Updating index with {len(changed_files)} changed and {len(new_files)} new files")
            
            # Filter files that need to be processed
            files_to_process = self.filter_changed_files(code_files)
            
            if not files_to_process and not deleted_files:
                logger.info("No files to process")
                return False
            
            # Load existing index if available
            if not faiss_index.load_index():
                logger.info("No existing index found, creating new index")
                return False  # No existing index, need to create a new one
            
            # Parse files
            parsed_files = code_parser.parse_files(files_to_process)
            logger.info(f"Parsed {len(parsed_files)} chunks from {len(files_to_process)} files")
            
            # If we have files to add or update
            if parsed_files:
                # Vectorize files
                vectors = vectorizer.vectorize_code(parsed_files)
                
                # Get existing vectors and metadata
                existing_embeddings = faiss_index.index.reconstruct_batch(range(faiss_index.index.ntotal))
                existing_metadata = faiss_index.metadata
                
                # Filter out deleted and changed files from existing data
                files_to_remove = changed_files.union(deleted_files)
                indices_to_keep = [
                    i for i, meta in enumerate(existing_metadata)
                    if meta['path'] not in files_to_remove
                ]
                
                # Create new index with filtered data plus new data
                if indices_to_keep:
                    filtered_embeddings = existing_embeddings[indices_to_keep]
                    filtered_metadata = [existing_metadata[i] for i in indices_to_keep]
                    
                    # Combine with new data
                    combined_embeddings = np.vstack([filtered_embeddings, vectors['embeddings']])
                    combined_metadata = filtered_metadata + vectors['metadata']
                else:
                    # If all existing data is being replaced
                    combined_embeddings = vectors['embeddings']
                    combined_metadata = vectors['metadata']
                
                # Create new index
                faiss_index.create_index({
                    'embeddings': combined_embeddings,
                    'metadata': combined_metadata
                }, combined_metadata)
                
                logger.info(f"Updated index with {len(parsed_files)} new chunks, total chunks: {faiss_index.index.ntotal}")
                return True
            
            # If we only have deleted files
            elif deleted_files:
                # Get existing vectors and metadata
                existing_embeddings = faiss_index.index.reconstruct_batch(range(faiss_index.index.ntotal))
                existing_metadata = faiss_index.metadata
                
                # Filter out deleted files from existing data
                indices_to_keep = [
                    i for i, meta in enumerate(existing_metadata)
                    if meta['path'] not in deleted_files
                ]
                
                # Create new index with filtered data
                filtered_embeddings = existing_embeddings[indices_to_keep]
                filtered_metadata = [existing_metadata[i] for i in indices_to_keep]
                
                # Create new index
                faiss_index.create_index({
                    'embeddings': filtered_embeddings,
                    'metadata': filtered_metadata
                }, filtered_metadata)
                
                logger.info(f"Updated index by removing {len(deleted_files)} deleted files, total chunks: {faiss_index.index.ntotal}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating FAISS index: {e}")
            import traceback
            traceback.print_exc()
            return False