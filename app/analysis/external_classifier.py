from __future__ import annotations
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
    # Phase 2 additions: missing builtins and common types
    'frozenset', 'compile', 'eval', 'exec', '__import__', 'object', 'bytes', 'bytearray',
    'memoryview', 'complex', 'slice', 'Ellipsis', 'NotImplemented', 'breakpoint',
    'SystemExit', 'GeneratorExit', 'KeyboardInterrupt', 'BaseException',
    'LookupError', 'ArithmeticError', 'SyntaxError', 'NameError', 'EOFError',
    'UnicodeDecodeError', 'UnicodeEncodeError', 'BufferError', 'ProcessLookupError',
    'ConnectionError', 'ConnectionResetError', 'ConnectionRefusedError',
    'DeprecationWarning', 'FutureWarning', 'UserWarning',
    'ContextVar',  # contextvars stdlib type used as bare name
    # Common stdlib types imported and used as bare names
    'defaultdict', 'OrderedDict', 'Counter', 'deque', 'namedtuple',  # collections
    'chain', 'product', 'combinations', 'permutations', 'groupby',   # itertools
    'partial', 'wraps', 'reduce', 'lru_cache', 'cached_property',    # functools
    'timedelta', 'date', 'time', 'timezone',                         # datetime
    'Path', 'PurePath', 'PurePosixPath',                             # pathlib
    'contextmanager', 'suppress', 'ExitStack',                       # contextlib
    'update_wrapper',                                                 # functools
    'itemgetter', 'attrgetter', 'methodcaller',                      # operator
    'Namespace',  # argparse/signal Namespace
    'LocalProxy',  # werkzeug/local proxy — always external
    'TemplateNotFound', 'TemplatesNotFound',  # jinja2
    'URLSafeTimedSerializer', 'URLSafeSerializer',  # itsdangerous
    'ImmutableDict', 'ImmutableMultiDict',  # werkzeug
    'BadRequest', 'NotFound', 'InternalServerError', 'Forbidden',  # werkzeug exceptions
    'MethodNotAllowed', 'Unauthorized', 'ServiceUnavailable',
    'Completer',  # readline
    'iscoroutinefunction', 'ensure_future',  # asyncio/inspect
    'import_string',  # werkzeug.utils
    'is_running_from_reloader', 'run_simple',  # werkzeug.serving
    'urlsplit', 'urljoin', 'urlparse', 'quote', 'unquote',  # urllib.parse
    'http_date', 'parse_date',  # werkzeug/http utils
    'b64encode', 'b64decode',  # base64
    'FileSystemLoader', 'BaseEnvironment',  # jinja2
    'Markup', 'escape',  # markupsafe
    'UUID',  # uuid
    '_url_quote',  # werkzeug
    'asgiref_async_to_sync',  # asgiref
}

PYTHON_STDLIB_PREFIXES = {
    'os', 'sys', 're', 'ast', 'json', 'pathlib', 'typing', 'collections', 'functools',
    'itertools', 'datetime', 'logging', 'unittest', 'abc', 'enum', 'dataclasses', 
    'io', 'warnings', 'copy', 'contextlib', 'threading', 'subprocess', 'tempfile', 
    'hashlib', 'base64', 'urllib', 'http', 'socket', 'email', 'html', 'xml', 'csv', 
    'sqlite3', 'pickle', 'struct', 'inspect', 'textwrap', 'string', 'shutil', 'glob', 
    'fnmatch', 'time', 'signal', 'math', 'random', 'secrets', 'uuid', 'weakref', 
    'traceback', 'pdb', 'pprint', 'importlib', 'pkgutil', 'codecs', 'operator', 
    'decimal', 'types', 'numbers', 'statistics', 'asyncio', 'multiprocessing', 'builtins',
    # Phase 2 additions: extended stdlib coverage
    'platform', 'readline', 'code', 'ssl', 'certifi', 'packaging', 'metadata',
    'contextvars', 'configparser', 'argparse', 'getpass', 'fileinput', 'difflib',
    'zipfile', 'tarfile', 'gzip', 'bz2', 'lzma', 'zlib', 'binascii',
    'distutils', 'sysconfig', 'site', 'compileall', 'dis', 'token', 'tokenize',
    'concurrent', 'queue', 'sched', 'select', 'selectors', 'mmap', 'ctypes',
    'array', 'bisect', 'heapq', 'plistlib', 'shelve', 'dbm',
    'atexit', 'gc', 'resource', 'locale',
}

PYTHON_PROTO_METHODS = {
    'append', 'extend', 'insert', 'pop', 'remove', 'clear', 'copy', 'update', 'get',
    'items', 'keys', 'values', 'setdefault', 'encode', 'decode', 'strip', 'lstrip', 
    'rstrip', 'split', 'rsplit', 'join', 'replace', 'find', 'rfind', 'index', 'count',
    'startswith', 'endswith', 'upper', 'lower', 'title', 'capitalize', 'format',
    'isalpha', 'isdigit', 'isalnum', 'isspace', 'add', 'discard', 'difference', 
    'intersection', 'union', 'symmetric_difference', 'read', 'write', 'close', 
    'seek', 'tell', 'flush', 'readline', 'readlines', 'writelines', 'send', 'recv', 
    'connect', 'listen', 'bind', 'accept', 'shutdown',
    # Phase 2 additions: string/collection methods used on variables
    'isupper', 'islower', 'removeprefix', 'removesuffix', 'partition', 'rpartition',
    'zfill', 'ljust', 'rjust', 'center', 'expandtabs', 'maketrans', 'translate',
    'sort', 'reverse',
    # Object protocol / attribute access methods 
    'total_seconds', 'loads', 'dumps',
    'getEffectiveLevel', 'setLevel', 'addHandler', 'setFormatter',
    'set_cookie', 'delete_cookie',
    'get_or_select_template', 'from_string', 'get_template',
    'match', 'allowed_methods',
    'format_message',
    'ensure_object', 'with_resource', 'get_parameter_source',
    'handle_parse_result',
    '_get_current_object',
    'with_traceback', 'is_relative_to', '__html__', 'force_type',
    'open_session', 'save_session',
    'iter_rules', 'bind_to_environ', 'build',
    'enter_context', 'get_filename', 'add_url_rule',
    'getlist',
}

# Typing module aliases — Python code often uses `import typing as t`
PYTHON_TYPING_ATTRS = {
    'TypeVar', 'cast', 'Optional', 'Union', 'Any', 'overload', 'ClassVar',
    'Final', 'Literal', 'Generic', 'Protocol', 'runtime_checkable',
    'TypedDict', 'NamedTuple', 'Callable', 'Iterator', 'Generator',
    'Sequence', 'Mapping', 'MutableMapping', 'Set', 'FrozenSet',
    'List', 'Dict', 'Tuple', 'Type', 'IO', 'TextIO', 'BinaryIO',
    'Pattern', 'Match', 'AnyStr', 'NoReturn', 'Never',
    'Awaitable', 'Coroutine', 'AsyncIterator', 'AsyncGenerator',
    'get_type_hints', 'TYPE_CHECKING', 'ParamSpec', 'Concatenate',
    'TypeAlias', 'TypeGuard', 'Self', 'Unpack',
}

JS_BUILTINS_SET = {
    'console.log', 'console.error', 'console.warn', 'Array.isArray', 'Object.keys', 
    'Object.values', 'Object.entries', 'Object.assign', 'Object.create', 
    'Object.defineProperty', 'Object.getPrototypeOf', 'Object.getOwnPropertyNames', 
    'Object.setPrototypeOf', 'JSON.parse', 'JSON.stringify', 'parseInt', 'parseFloat',
    'String', 'Number', 'Boolean', 'Array', 'Object', 'Promise.resolve', 
    'Promise.reject', 'Promise.all', 'Buffer.from', 'Buffer.alloc', 'setTimeout', 
    'setInterval', 'clearTimeout', 'clearInterval', 'setImmediate', 
    'encodeURIComponent', 'decodeURIComponent', 'encodeURI', 'decodeURI',
    'Error', 'TypeError', 'RangeError', 'SyntaxError', 'ReferenceError',
    'RegExp', 'Date', 'Map', 'Set', 'Symbol', 'require', 'process.env', 'process.exit', 
    'process.nextTick', 'isNaN', 'isFinite', 'Math.max', 'Math.min', 'Math.floor', 
    'Math.ceil', 'Math.round', 'Math.abs', 'ArrayBuffer.isView',
}

JS_BUILTIN_ROOTS = {
    'console', 'Math', 'JSON', 'Object', 'Array', 'Promise', 'Buffer', 'process',
    'Error', 'TypeError', 'RangeError', 'RegExp', 'Date', 'Map', 'Set', 'Symbol', 
    'Number', 'String', 'Boolean', 'Proxy', 'Reflect', 'WeakMap', 'WeakSet', 'Intl', 
    'globalThis', 'arguments', 'ArrayBuffer', 'DataView', 'Uint8Array',
    'Float32Array', 'Float64Array', 'Int32Array',
}

JS_PROTO_METHODS = {
    'push', 'pop', 'shift', 'unshift', 'splice', 'slice', 'concat', 'join', 'indexOf', 
    'includes', 'find', 'filter', 'map', 'reduce', 'forEach', 'some', 'every', 'sort', 
    'reverse', 'flat', 'flatMap', 'keys', 'values', 'entries', 'toString', 'valueOf', 
    'hasOwnProperty', 'charAt', 'charCodeAt', 'split', 'replace', 'match', 'search', 
    'trim', 'trimRight', 'trimLeft', 'trimStart', 'trimEnd',
    'startsWith', 'endsWith', 'toUpperCase', 'toLowerCase', 'substring', 'padStart', 'padEnd',
    'substr', 'then', 'catch', 'finally', 'resolve', 'reject', 'bind', 'call', 'apply',
    'emit', 'on', 'once', 'removeListener', 'addEventListener', 'removeEventListener',
    'write', 'end', 'pipe', 'read', 'close', 'destroy', 'get', 'set', 'has', 'delete',
    'lastIndexOf', 'at', 'fill', 'copyWithin', 'findIndex', 'from', 'of',
}

NODE_MODULES = {
    'fs', 'path', 'http', 'https', 'net', 'stream', 'url', 'querystring', 'crypto',
    'os', 'child_process', 'cluster', 'events', 'util', 'assert', 'zlib', 'tls', 
    'dgram', 'dns', 'readline', 'repl', 'vm', 'v8', 'perf_hooks', 'worker_threads',
    'string_decoder', 'punycode', 'domain', 'timers',
}

# Known dynamic dispatch patterns — calls via variable names, not static identifiers.
# These are provably unresolvable by static analysis.
DYNAMIC_CALL_PATTERNS = {
    'callback', 'func', 'cls', 'handler', 'wrapped', 'wrapped_view',
    'indirect', 'generator_or_function', 'app_factory', 'attr', 'type_func',
    'super_convert', 'decorator', 'interactive_hook', 'request_close',
    'next', 'done', 'resolve', 'reject', 'cb', 'fn', 'handle', 'listener',
    'processor', 'trust', 'etagFn',
    # Class attribute dispatch: self.session_class(), self.response_class(), etc.
    'session_class', 'response_class', 'null_session_class', 'path_type',
    'split_envvar_value', 'view_class', 'self_ref', 'url_func',
    'get_converter',
    'json_provider_class', 'url_map_class', 'config_class', 'aborter_class',
    'url_rule_class', 'jinja_environment', 'app_ctx_globals_class',
    'session_interface', 'tag_class', 'tag',
    'create_app', 'deferred', 'f',
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
        # Typing alias: `import typing as t` → t.TypeVar, t.cast, etc.
        if root == 't' and method_part in PYTHON_TYPING_ATTRS:
            return "EXTERNAL"
        # Framework internal aliases: _signals.*, _wz_*, _cv_*
        if root.startswith('_wz_') or root.startswith('_signals') or root.startswith('_cv_'):
            return "EXTERNAL"
        # Dunder methods used as bare calls (__init__, __getitem__, etc.)
        if target_name.startswith('__') and target_name.endswith('__'):
            return "EXTERNAL"
        if method_part.startswith('__') and method_part.endswith('__'):
            return "EXTERNAL"
        # Logger/handler method calls on logging objects
        if root in ('logger', 'log', 'default_handler'):
            return "EXTERNAL"
        # Chained logger calls: app.logger.info, self.logger.error, etc.
        if '.logger.' in target_name:
            return "EXTERNAL"
        # dotenv calls not caught by dependency manifest
        if root == 'dotenv':
            return "EXTERNAL"
        # Variable method calls that are clearly on external/stdlib objects
        # e.g., ctx.ensure_object, builder.get_request, response.set_cookie
        if root in ('ctx', 'request_ctx', 'app_ctx', 'builder', 'response', 's', 'e',
                     'session_interface', 'current_app', 'ep', 'loader', 'state',
                     'blueprint', 'url_adapter', 'request', 'resp',
                     'o', 'value', 'package_path', 'tag'):
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
        # require('...') calls
        if target_name.startswith("require("):
            return "EXTERNAL"
        # Node HTTP response/request methods (this.setHeader, res.setHeader, etc.)
        if method_part in ('setHeader', 'removeHeader', 'getHeader', 'writeHead',
                           'statusCode', 'statusMessage', 'end', 'write',
                          'isFile', 'isDirectory'):
            return "EXTERNAL"
        # Node path module functions used as aliases
        if target_name in ('extname', 'basename', 'dirname', 'resolve', 'join',
                           'isAbsolute', 'normalize', 'relative', 'parse',
                           'pathIsAbsolute', 'isIP'):
            return "EXTERNAL"
        # Common npm require() aliases — variable names assigned from require('dep')
        NPM_REQUIRE_ALIASES = {
            'contentDisposition', 'contentType', 'deprecate', 'encodeUrl',
            'escapeHtml', 'proxyaddr', 'queryparse', 'typeis', 'onFinished',
            'createError', 'parseRange', 'normalizeType', 'normalizeTypes',
            'setCharset', 'compileTrust', 'compileETag', 'compileQueryParser',
            'mixin', 'sign', 'accepts', 'fresh', 'vary', 'statuses',
            'merge', 'flatten', 'debug',
        }
        if target_name in NPM_REQUIRE_ALIASES or root in NPM_REQUIRE_ALIASES:
            return "EXTERNAL"
        # this.* on known framework base objects (router, app, parent)
        if root == 'this' and method_part in ('type', 'enabled', 'disabled',
                                               'route', 'param', 'handle',
                                               'path', 'parent'):
            return "EXTERNAL"
        # obj.method patterns on external objects  
        if root in ('obj', 'stat', 'res', 'req'):
            return "EXTERNAL"
        if root in project_dependencies or target_name in project_dependencies:
            return "EXTERNAL"
        
    return "INTERNAL"


def is_dynamic_call(call_name: str, expr_type: str) -> bool:
    """
    Determine if a call is dynamically dispatched (runtime variable as callable).
    These calls are provably unresolvable by static analysis.
    """
    if expr_type == "other":
        return True
    base = call_name.split('.')[-1] if '.' in call_name else call_name
    return base in DYNAMIC_CALL_PATTERNS
