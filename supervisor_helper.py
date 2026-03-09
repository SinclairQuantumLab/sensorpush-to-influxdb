import sys
import builtins
from datetime import datetime, timezone

def _timestamp():
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")

def print(*args, **kwargs):
    builtins.print(*args, flush=True, **kwargs)

def print_stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def _format_log_message(level, message):
    prefix = f"[{_timestamp()}] [{level}] "
    indent = " " * len(prefix)

    message = str(message)
    message = message.replace("\r\n", "\n").replace("\r", "\n")
    message = message.replace("\n", "\n" + indent)

    return prefix + message

def log_info(message, **kwargs):
    print(_format_log_message("INFO", message), **kwargs)

def log_warn(message, **kwargs):
    print_stderr(_format_log_message("WARN", message), **kwargs)

def log_error(message, **kwargs):
    print_stderr(_format_log_message("ERROR", message), **kwargs)