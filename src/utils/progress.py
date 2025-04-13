"""
Progress tracking module for long-running operations.
"""
import threading
import time
from typing import Dict, Optional, Callable

class ProgressTracker:
    """
    Singleton class to track progress of various operations.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProgressTracker, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize the progress tracker state."""
        self.operations = {}
        self.lock = threading.Lock()
    
    def start_operation(self, operation_id: str, description: str = "") -> None:
        """
        Start tracking a new operation.
        
        Args:
            operation_id: Unique identifier for the operation
            description: Human-readable description of the operation
        """
        with self.lock:
            self.operations[operation_id] = {
                'status': 'in_progress',
                'progress': 0.0,
                'description': description,
                'message': f"Starting {description}...",
                'start_time': time.time(),
                'end_time': None
            }
    
    def update_progress(self, operation_id: str, progress: float, message: str = "") -> None:
        """
        Update the progress of an ongoing operation.
        
        Args:
            operation_id: Identifier of the operation to update
            progress: Progress value between 0.0 and 1.0
            message: Optional status message
        """
        with self.lock:
            if operation_id in self.operations:
                self.operations[operation_id]['progress'] = min(max(progress, 0.0), 1.0)
                if message:
                    self.operations[operation_id]['message'] = message
    
    def complete_operation(self, operation_id: str, success: bool = True, message: str = "") -> None:
        """
        Mark an operation as complete.
        
        Args:
            operation_id: Identifier of the operation to complete
            success: Whether the operation completed successfully
            message: Optional completion message
        """
        with self.lock:
            if operation_id in self.operations:
                self.operations[operation_id]['status'] = 'success' if success else 'error'
                self.operations[operation_id]['progress'] = 1.0 if success else self.operations[operation_id]['progress']
                if message:
                    self.operations[operation_id]['message'] = message
                self.operations[operation_id]['end_time'] = time.time()
    
    def get_operation_status(self, operation_id: str) -> Dict:
        """
        Get the current status of an operation.
        
        Args:
            operation_id: Identifier of the operation
            
        Returns:
            Dictionary containing operation status information
        """
        with self.lock:
            if operation_id in self.operations:
                return self.operations[operation_id].copy()
            return {
                'status': 'not_found',
                'progress': 0.0,
                'message': f"Operation {operation_id} not found"
            }
    
    def get_all_operations(self) -> Dict:
        """
        Get the status of all operations.
        
        Returns:
            Dictionary mapping operation IDs to their status information
        """
        with self.lock:
            return {k: v.copy() for k, v in self.operations.items()}


# Create proxy functions for easy access to the singleton
_tracker = ProgressTracker()

def start_operation(operation_id: str, description: str = "") -> None:
    """Start tracking a new operation."""
    _tracker.start_operation(operation_id, description)

def update_progress(operation_id: str, progress: float, message: str = "") -> None:
    """Update the progress of an ongoing operation."""
    _tracker.update_progress(operation_id, progress, message)

def complete_operation(operation_id: str, success: bool = True, message: str = "") -> None:
    """Mark an operation as complete."""
    _tracker.complete_operation(operation_id, success, message)

def get_operation_status(operation_id: str) -> Dict:
    """Get the current status of an operation."""
    return _tracker.get_operation_status(operation_id)

def get_all_operations() -> Dict:
    """Get the status of all operations."""
    return _tracker.get_all_operations()


class ProgressHook:
    """
    Progress hook for libraries that support callbacks during downloads.
    Compatible with huggingface_hub and other similar libraries.
    """
    def __init__(self, operation_id: str, total_size: Optional[int] = None):
        self.operation_id = operation_id
        self.total_size = total_size
        self.downloaded = 0
        
    def __call__(self, size: int, total: Optional[int] = None) -> None:
        self.downloaded += size
        
        if total is not None:
            self.total_size = total
            
        if self.total_size:
            progress = min(self.downloaded / self.total_size, 1.0)
            update_progress(
                self.operation_id, 
                progress, 
                f"Downloaded {self.downloaded / 1024 / 1024:.1f}MB of {self.total_size / 1024 / 1024:.1f}MB"
            )