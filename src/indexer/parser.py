"""
Code parsing module.
"""
from typing import List, Dict, Any


class CodeParser:
    def __init__(self):
        pass
    
    def parse_files(self, code_files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse code files into chunks suitable for embedding.
        
        Args:
            code_files: List of dictionaries containing code file information
            
        Returns:
            List of parsed code chunks with metadata
        """
        parsed_files = []
        
        for file in code_files:
            chunks = self._chunk_file(file)
            parsed_files.extend(chunks)
            
        return parsed_files
    
    def _chunk_file(self, file: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split a file into smaller chunks for better retrieval.
        
        Args:
            file: Dictionary containing code file information
            
        Returns:
            List of chunks with metadata
        """
        content = file['content']
        path = file['path']
        
        # Split by function/class or by a fixed number of lines
        lines = content.split('\n')
        chunks = []
        
        # Simple chunking by fixed number of lines
        chunk_size = 50  # Number of lines per chunk
        overlap = 10     # Number of overlapping lines between chunks
        
        for i in range(0, len(lines), chunk_size - overlap):
            chunk_lines = lines[i:i + chunk_size]
            if not chunk_lines:
                continue
                
            chunk_content = '\n'.join(chunk_lines)
            
            # Skip empty chunks
            if not chunk_content.strip():
                continue
            
            chunk = {
                'path': path,
                'content': chunk_content,
                'start_line': i + 1,
                'end_line': min(i + len(chunk_lines), len(lines)),
                'metadata': {
                    'file': path,
                    'language': self._get_language_from_extension(file['extension'])
                }
            }
            
            chunks.append(chunk)
        
        return chunks
    
    def _get_language_from_extension(self, ext: str) -> str:
        """Map file extension to language name."""
        extension_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.jsx': 'JavaScript/React',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript/React',
            '.java': 'Java',
            '.c': 'C',
            '.cpp': 'C++',
            '.h': 'C/C++ Header',
            '.hpp': 'C++ Header',
            '.cs': 'C#',
            '.go': 'Go',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.rs': 'Rust'
        }
        
        return extension_map.get(ext, 'Unknown')