"""
Code generator module for generating tests and documentation.
"""
import os
import re
import ast
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger('github_repo_analyzer')

class CodeGenerator:
    def __init__(self, llm_generator):
        """
        Initialize the code generator.
        
        Args:
            llm_generator: LLM generator for text generation
        """
        self.llm_generator = llm_generator
    
    def generate_tests(self, code_content: str, file_path: str, language: str = None) -> str:
        """
        Generate test code for the given file.
        
        Args:
            code_content: Content of the code file
            file_path: Path to the code file
            language: Programming language of the code
            
        Returns:
            Generated test code
        """
        logger.info(f"Generating tests for {file_path}")
        
        # Determine language if not provided
        if not language:
            language = self._detect_language(file_path)
        
        # Extract functions and classes for targeted test generation
        functions, classes = self._extract_code_elements(code_content, language)
        
        # Create prompt for test generation
        prompt = self._create_test_prompt(code_content, file_path, language, functions, classes)
        
        # Generate tests using LLM
        tests = self.llm_generator.generate(prompt, [])
        
        return tests
    
    def generate_documentation(self, code_content: str, file_path: str, language: str = None) -> str:
        """
        Generate documentation for the given file.
        
        Args:
            code_content: Content of the code file
            file_path: Path to the code file
            language: Programming language of the code
            
        Returns:
            Generated documentation
        """
        logger.info(f"Generating documentation for {file_path}")
        
        # Determine language if not provided
        if not language:
            language = self._detect_language(file_path)
        
        # Extract functions and classes for targeted documentation generation
        functions, classes = self._extract_code_elements(code_content, language)
        
        # Create prompt for documentation generation
        prompt = self._create_documentation_prompt(code_content, file_path, language, functions, classes)
        
        # Generate documentation using LLM
        documentation = self.llm_generator.generate(prompt, [])
        
        return documentation
    
    def generate_code_explanation(self, code_content: str, file_path: str, language: str = None) -> str:
        """
        Generate an explanation of the code.
        
        Args:
            code_content: Content of the code file
            file_path: Path to the code file
            language: Programming language of the code
            
        Returns:
            Generated explanation
        """
        logger.info(f"Generating explanation for {file_path}")
        
        # Determine language if not provided
        if not language:
            language = self._detect_language(file_path)
        
        # Create prompt for explanation generation
        prompt = f"""You are a programming expert who explains code in clear, concise terms.
                    Please explain the following code file:

                    File: {file_path}
                    Language: {language}

                    ```{language}
                    {code_content}
                    ```

                    Provide a detailed explanation of:
                    1. What this code does
                    2. Its main components and how they interact
                    3. The purpose and functionality of key functions and classes
                    4. Any notable patterns or techniques used
                    5. Potential issues or improvements

                    Explanation:
                    """
        
        # Generate explanation using LLM
        explanation = self.llm_generator.generate(prompt, [])
        
        return explanation
    
    def _detect_language(self, file_path: str) -> str:
        """
        Detect the programming language based on file extension.
        
        Args:
            file_path: Path to the code file
            
        Returns:
            Programming language name
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'cpp',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.rs': 'rust',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.md': 'markdown',
            '.json': 'json',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.xml': 'xml',
            '.sh': 'bash',
            '.bat': 'batch'
        }
        
        return language_map.get(ext, 'text')
    
    def _extract_code_elements(self, code_content: str, language: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract functions and classes from code content.
        
        Args:
            code_content: Content of the code file
            language: Programming language of the code
            
        Returns:
            Tuple of (functions, classes)
        """
        functions = []
        classes = []
        
        try:
            if language == 'python':
                # Parse Python code with AST
                tree = ast.parse(code_content)
                
                # Extract functions
                for node in ast.iter_child_nodes(tree):
                    if isinstance(node, ast.FunctionDef):
                        functions.append({
                            'name': node.name,
                            'docstring': ast.get_docstring(node),
                            'args': [arg.arg for arg in node.args.args],
                            'line_start': node.lineno,
                            'line_end': node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                        })
                    
                    elif isinstance(node, ast.ClassDef):
                        class_methods = []
                        
                        for child in ast.iter_child_nodes(node):
                            if isinstance(child, ast.FunctionDef):
                                class_methods.append({
                                    'name': child.name,
                                    'docstring': ast.get_docstring(child),
                                    'args': [arg.arg for arg in child.args.args],
                                    'line_start': child.lineno,
                                    'line_end': child.end_lineno if hasattr(child, 'end_lineno') else child.lineno
                                })
                        
                        classes.append({
                            'name': node.name,
                            'docstring': ast.get_docstring(node),
                            'methods': class_methods,
                            'line_start': node.lineno,
                            'line_end': node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                        })
            
            elif language in ['javascript', 'typescript']:
                # Simple regex-based extraction for JS/TS
                # This is a simplified approach; a proper parser would be better
                
                # Extract functions
                function_pattern = r'(async\s+)?function\s+(\w+)\s*\(([^)]*)\)'
                func_matches = re.finditer(function_pattern, code_content)
                
                for match in func_matches:
                    functions.append({
                        'name': match.group(2),
                        'args': [arg.strip() for arg in match.group(3).split(',') if arg.strip()],
                        'is_async': match.group(1) is not None
                    })
                
                # Extract arrow functions
                arrow_func_pattern = r'const\s+(\w+)\s*=\s*(async\s+)?\(([^)]*)\)\s*=>'
                arrow_matches = re.finditer(arrow_func_pattern, code_content)
                
                for match in arrow_matches:
                    functions.append({
                        'name': match.group(1),
                        'args': [arg.strip() for arg in match.group(3).split(',') if arg.strip()],
                        'is_async': match.group(2) is not None
                    })
                
                # Extract classes
                class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*{'
                class_matches = re.finditer(class_pattern, code_content)
                
                for match in class_matches:
                    classes.append({
                        'name': match.group(1),
                        'extends': match.group(2) if match.group(2) else None
                    })
        
        except Exception as e:
            logger.error(f"Error extracting code elements: {e}")
        
        return functions, classes
    
    def _create_test_prompt(
        self, 
        code_content: str, 
        file_path: str, 
        language: str, 
        functions: List[Dict[str, Any]], 
        classes: List[Dict[str, Any]]
    ) -> str:
        """
        Create a prompt for test generation.
        
        Args:
            code_content: Content of the code file
            file_path: Path to the code file
            language: Programming language of the code
            functions: List of functions in the code
            classes: List of classes in the code
            
        Returns:
            Prompt for test generation
        """
        # Create a summary of functions and classes
        function_summary = "\n".join([f"- {f['name']}({', '.join(f.get('args', []))})" for f in functions])
        class_summary = "\n".join([f"- {c['name']}" for c in classes])
        
        # Create test framework recommendations based on language
        test_framework = {
            'python': 'pytest or unittest',
            'javascript': 'Jest or Mocha',
            'typescript': 'Jest or Jasmine',
            'java': 'JUnit',
            'cpp': 'Google Test (gtest) or Catch2',
            'csharp': 'xUnit or NUnit',
            'go': 'testing package',
            'ruby': 'RSpec or Minitest',
            'php': 'PHPUnit',
            'rust': 'the built-in testing framework'
        }.get(language, 'a suitable testing framework')
        
        prompt = f"""You are a test-driven development expert. Your task is to create comprehensive tests for the following code.

                    File: {file_path}
                    Language: {language}

                    Here's the code to test:

                    ```{language}
                    {code_content}
                    ```

                    Functions in this code:
                    {function_summary if function_summary else "No functions extracted."}

                    Classes in this code:
                    {class_summary if class_summary else "No classes extracted."}

                    Please generate test code using {test_framework} that covers:
                    1. All public functions and methods with multiple test cases
                    2. Edge cases and error handling
                    3. Different input scenarios
                    4. Appropriate mocking of dependencies when necessary

                    Make the tests specific to this code, with actual function names and realistic inputs and expected outputs.
                    Include setup and teardown as appropriate. Structure the tests logically with clear descriptions.

                    Generated test code:
                    """
        
        return prompt
    
    def _create_documentation_prompt(
        self, 
        code_content: str, 
        file_path: str, 
        language: str, 
        functions: List[Dict[str, Any]], 
        classes: List[Dict[str, Any]]
    ) -> str:
        """
        Create a prompt for documentation generation.
        
        Args:
            code_content: Content of the code file
            file_path: Path to the code file
            language: Programming language of the code
            functions: List of functions in the code
            classes: List of classes in the code
            
        Returns:
            Prompt for documentation generation
        """
        # Determine documentation format based on language
        doc_format = {
            'python': 'Google style or NumPy style docstrings',
            'javascript': 'JSDoc',
            'typescript': 'TSDoc or JSDoc',
            'java': 'Javadoc',
            'cpp': 'Doxygen',
            'csharp': 'XML documentation comments',
            'go': 'godoc style comments',
            'ruby': 'YARD',
            'php': 'PHPDoc',
            'rust': 'rustdoc'
        }.get(language, 'appropriate documentation format')
        
        prompt = f"""You are a documentation expert. Your task is to create comprehensive documentation for the following code.

                    File: {file_path}
                    Language: {language}

                    Here's the code to document:

                    ```{language}
                    {code_content}
                    ```

                    Please generate detailed documentation in {doc_format} format for this code, including:

                    1. A file-level overview explaining the purpose and functionality
                    2. Documentation for each function and class, with:
                    - Description of purpose
                    - Parameters and return values with types
                    - Examples of usage where helpful
                    - Any exceptions or errors that might be thrown

                    Create the documentation in a format that could be directly inserted into the original code.
                    Be specific to this code, with accurate function names, parameter names, and descriptions.

                    Generated documentation:
                    """
        
        return prompt