"""
M.B.S Studio - Logging Utilities
=================================

Comprehensive logging utilities for the podcast generator application.

Features:
    - Rich-formatted console output
    - Function call decorators for automatic logging
    - Performance timing utilities
    - Exception context helpers
    - Log file rotation

Author: M.B.S Studio
Version: 2.0.0
"""

from __future__ import annotations

import functools
import logging
import os
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from rich.console import Console
from rich.logging import RichHandler

# Type variable for generic function decorators
F = TypeVar("F", bound=Callable[..., Any])

# Global state
_LOGGER_CACHE: dict[str, logging.Logger] = {}
_CONSOLE = Console()
_FILE_HANDLER: Optional[logging.FileHandler] = None
_LOG_FILE_PATH: Optional[Path] = None

# Performance thresholds (in seconds)
SLOW_OPERATION_THRESHOLD = 5.0
VERY_SLOW_OPERATION_THRESHOLD = 30.0


def configure_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    format_string: Optional[str] = None,
) -> None:
    """
    Configure the logging system.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file
        format_string: Optional custom format string
    """
    global _FILE_HANDLER, _LOG_FILE_PATH
    
    handlers: list[logging.Handler] = [
        RichHandler(console=_CONSOLE, rich_tracebacks=True)
    ]
    
    # Add file handler if requested
    if log_file:
        _LOG_FILE_PATH = log_file
        log_file.parent.mkdir(parents=True, exist_ok=True)
        _FILE_HANDLER = logging.FileHandler(log_file, encoding="utf-8")
        _FILE_HANDLER.setFormatter(logging.Formatter(
            format_string or "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        handlers.append(_FILE_HANDLER)
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
        force=True,
    )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Return a module-level logger with Rich formatting.
    
    Args:
        name: Logger name (default: azure_podcast_generator)
        
    Returns:
        Configured logger instance
    """
    if not _LOGGER_CACHE:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        
        # Check for log file path in environment
        log_file_str = os.getenv("LOG_FILE")
        log_file = Path(log_file_str) if log_file_str else None
        
        configure_logging(level, log_file)
        
    key = name or "azure_podcast_generator"
    if key not in _LOGGER_CACHE:
        _LOGGER_CACHE[key] = logging.getLogger(key)
    return _LOGGER_CACHE[key]


def log_function_call(
    logger: Optional[logging.Logger] = None,
    log_args: bool = False,
    log_result: bool = False,
    time_threshold: float = SLOW_OPERATION_THRESHOLD,
) -> Callable[[F], F]:
    """
    Decorator that logs function entry, exit, and timing.
    
    Args:
        logger: Logger instance (uses function's module logger if None)
        log_args: Whether to log function arguments
        log_result: Whether to log return value
        time_threshold: Warn if execution exceeds this time (seconds)
        
    Returns:
        Decorated function
        
    Example:
        >>> @log_function_call(log_args=True)
        ... def process_file(path: str) -> bool:
        ...     return True
    """
    def decorator(func: F) -> F:
        func_logger = logger or get_logger(func.__module__)
        func_name = f"{func.__module__}.{func.__qualname__}"
        
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            
            # Log entry
            if log_args:
                args_str = _format_args(args, kwargs)
                func_logger.debug("[ENTER] %s(%s)", func_name, args_str)
            else:
                func_logger.debug("[ENTER] %s", func_name)
            
            try:
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                
                # Log exit with timing
                if log_result:
                    result_str = _format_value(result)
                    func_logger.debug("[EXIT] %s -> %s (%.3fs)", func_name, result_str, elapsed)
                else:
                    func_logger.debug("[EXIT] %s (%.3fs)", func_name, elapsed)
                
                # Warn on slow operations
                if elapsed > VERY_SLOW_OPERATION_THRESHOLD:
                    func_logger.warning("[SLOW] %s took %.1fs (very slow)", func_name, elapsed)
                elif elapsed > time_threshold:
                    func_logger.info("[SLOW] %s took %.1fs", func_name, elapsed)
                
                return result
                
            except Exception as e:
                elapsed = time.time() - start_time
                func_logger.error("[ERROR] %s failed after %.3fs: %s", func_name, elapsed, e)
                raise
        
        return cast(F, wrapper)
    return decorator


def log_exception_context(
    logger: logging.Logger,
    context: str,
    include_locals: bool = False,
) -> None:
    """
    Log detailed exception context for debugging.
    
    Args:
        logger: Logger instance
        context: Description of what was happening
        include_locals: Whether to include local variables (can be verbose)
    """
    exc_type, exc_value, exc_tb = sys.exc_info()
    
    if not exc_type:
        logger.warning("[log_exception_context] No exception to log")
        return
    
    # Format exception
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_str = "".join(tb_lines)
    
    logger.error(
        "[EXCEPTION] Context: %s\n"
        "Type: %s\n"
        "Message: %s\n"
        "Traceback:\n%s",
        context, exc_type.__name__, exc_value, tb_str
    )
    
    # Optionally log local variables from each frame
    if include_locals and exc_tb:
        logger.debug("[EXCEPTION] Local variables from frames:")
        frame = exc_tb.tb_frame
        while frame:
            logger.debug("  Frame %s in %s:", frame.f_code.co_name, frame.f_code.co_filename)
            for key, value in frame.f_locals.items():
                if not key.startswith("__"):
                    logger.debug("    %s = %s", key, _format_value(value))
            frame = frame.f_back


@contextmanager
def log_operation(
    logger: logging.Logger,
    operation_name: str,
    level: int = logging.INFO,
):
    """
    Context manager for logging operation start/end with timing.
    
    Args:
        logger: Logger instance
        operation_name: Name of the operation
        level: Logging level
        
    Example:
        >>> with log_operation(logger, "Loading project"):
        ...     load_project()
    """
    start_time = time.time()
    logger.log(level, "[START] %s", operation_name)
    
    try:
        yield
        elapsed = time.time() - start_time
        logger.log(level, "[DONE] %s (%.3fs)", operation_name, elapsed)
        
        if elapsed > VERY_SLOW_OPERATION_THRESHOLD:
            logger.warning("[SLOW] %s took %.1fs", operation_name, elapsed)
            
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("[FAILED] %s after %.3fs: %s", operation_name, elapsed, e)
        raise


class TimingContext:
    """
    Class for tracking operation timing with checkpoints.
    
    Example:
        >>> timing = TimingContext(logger, "Pipeline execution")
        >>> timing.checkpoint("Loaded metadata")
        >>> timing.checkpoint("Generated dialogue")
        >>> timing.finish()
    """
    
    def __init__(self, logger: logging.Logger, operation_name: str) -> None:
        self.logger = logger
        self.operation_name = operation_name
        self.start_time = time.time()
        self.last_checkpoint = self.start_time
        self.checkpoints: list[tuple[str, float, float]] = []
        
        self.logger.info("[TIMING] Started: %s", operation_name)
    
    def checkpoint(self, name: str) -> float:
        """Record a checkpoint and return time since last checkpoint."""
        now = time.time()
        since_last = now - self.last_checkpoint
        since_start = now - self.start_time
        
        self.checkpoints.append((name, since_start, since_last))
        self.last_checkpoint = now
        
        self.logger.debug("[TIMING] %s: %s (%.3fs since start, %.3fs since last)",
                         self.operation_name, name, since_start, since_last)
        
        return since_last
    
    def finish(self) -> Dict[str, float]:
        """
        Finish timing and return summary.
        
        Returns:
            Dict with total time and checkpoint times
        """
        total = time.time() - self.start_time
        
        self.logger.info("[TIMING] Finished: %s in %.3fs", self.operation_name, total)
        
        if self.checkpoints:
            self.logger.debug("[TIMING] Checkpoints:")
            for name, since_start, since_last in self.checkpoints:
                self.logger.debug("  - %s: %.3fs (delta: %.3fs)", name, since_start, since_last)
        
        return {
            "total": total,
            "checkpoints": {name: since_start for name, since_start, _ in self.checkpoints},
        }


def _format_args(args: tuple, kwargs: dict) -> str:
    """Format function arguments for logging."""
    parts = []
    for arg in args:
        parts.append(_format_value(arg))
    for key, value in kwargs.items():
        parts.append(f"{key}={_format_value(value)}")
    return ", ".join(parts)


def _format_value(value: Any, max_length: int = 100) -> str:
    """Format a value for logging with length limits."""
    if value is None:
        return "None"
    
    if isinstance(value, (str, bytes)):
        if len(value) > max_length:
            return f"'{value[:max_length]}...' ({len(value)} total)"
        return f"'{value}'"
    
    if isinstance(value, (list, tuple)):
        return f"[{len(value)} items]"
    
    if isinstance(value, dict):
        return f"{{{len(value)} keys}}"
    
    if isinstance(value, Path):
        return str(value)
    
    str_value = str(value)
    if len(str_value) > max_length:
        return f"{str_value[:max_length]}..."
    return str_value


def get_log_file_path() -> Optional[Path]:
    """Get the current log file path if file logging is enabled."""
    return _LOG_FILE_PATH


def create_session_log_file(base_dir: Path, prefix: str = "session") -> Path:
    """
    Create a new session log file with timestamp.
    
    Args:
        base_dir: Directory for log files
        prefix: Filename prefix
        
    Returns:
        Path to the new log file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = base_dir / f"{prefix}_{timestamp}.log"
    
    # Reconfigure logging with new file
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    configure_logging(level, log_file)
    
    return log_file

