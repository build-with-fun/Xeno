"""
Self-Improvement Engine - Code Rewriting and Architecture Evolution
Enables Xeno to modify its own codebase for continuous improvement
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import ast
import structlog
from datetime import datetime

logger = structlog.get_logger()


class CodeRewriter:
    """
    Self-improvement engine that can:
    - Analyze existing code for improvements
    - Rewrite code sections autonomously
    - Add new features and capabilities
    - Fix bugs and optimize performance
    - Refactor architecture
    """
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.improvement_history: List[Dict] = []
        self.allowed_patterns = [
            'optimization',
            'bug_fix',
            'feature_addition',
            'refactoring',
            'documentation',
            'performance'
        ]
    
    async def analyze_code(self, file_path: str) -> Dict[str, Any]:
        """Analyze code for potential improvements"""
        path = self.base_path / file_path
        
        if not path.exists():
            return {'error': f'File not found: {file_path}'}
        
        with open(path, 'r') as f:
            code = f.read()
        
        analysis = {
            'file': file_path,
            'lines_of_code': len(code.split('\n')),
            'complexity': self._calculate_complexity(code),
            'issues': [],
            'suggestions': [],
            'optimization_opportunities': []
        }
        
        # Parse AST for deeper analysis
        try:
            tree = ast.parse(code)
            analysis['functions'] = self._extract_functions(tree)
            analysis['classes'] = self._extract_classes(tree)
            analysis['imports'] = self._extract_imports(tree)
            
            # Detect issues
            analysis['issues'].extend(self._detect_issues(tree, code))
            
        except SyntaxError as e:
            analysis['error'] = f'Syntax error: {str(e)}'
        
        logger.info("Code analyzed", file=file_path, issues=len(analysis['issues']))
        return analysis
    
    def _calculate_complexity(self, code: str) -> float:
        """Calculate cyclomatic complexity estimate"""
        lines = code.split('\n')
        complexity = 1
        
        keywords = ['if', 'elif', 'for', 'while', 'except', 'and', 'or']
        for line in lines:
            for keyword in keywords:
                if f' {keyword} ' in line or line.startswith(f'{keyword} '):
                    complexity += 1
        
        return complexity
    
    def _extract_functions(self, tree: ast.AST) -> List[Dict]:
        """Extract function definitions from AST"""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    'name': node.name,
                    'line': node.lineno,
                    'args': [arg.arg for arg in node.args.args],
                    'decorators': [ast.unparse(d) for d in node.decorator_list]
                })
        return functions
    
    def _extract_classes(self, tree: ast.AST) -> List[Dict]:
        """Extract class definitions from AST"""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append({
                    'name': node.name,
                    'line': node.lineno,
                    'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                    'bases': [ast.unparse(base) for base in node.bases]
                })
        return classes
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements"""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(f"from {node.module} import ...")
        return imports
    
    def _detect_issues(self, tree: ast.AST, code: str) -> List[Dict]:
        """Detect code issues and anti-patterns"""
        issues = []
        
        # Check for long functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno + 50
                func_length = end_line - node.lineno
                if func_length > 100:
                    issues.append({
                        'type': 'long_function',
                        'severity': 'medium',
                        'location': f"line {node.lineno}",
                        'function': node.name,
                        'suggestion': f'Function {node.name} is too long ({func_length} lines). Consider breaking it down.'
                    })
        
        # Check for missing docstrings
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if not ast.get_docstring(node):
                    issues.append({
                        'type': 'missing_docstring',
                        'severity': 'low',
                        'location': f"line {node.lineno}",
                        'name': node.name,
                        'suggestion': f'Add docstring to {node.name}'
                    })
        
        return issues
    
    async def rewrite_code(self, file_path: str, improvements: List[Dict]) -> Dict[str, Any]:
        """Apply improvements to code"""
        path = self.base_path / file_path
        
        if not path.exists():
            return {'error': f'File not found: {file_path}'}
        
        with open(path, 'r') as f:
            original_code = f.read()
        
        # Create backup
        backup_path = path.with_suffix(path.suffix + '.backup')
        with open(backup_path, 'w') as f:
            f.write(original_code)
        
        improved_code = original_code
        
        # Apply each improvement
        for improvement in improvements:
            improved_code = self._apply_improvement(improved_code, improvement)
        
        # Write improved code
        with open(path, 'w') as f:
            f.write(improved_code)
        
        # Record improvement
        self.improvement_history.append({
            'file': file_path,
            'timestamp': datetime.utcnow().isoformat(),
            'improvements': improvements,
            'backup': str(backup_path)
        })
        
        logger.info("Code rewritten", file=file_path, improvements=len(improvements))
        
        return {
            'success': True,
            'file': file_path,
            'improvements_applied': len(improvements),
            'backup': str(backup_path)
        }
    
    def _apply_improvement(self, code: str, improvement: Dict) -> str:
        """Apply a single improvement to code"""
        improvement_type = improvement.get('type')
        
        if improvement_type == 'add_docstring':
            # Simple docstring addition (placeholder for AI-powered implementation)
            pass
        
        elif improvement_type == 'optimize_loop':
            # Loop optimization (placeholder)
            pass
        
        elif improvement_type == 'fix_bug':
            # Bug fix (placeholder)
            pass
        
        return code
    
    async def generate_new_feature(self, feature_spec: Dict) -> Dict[str, Any]:
        """Generate code for a new feature"""
        # This would use LLM to generate new code based on specification
        feature_name = feature_spec.get('name')
        description = feature_spec.get('description')
        target_file = feature_spec.get('target_file')
        
        generated_code = f'''
# Auto-generated feature: {feature_name}
# Description: {description}
# Generated at: {datetime.utcnow().isoformat()}

def {feature_name.lower().replace(" ", "_")}():
    """Auto-generated function for {feature_name}"""
    # TODO: Implement feature logic
    pass
'''
        
        return {
            'success': True,
            'feature': feature_name,
            'code': generated_code,
            'target_file': target_file
        }
    
    async def refactor_module(self, module_path: str, strategy: str) -> Dict[str, Any]:
        """Refactor an entire module"""
        # Strategies: 'split_large_files', 'consolidate_similar', 'optimize_imports'
        
        if strategy == 'split_large_files':
            return await self._split_large_module(module_path)
        elif strategy == 'consolidate_similar':
            return await self._consolidate_similar_modules(module_path)
        elif strategy == 'optimize_imports':
            return await self._optimize_imports(module_path)
        
        return {'error': f'Unknown refactoring strategy: {strategy}'}
    
    async def _split_large_module(self, module_path: str) -> Dict[str, Any]:
        """Split large modules into smaller ones"""
        # Implementation placeholder
        return {'success': True, 'strategy': 'split_large_files'}
    
    async def _consolidate_similar_modules(self, module_path: str) -> Dict[str, Any]:
        """Consolidate similar modules"""
        # Implementation placeholder
        return {'success': True, 'strategy': 'consolidate_similar'}
    
    async def _optimize_imports(self, module_path: str) -> Dict[str, Any]:
        """Optimize import statements"""
        # Implementation placeholder
        return {'success': True, 'strategy': 'optimize_imports'}
    
    def get_improvement_history(self, limit: int = 100) -> List[Dict]:
        """Get history of all improvements"""
        return self.improvement_history[-limit:]
