"""Static source scopes and exact task-clause cues; never import project code."""
import ast
import hashlib
import re


def source_context(source, start, end):
    """Self-contained so this exact implementation can run in isolated Python."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as error:
        return {'parse_error': type(error).__name__, 'scopes': []}
    functions = []
    def walk(node, parents):
        for child in ast.iter_child_nodes(node):
            scoped = isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.lineno <= end and child.end_lineno >= start:
                    functions.append((child, parents))
            walk(child, parents + [child] if scoped else parents)
    walk(tree, [])
    # Prefer the innermost function containing the requested start, then nearby definitions.
    functions.sort(key=lambda pair: (not (pair[0].lineno <= start <= pair[0].end_lineno),
                                     pair[0].end_lineno - pair[0].lineno if pair[0].lineno <= start <= pair[0].end_lineno else pair[0].lineno))
    scopes = []
    for node, parents in functions[:2]:
        signature = ('async def ' if isinstance(node, ast.AsyncFunctionDef) else 'def ') + node.name + '(' + ast.unparse(node.args) + ')'
        if node.returns:
            signature += ' -> ' + ast.unparse(node.returns)
        signature += ':'
        item = {'qualified_name': '.'.join([p.name for p in parents] + [node.name]),
                'start': node.lineno, 'end': node.end_lineno,
                'signature': signature if len(signature) <= 1200 else None,
                'signature_omitted': len(signature) > 1200,
                'parameters': [a.arg for a in node.args.posonlyargs + node.args.args + node.args.kwonlyargs]
                              + ([node.args.vararg.arg] if node.args.vararg else [])
                              + ([node.args.kwarg.arg] if node.args.kwarg else [])}
        enclosing = next((p for p in reversed(parents) if isinstance(p, ast.ClassDef)), None)
        if enclosing is not None:
            item['class_name'] = enclosing.name
            item['class_bases'] = [ast.unparse(base)[:160] for base in enclosing.bases[:4]]
        scopes.append(item)
    return {'parse_error': None, 'scopes': scopes}


def task_cues(instruction):
    """Exact sentences already present in the original task, not inferred requirements."""
    cues = []
    for match in re.finditer(r'[^.!?]+[.!?]?', instruction):
        sentence = match.group().strip()
        if re.search(r'\b(preserve|must|should|subclass|without|avoid|do not)\b', sentence, re.I):
            if len(sentence) <= 380:
                start = instruction.find(sentence, match.start())
                cues.append({'text': sentence, 'start': start, 'end': start + len(sentence)})
    return {'task_sha256': hashlib.sha256(instruction.encode()).hexdigest(), 'clauses': cues[:6]}
