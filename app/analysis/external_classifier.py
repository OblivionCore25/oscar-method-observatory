PYTHON_BUILTINS = {
    'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted', 'reversed',
    'list', 'dict', 'set', 'tuple', 'str', 'int', 'float', 'bool', 'type', 'super', 
    'isinstance', 'issubclass', 'hasattr', 'getattr', 'setattr', 'delattr', 'repr', 
    'vars', 'iter', 'next', 'open', 'id', 'hash', 'min', 'max', 'sum', 'abs', 'round', 
    'pow', 'any', 'all', 'format', 'chr', 'ord', 'hex', 'oct', 'bin', 'input', 
    'property', 'classmethod', 'staticmethod', 'callable', 'dir', 'globals', 'locals',
    'NotImplementedError', 'TypeError', 'ValueError', 'KeyError', 'AttributeError', 
    'RuntimeError', 'ImportError', 'StopIteration', 'Exception', 'OSError', 'IOError', 
    'FileNotFoundError', 'AssertionError', 'IndexError', 'OverflowError', 
    'UnicodeError', 'MemoryError', 'RecursionError', 'TimeoutError', 'PermissionError',
}

PYTHON_STDLIB_PREFIXES = {
    'os', 'sys', 're', 'ast', 'json', 'pathlib', 'typing', 'collections', 'functools',
    'itertools', 'datetime', 'logging', 'unittest', 'abc', 'enum', 'dataclasses', 
    'io', 'warnings', 'copy', 'contextlib', 'threading', 'subprocess', 'tempfile', 
    'hashlib', 'base64', 'urllib', 'http', 'socket', 'email', 'html', 'xml', 'csv', 
    'sqlite3', 'pickle', 'struct', 'inspect', 'textwrap', 'string', 'shutil', 'glob', 
    'fnmatch', 'time', 'signal', 'math', 'random', 'secrets', 'uuid', 'weakref', 
    'traceback', 'pdb', 'pprint', 'importlib', 'pkgutil', 'codecs', 'operator', 
    'decimal', 'types', 'numbers', 'statistics', 'asyncio', 'multiprocessing', 'builtins'
}

PYTHON_PROTO_METHODS = {
    'append', 'extend', 'insert', 'pop', 'remove', 'clear', 'copy', 'update', 'get',
    'items', 'keys', 'values', 'setdefault', 'encode', 'decode', 'strip', 'lstrip', 
    'rstrip', 'split', 'rsplit', 'join', 'replace', 'find', 'rfind', 'index', 'count',
    'startswith', 'endswith', 'upper', 'lower', 'title', 'capitalize', 'format',
    'isalpha', 'isdigit', 'isalnum', 'isspace', 'add', 'discard', 'difference', 
    'intersection', 'union', 'symmetric_difference', 'read', 'write', 'close', 
    'seek', 'tell', 'flush', 'readline', 'readlines', 'writelines', 'send', 'recv', 
    'connect', 'listen', 'bind', 'accept', 'shutdown'
}

JS_BUILTINS_SET = {
    'console.log', 'console.error', 'console.warn', 'Array.isArray', 'Object.keys', 
    'Object.values', 'Object.entries', 'Object.assign', 'Object.create', 
    'Object.defineProperty', 'Object.getPrototypeOf', 'Object.getOwnPropertyNames', 
    'Object.setPrototypeOf', 'JSON.parse', 'JSON.stringify', 'parseInt', 'parseFloat',
    'String', 'Number', 'Boolean', 'Array', 'Object', 'Promise.resolve', 
    'Promise.reject', 'Promise.all', 'Buffer.from', 'Buffer.alloc', 'setTimeout', 
    'setInterval', 'clearTimeout', 'clearInterval', 'setImmediate', 
    'encodeURIComponent', 'decodeURIComponent', 'Error', 'TypeError', 'RangeError',
    'RegExp', 'Date', 'Map', 'Set', 'Symbol', 'require', 'process.env', 'process.exit', 
    'process.nextTick', 'isNaN', 'isFinite', 'Math.max', 'Math.min', 'Math.floor', 
    'Math.ceil', 'Math.round', 'Math.abs',
}

JS_BUILTIN_ROOTS = {
    'console', 'Math', 'JSON', 'Object', 'Array', 'Promise', 'Buffer', 'process',
    'Error', 'TypeError', 'RangeError', 'RegExp', 'Date', 'Map', 'Set', 'Symbol', 
    'Number', 'String', 'Boolean', 'Proxy', 'Reflect', 'WeakMap', 'WeakSet', 'Intl', 
    'globalThis', 'arguments'
}

JS_PROTO_METHODS = {
    'push', 'pop', 'shift', 'unshift', 'splice', 'slice', 'concat', 'join', 'indexOf', 
    'includes', 'find', 'filter', 'map', 'reduce', 'forEach', 'some', 'every', 'sort', 
    'reverse', 'flat', 'flatMap', 'keys', 'values', 'entries', 'toString', 'valueOf', 
    'hasOwnProperty', 'charAt', 'charCodeAt', 'split', 'replace', 'match', 'search', 
    'trim', 'startsWith', 'endsWith', 'toUpperCase', 'toLowerCase', 'substring', 
    'substr', 'then', 'catch', 'finally', 'resolve', 'reject', 'bind', 'call', 'apply',
    'emit', 'on', 'once', 'removeListener', 'addEventListener', 'removeEventListener',
    'write', 'end', 'pipe', 'read', 'close', 'destroy', 'get', 'set', 'has', 'delete',
}

NODE_MODULES = {
    'fs', 'path', 'http', 'https', 'net', 'stream', 'url', 'querystring', 'crypto',
    'os', 'child_process', 'cluster', 'events', 'util', 'assert', 'zlib', 'tls', 
    'dgram', 'dns'
}

def classify_call(target_name: str, ecosystem: str, project_dependencies: set[str] = None) -> str:
    """
    Classify a raw call target as 'INTERNAL' (part of the project, or at least
    project-specific) or 'EXTERNAL' (language built-in, standard library, or known 
    external primitive or dependency). 
    
    This classification is used to filter out language primitives from the 
    Resolution Rate denominator.
    """
    if not target_name:
        return "INTERNAL"
        
    project_dependencies = project_dependencies or set()
        
    root = target_name.split('.')[0] if '.' in target_name else target_name
    method_part = target_name.split('.')[-1] if '.' in target_name else target_name

    if ecosystem.lower() == "pypi":
        if target_name in PYTHON_BUILTINS or root in PYTHON_BUILTINS:
            return "EXTERNAL"
        if root in PYTHON_STDLIB_PREFIXES:
            return "EXTERNAL"
        if method_part in PYTHON_PROTO_METHODS:
            return "EXTERNAL"
        if root.lower() in project_dependencies or target_name.lower() in project_dependencies:
            return "EXTERNAL"
            
    elif ecosystem.lower() == "npm":
        if target_name in JS_BUILTINS_SET or root in JS_BUILTIN_ROOTS or target_name == "require":
            return "EXTERNAL"
        if root in NODE_MODULES:
            return "EXTERNAL"
        if method_part in JS_PROTO_METHODS:
            return "EXTERNAL"
        if root in project_dependencies or target_name in project_dependencies:
            return "EXTERNAL"
        
    return "INTERNAL"
