"""
Code structure analysis module for parsing repository structure and relationships.
"""
import os
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
import logging

logger = logging.getLogger('github_repo_analyzer')

class CodeStructureAnalyzer:
    def __init__(self, repo_path: str):
        """
        Initialize the code structure analyzer.
        
        Args:
            repo_path: Path to the repository root
        """
        self.repo_path = Path(repo_path)
        self.modules = {}
        self.dependencies = {}
        self.imports = {}
        self.file_tree = None
    
    def analyze_structure(self) -> Dict[str, Any]:
        """
        Analyze the structure of the repository.
        
        Returns:
            Dictionary containing repository structure information
        """
        logger.info(f"Analyzing structure of repository at {self.repo_path}")
        
        # Build the file tree
        self.file_tree = self._build_file_tree()
        
        # Process Python files to extract imports and dependencies
        self._process_python_files()
        
        return {
            "file_tree": self.file_tree,
            "modules": self.modules,
            "dependencies": self.dependencies,
            "imports": self.imports
        }
    
    def _build_file_tree(self) -> Dict[str, Any]:
        """
        Build a tree representation of the repository file structure.
        
        Returns:
            Dictionary representing the file tree
        """
        logger.info("Building file tree")
        
        root = {
            "name": self.repo_path.name,
            "type": "directory",
            "path": "",
            "children": []
        }
        
        ignore_dirs = {'.git', '__pycache__', 'node_modules', 'venv', 'env', '.venv', '.env'}
        ignore_patterns = {'.pyc', '.pyo', '.pyd', '.so', '.dll', '.class'}
        
        def add_to_tree(current_path, parent_node):
            try:
                items = os.listdir(current_path)
                
                # Sort: directories first, then files
                dirs = [item for item in items if os.path.isdir(os.path.join(current_path, item)) and item not in ignore_dirs]
                files = [item for item in items if os.path.isfile(os.path.join(current_path, item)) and not any(item.endswith(pat) for pat in ignore_patterns)]
                
                dirs.sort()
                files.sort()
                
                # Process directories
                for dir_name in dirs:
                    dir_path = os.path.join(current_path, dir_name)
                    rel_path = os.path.relpath(dir_path, self.repo_path)
                    
                    # Skip hidden directories
                    if dir_name.startswith('.'):
                        continue
                        
                    dir_node = {
                        "name": dir_name,
                        "type": "directory",
                        "path": rel_path.replace('\\', '/'),
                        "children": []
                    }
                    
                    # Recursively add children
                    add_to_tree(dir_path, dir_node)
                    
                    # Only add non-empty directories
                    if dir_node["children"]:
                        parent_node["children"].append(dir_node)
                
                # Process files
                for file_name in files:
                    # Skip hidden files
                    if file_name.startswith('.'):
                        continue
                        
                    file_path = os.path.join(current_path, file_name)
                    rel_path = os.path.relpath(file_path, self.repo_path)
                    
                    file_node = {
                        "name": file_name,
                        "type": "file",
                        "path": rel_path.replace('\\', '/'),
                        "language": self._get_language_from_extension(os.path.splitext(file_name)[1])
                    }
                    
                    parent_node["children"].append(file_node)
            
            except Exception as e:
                logger.error(f"Error processing directory {current_path}: {e}")
        
        # Start building the tree from the repo root
        add_to_tree(self.repo_path, root)
        
        return root
    
    def _process_python_files(self):
        """Process Python files to extract imports, functions, and classes."""
        logger.info("Processing Python files")
        
        python_files = self._find_python_files()
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                rel_path = os.path.relpath(file_path, self.repo_path)
                self._analyze_python_file(rel_path, content)
            
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
    
    def _find_python_files(self) -> List[str]:
        """Find all Python files in the repository."""
        python_files = []
        
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories and common exclude directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and 
                       d not in {'__pycache__', 'venv', 'env', '.venv', '.env', 'node_modules'}]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        return python_files
    
    def _analyze_python_file(self, file_path: str, content: str):
        """
        Analyze a Python file to extract imports, functions, and classes.
        
        Args:
            file_path: Relative path to the file
            content: File content
        """
        try:
            tree = ast.parse(content)
            module_info = {
                "imports": [],
                "functions": [],
                "classes": [],
                "variables": []
            }
            
            # Process imports
            import_names = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        import_names.append(name.name)
                        module_info["imports"].append({
                            "type": "import",
                            "name": name.name,
                            "alias": name.asname
                        })
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for name in node.names:
                        import_names.append(f"{module}.{name.name}" if module else name.name)
                        module_info["imports"].append({
                            "type": "from",
                            "module": module,
                            "name": name.name,
                            "alias": name.asname
                        })
            
            # Store imports
            self.imports[file_path] = import_names
            
            # Process functions
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.FunctionDef):
                    function_info = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "args": [arg.arg for arg in node.args.args],
                        "decorators": [self._get_decorator_name(d) for d in node.decorator_list]
                    }
                    module_info["functions"].append(function_info)
                
                elif isinstance(node, ast.ClassDef):
                    # Get base classes
                    bases = []
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            bases.append(base.id)
                        elif isinstance(base, ast.Attribute):
                            bases.append(f"{self._get_attribute_name(base)}")
                    
                    # Get class methods
                    methods = []
                    for child in ast.iter_child_nodes(node):
                        if isinstance(child, ast.FunctionDef):
                            methods.append(child.name)
                    
                    class_info = {
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "bases": bases,
                        "methods": methods,
                        "decorators": [self._get_decorator_name(d) for d in node.decorator_list]
                    }
                    module_info["classes"].append(class_info)
            
            # Store module info
            self.modules[file_path] = module_info
            
            # Build dependencies
            self.dependencies[file_path] = self._find_dependencies(file_path, import_names)
            
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
    
    def _get_decorator_name(self, decorator) -> str:
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id
            elif isinstance(decorator.func, ast.Attribute):
                return self._get_attribute_name(decorator.func)
        elif isinstance(decorator, ast.Attribute):
            return self._get_attribute_name(decorator)
        return "unknown"
    
    def _get_attribute_name(self, node) -> str:
        """Extract full attribute name from AST node."""
        if isinstance(node, ast.Attribute):
            return f"{self._get_attribute_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Name):
            return node.id
        return "unknown"
    
    def _find_dependencies(self, file_path: str, imports: List[str]) -> List[str]:
        """
        Find dependencies of a file based on imports.
        
        Args:
            file_path: Relative path to the file
            imports: List of imported modules
            
        Returns:
            List of dependencies
        """
        dependencies = []
        file_dir = os.path.dirname(file_path)
        
        for imp in imports:
            # Handle relative imports
            if imp.startswith('.'):
                parts = imp.lstrip('.').split('.')
                level = len(imp) - len(imp.lstrip('.'))
                
                # Navigate up according to the level
                parent_dir = file_dir
                for _ in range(level):
                    parent_dir = os.path.dirname(parent_dir)
                
                # Construct the relative path
                if parts[0]:
                    potential_path = os.path.join(parent_dir, *parts)
                    if os.path.exists(os.path.join(self.repo_path, f"{potential_path}.py")):
                        dependencies.append(f"{potential_path}.py")
                    elif os.path.exists(os.path.join(self.repo_path, potential_path, "__init__.py")):
                        dependencies.append(os.path.join(potential_path, "__init__.py"))
            
            # Handle absolute imports within the project
            else:
                parts = imp.split('.')
                
                # Check if this might be a local module
                potential_path = os.path.join(*parts)
                if os.path.exists(os.path.join(self.repo_path, f"{potential_path}.py")):
                    dependencies.append(f"{potential_path}.py")
                elif os.path.exists(os.path.join(self.repo_path, potential_path, "__init__.py")):
                    dependencies.append(os.path.join(potential_path, "__init__.py"))
        
        return dependencies
    
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
            '.rs': 'Rust',
            '.html': 'HTML',
            '.css': 'CSS',
            '.scss': 'SCSS',
            '.md': 'Markdown',
            '.json': 'JSON',
            '.yml': 'YAML',
            '.yaml': 'YAML',
            '.xml': 'XML',
            '.toml': 'TOML',
            '.ini': 'INI',
            '.sh': 'Shell',
            '.bat': 'Batch'
        }
        
        return extension_map.get(ext.lower(), 'Unknown')

def analyze_repository(repo_path: str) -> Dict[str, Any]:
    """
    Analyze a repository and return its structure.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary containing repository structure information
    """
    analyzer = CodeStructureAnalyzer(repo_path)
    return analyzer.analyze_structure()