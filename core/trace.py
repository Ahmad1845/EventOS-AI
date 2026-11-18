"""Trace recorder and formatter with truthful token accounting per Section 10."""

from typing import Any, Dict, List, Optional


class Trace:
    def __init__(self, run_number: int, mode: str, filename: str, num_messages: int) -> None:
        self.run_number = run_number
        self.mode = mode
        self.filename = filename
        self.num_messages = num_messages
        self.entries: List[Dict[str, Any]] = []
        self.model_calls: List[Dict[str, Any]] = []
        self.python_events: List[Dict[str, str]] = []
        self.total_tokens: int = 0

    def record_model_call(
        self,
        n: int,
        model: str,
        tag: str,
        input_text: str,
        output_text: str,
        input_tokens: Optional[int],
        output_tokens: Optional[int],
        total_tokens: Optional[int],
    ) -> None:
        reported = (
            input_tokens is not None
            and output_tokens is not None
            and total_tokens is not None
        )
        if reported and total_tokens is not None:
            self.total_tokens += int(total_tokens)

        call_obj = {
            "kind": "model_call",
            "n": n,
            "model": model,
            "area": tag,
            "input": input_text,
            "output": output_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "reported": reported,
        }
        self.entries.append(call_obj)
        self.model_calls.append(call_obj)

    def python_event(self, kind: str, text: str) -> None:
        evt = {"kind": "python", "stage": kind, "text": text}
        self.entries.append(evt)
        self.python_events.append(evt)

    def format_run_trace(self) -> str:
        lines: List[str] = []
        header = (
            f"=== RUN {self.run_number} ({self.mode}) | "
            f"file: {self.filename} | {self.num_messages} messages ==="
        )
        lines.append(header)

        for entry in self.entries:
            if entry["kind"] == "model_call":
                lines.append(f"MODEL CALL {entry['n']}")
                lines.append(f"  model: {entry['model']}")
                lines.append(f"  area: {entry['area']}")
                lines.append(f"  input: {entry['input']}")
                lines.append(f"  output: {entry['output']}")
                if entry["reported"]:
                    lines.append(
                        f"  tokens: input={entry['input_tokens']} "
                        f"output={entry['output_tokens']} "
                        f"total={entry['total_tokens']}"
                    )
                else:
                    lines.append("  tokens: not reported")
            else:
                stage = entry["stage"].ljust(9)
                lines.append(f"PYTHON | {stage} | {entry['text']}")

        lines.append(f"TOTAL TOKENS: {self.total_tokens}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_number": self.run_number,
            "mode": self.mode,
            "filename": self.filename,
            "num_messages": self.num_messages,
            "entries": self.entries,
            "model_calls": self.model_calls,
            "python_events": self.python_events,
            "total_tokens": self.total_tokens,
        }
