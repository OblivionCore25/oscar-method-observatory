import sys
import threading
from collections import defaultdict
from dataclasses import dataclass, field

@dataclass
class TraceRecord:
    caller_file: str
    caller_name: str
    callee_file: str
    callee_name: str
    count: int = 0

class RuntimeTracer:
    """
    Instruments Python execution via sys.settrace() to record actual method calls.
    Usage:
        tracer = RuntimeTracer(project_root="/path/to/project")
        tracer.start()
        # ... run tests or code here ...
        records = tracer.stop()
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self._call_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
        self._lock = threading.Lock()
        self._original_trace: object = None

    def start(self) -> None:
        """Starts OS-level python trace injections."""
        self._original_trace = sys.gettrace()
        sys.settrace(self._trace_calls)

    def stop(self) -> list[TraceRecord]:
        """Stops trace injections and maps records."""
        sys.settrace(self._original_trace)
        return self._build_records()

    def _trace_calls(self, frame, event, arg):
        if event != "call":
            return self._trace_calls

        filename = frame.f_code.co_filename
        # Only trace files within the project bounds to eliminate memory leaks and external bottlenecks
        if not filename.startswith(self.project_root):
            return None  # don't inject local lines

        func_name = frame.f_code.co_qualname  # Includes ClassName.method_name

        # Leverage the OS frame.f_back context for perfect stack depth resolution
        # This completely side-steps issues where raised exceptions bypass our manual tracking stack!
        caller_frame = frame.f_back
        with self._lock:
            if caller_frame:
                caller_file = caller_frame.f_code.co_filename
                caller_name = caller_frame.f_code.co_qualname
                self._call_counts[(caller_file, caller_name, filename, func_name)] += 1

        return self._trace_calls

    def _build_records(self) -> list[TraceRecord]:
        return [
            TraceRecord(cf, cn, tf, tn, count)
            for (cf, cn, tf, tn), count in self._call_counts.items()
        ]
