"""
Code dependency analysis module for extracting file dependencies and relationships.
"""
import os
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Any
import logging

logger = logging.getLogger('github_repo_analyzer')

class DependencyAnalyzer:
    def __init__(self, repo_path: str):
        """
        Initialize the dependency analyzer.
        
        Args:
            repo_path: Path to the repository root
        """
        self.repo_path = Path(repo_path)
        self.dependencies = {}
        self.imports = {}
        self.modules = {}
        self.file_sizes = {}
    
    def analyze_dependencies(self) -> Dict[str, Any]:
        """
        Analyze the dependencies of the repository.
        
        Returns:
            Dictionary containing dependency information
        """
        logger.info(f"Analyzing dependencies of repository at {self.repo_path}")
        
        # Get file sizes
        self._get_file_sizes()
        
        # Process Python files to extract imports and dependencies
        self._process_python_files()
        
        # Process JavaScript files
        self._process_javascript_files()
        
        # Get the file tree structure
        from .structure import analyze_repository
        file_tree = analyze_repository(str(self.repo_path))['file_tree']
        
        return {
            "dependencies": self.dependencies,
            "imports": self.imports,
            "modules": self.modules,
            "file_sizes": self.file_sizes,
            "file_tree": file_tree
        }
    
    def _get_file_sizes(self):
        """Get the size of all files in the repository."""
        logger.info("Getting file sizes")
        
        for root, _, files in os.walk(self.repo_path):
            # Skip hidden directories and common exclude directories
            if any(part.startswith('.') for part in Path(root).parts) or \
               any(part in ['__pycache__', 'node_modules', 'venv', '.git'] for part in Path(root).parts):
                continue
                
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.repo_path)
                rel_path = rel_path.replace('\\', '/')  # Normalize path separators
                
                try:
                    self.file_sizes[rel_path] = os.path.getsize(file_path)
                except Exception as e:
                    logger.error(f"Error getting size of {file_path}: {e}")
    
    def _process_python_files(self):
        """Process Python files to extract imports and dependencies."""
        logger.info("Processing Python files for dependencies")
        
        python_files = self._find_files('.py')
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                rel_path = os.path.relpath(file_path, self.repo_path)
                rel_path = rel_path.replace('\\', '/')  # Normalize path separators
                
                self._analyze_python_file(rel_path, content)
            
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
    
    def _process_javascript_files(self):
        """Process JavaScript files to extract imports and dependencies."""
        logger.info("Processing JavaScript files for dependencies")
        
        js_files = self._find_files('.js')
        
        for file_path in js_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                rel_path = os.path.relpath(file_path, self.repo_path)
                rel_path = rel_path.replace('\\', '/')  # Normalize path separators
                
                self._analyze_javascript_file(rel_path, content)
            
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
    
    def _find_files(self, extension: str) -> List[str]:
        """Find all files with the given extension in the repository."""
        matching_files = []
        
        for root, dirs, files in os.walk(self.repo_path):
            # Skip hidden directories and common exclude directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and 
                       d not in {'__pycache__', 'venv', 'env', '.venv', '.env', 'node_modules', '.git'}]
            
            for file in files:
                if file.endswith(extension):
                    matching_files.append(os.path.join(root, file))
        
        return matching_files
    
    def _analyze_python_file(self, file_path: str, content: str):
        """
        Analyze a Python file to extract imports and dependencies.
        
        Args:
            file_path: Relative path to the file
            content: File content
        """
        try:
            tree = ast.parse(content)
            
            # Initialize imports and dependencies
            self.imports[file_path] = []
            self.dependencies[file_path] = []
            
            # Initialize module info
            module_info = {
                "imports": [],
                "functions": [],
                "classes": [],
                "variables": []
            }
            
            # Process imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        self.imports[file_path].append(name.name)
                        module_info["imports"].append({
                            "type": "import",
                            "name": name.name,
                            "alias": name.asname
                        })
                        
                        # Add external dependency
                        if not self._is_local_module(name.name):
                            external_path = f"external/{name.name}"
                            self.dependencies[file_path].append(external_path)
                        
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for name in node.names:
                        import_name = f"{module}.{name.name}" if module else name.name
                        self.imports[file_path].append(import_name)
                        module_info["imports"].append({
                            "type": "from",
                            "module": module,
                            "name": name.name,
                            "alias": name.asname
                        })
                        
                        # Add external dependency if not a relative import
                        if not module.startswith('.') and not self._is_local_module(module):
                            external_path = f"external/{module}"
                            self.dependencies[file_path].append(external_path)
            
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
            
            # Find dependencies within the project
            self._find_python_dependencies(file_path)
            
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
    
    def _analyze_javascript_file(self, file_path: str, content: str):
        """
        Analyze a JavaScript file to extract imports and dependencies.
        This is a simple regex-based approach for basic import/require statements.
        
        Args:
            file_path: Relative path to the file
            content: File content
        """
        try:
            import re
            
            # Initialize imports and dependencies
            self.imports[file_path] = []
            self.dependencies[file_path] = []
            
            # Look for ES6 imports
            import_regex = r'import\s+(?:{[^}]*}|[^{]*)\s+from\s+[\'"]([^\'"]+)[\'"]'
            imports = re.findall(import_regex, content)
            
            # Look for require statements
            require_regex = r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
            requires = re.findall(require_regex, content)
            
            # Combine all imports
            all_imports = imports + requires
            
            for imp in all_imports:
                self.imports[file_path].append(imp)
                
                # Determine if local or external
                if imp.startswith('.') or imp.startswith('/'):
                    # Local import - try to resolve the path
                    resolved_path = self._resolve_js_import_path(file_path, imp)
                    if resolved_path:
                        self.dependencies[file_path].append(resolved_path)
                else:
                    # External import
                    external_path = f"external/{imp}"
                    self.dependencies[file_path].append(external_path)
            
        except Exception as e:
            logger.error(f"Error analyzing JavaScript file {file_path}: {e}")
    
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
    
    def _is_local_module(self, module_name: str) -> bool:
        """Check if a module name might refer to a local module."""
        parts = module_name.split('.')
        
        # Check if this might be a local module
        potential_path = os.path.join(self.repo_path, *parts)
        
        return (os.path.exists(f"{potential_path}.py") or 
                os.path.exists(os.path.join(potential_path, "__init__.py")))
    
    def _find_python_dependencies(self, file_path: str):
        """
        Find dependencies of a Python file based on imports.
        
        Args:
            file_path: Relative path to the file
        """
        if file_path not in self.imports:
            return
        
        file_dir = os.path.dirname(file_path)
        
        for imp in self.imports[file_path]:
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
                    potential_path = potential_path.replace('\\', '/')  # Normalize path separators
                    
                    if os.path.exists(os.path.join(self.repo_path, f"{potential_path}.py")):
                        self.dependencies[file_path].append(f"{potential_path}.py")
                    elif os.path.exists(os.path.join(self.repo_path, potential_path, "__init__.py")):
                        self.dependencies[file_path].append(os.path.join(potential_path, "__init__.py").replace('\\', '/'))
            
            # Handle absolute imports within the project
            else:
                parts = imp.split('.')
                
                # Check if this might be a local module
                potential_path = os.path.join(*parts)
                potential_path = potential_path.replace('\\', '/')  # Normalize path separators
                
                if os.path.exists(os.path.join(self.repo_path, f"{potential_path}.py")):
                    self.dependencies[file_path].append(f"{potential_path}.py")
                elif os.path.exists(os.path.join(self.repo_path, potential_path, "__init__.py")):
                    self.dependencies[file_path].append(os.path.join(potential_path, "__init__.py").replace('\\', '/'))
    
    def _resolve_js_import_path(self, file_path: str, import_path: str) -> str:
        """
        Resolve a JavaScript import path to an actual file path.
        
        Args:
            file_path: Path of the file containing the import
            import_path: The import path to resolve
            
        Returns:
            Resolved file path or None if not found
        """
        file_dir = os.path.dirname(file_path)
        
        # Remove any query parameters or hash
        import_path = import_path.split('?')[0].split('#')[0]
        
        # Handle relative paths
        if import_path.startswith('.'):
            # Construct the full path
            full_path = os.path.normpath(os.path.join(file_dir, import_path))
            full_path = full_path.replace('\\', '/')  # Normalize path separators
            
            # Check for exact file match
            if os.path.exists(os.path.join(self.repo_path, full_path)):
                return full_path
            
            # Check with .js extension
            if os.path.exists(os.path.join(self.repo_path, full_path + '.js')):
                return full_path + '.js'
            
            # Check with .jsx extension
            if os.path.exists(os.path.join(self.repo_path, full_path + '.jsx')):
                return full_path + '.jsx'
            
            # Check for index.js in directory
            if os.path.exists(os.path.join(self.repo_path, full_path, 'index.js')):
                return os.path.join(full_path, 'index.js').replace('\\', '/')
        
        return None

def analyze_dependencies(repo_path: str) -> Dict[str, Any]:
    """
    Analyze the dependencies of a repository.
    
    Args:
        repo_path: Path to the repository
        
    Returns:
        Dictionary containing dependency information
    """
    analyzer = DependencyAnalyzer(repo_path)
    return analyzer.analyze_dependencies()