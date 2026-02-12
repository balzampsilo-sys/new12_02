"""Centralized error handling for external calls and critical operations

This module provides:
- Retry logic with exponential backoff
- Structured error logging
- Error classification and recovery strategies
- Integration with Sentry for monitoring
"""

import asyncio
import functools
import logging
from enum import Enum
from typing import Any, Callable, Optional, Type, TypeVar

import aiosqlite
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from pydantic import ValidationError

try:
    import sentry_sdk

    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "low"  # Recoverable, logged only
    MEDIUM = "medium"  # Recoverable, logged + notified
    HIGH = "high"  # May need manual intervention
    CRITICAL = "critical"  # Requires immediate attention


class RetryableError(Exception):
    """Base class for errors that can be retried"""

    pass


class DatabaseError(RetryableError):
    """Database operation errors"""

    pass


class ValidationError(Exception):
    """Input validation errors (non-retryable)"""

    pass


class ExternalServiceError(RetryableError):
    """External service errors (Telegram API, etc)"""

    pass


# === ERROR CLASSIFICATION ===

RETRYABLE_DB_ERRORS = (aiosqlite.OperationalError, aiosqlite.DatabaseError)

RETRYABLE_TELEGRAM_ERRORS = (TelegramNetworkError, TelegramRetryAfter)

NON_RETRYABLE_TELEGRAM_ERRORS = (TelegramBadRequest, TelegramForbiddenError)


def classify_error(error: Exception) -> ErrorSeverity:
    """Classify error by severity

    Args:
        error: Exception to classify

    Returns:
        ErrorSeverity level
    """
    if isinstance(error, ValidationError):
        return ErrorSeverity.LOW

    if isinstance(error, (TelegramBadRequest, TelegramForbiddenError)):
        return ErrorSeverity.LOW

    if isinstance(error, (TelegramNetworkError, aiosqlite.OperationalError)):
        return ErrorSeverity.MEDIUM

    if isinstance(error, TelegramRetryAfter):
        return ErrorSeverity.MEDIUM

    if isinstance(error, aiosqlite.IntegrityError):
        return ErrorSeverity.HIGH

    # Unknown errors are critical
    return ErrorSeverity.CRITICAL


def should_retry(error: Exception) -> bool:
    """Determine if error is retryable

    Args:
        error: Exception to check

    Returns:
        True if should retry
    """
    if isinstance(error, NON_RETRYABLE_TELEGRAM_ERRORS):
        return False

    if isinstance(error, (RETRYABLE_DB_ERRORS, RETRYABLE_TELEGRAM_ERRORS)):
        return True

    if isinstance(error, RetryableError):
        return True

    return False


# === RETRY DECORATOR ===


def async_retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_error: Optional[Callable] = None,
):
    """Decorator for async functions with retry logic

    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for exponential backoff
        exceptions: Tuple of exception types to catch
        on_error: Optional callback called on each error

    Example:
        @async_retry_on_error(max_attempts=3, delay=1.0)
        async def fetch_data():
            # May fail transiently
            pass
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    severity = classify_error(e)

                    # Check if should retry
                    if not should_retry(e) or attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed permanently after {attempt} attempts: {e}",
                            exc_info=True,
                            extra={
                                "function": func.__name__,
                                "attempt": attempt,
                                "severity": severity.value,
                            },
                        )

                        # Send to Sentry for high/critical errors
                        if SENTRY_AVAILABLE and severity in (
                            ErrorSeverity.HIGH,
                            ErrorSeverity.CRITICAL,
                        ):
                            sentry_sdk.capture_exception(e)

                        # Call error callback if provided
                        if on_error:
                            await on_error(e, attempt)

                        raise

                    # Log retry attempt
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {current_delay:.1f}s...",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt,
                            "delay": current_delay,
                        },
                    )

                    # Wait before retry
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            # Should not reach here, but just in case
            raise last_exception

        return wrapper

    return decorator


# === CONTEXT MANAGERS ===


class safe_operation:
    """Context manager for safe operations with error handling

    Example:
        async with safe_operation("create_booking", user_id=123):
            await create_booking(...)
    """

    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context
        self.start_time = None

    async def __aenter__(self):
        import time

        self.start_time = time.time()
        logger.debug(f"Starting operation: {self.operation}", extra=self.context)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        import time

        duration = time.time() - self.start_time

        if exc_type is None:
            logger.debug(
                f"Operation completed: {self.operation} ({duration:.2f}s)",
                extra={**self.context, "duration": duration},
            )
            return True

        # Error occurred
        severity = classify_error(exc_val) if exc_val else ErrorSeverity.CRITICAL

        logger.error(
            f"Operation failed: {self.operation} ({duration:.2f}s): {exc_val}",
            exc_info=(exc_type, exc_val, exc_tb),
            extra={**self.context, "duration": duration, "severity": severity.value},
        )

        # Send to Sentry if critical
        if SENTRY_AVAILABLE and severity in (ErrorSeverity.HIGH, ErrorSeverity.CRITICAL):
            sentry_sdk.capture_exception(exc_val)

        # Don't suppress exception
        return False


# === TELEGRAM ERROR HANDLERS ===


async def handle_telegram_error(
    error: TelegramAPIError, context: dict[str, Any]
) -> Optional[str]:
    """Handle Telegram API errors with user-friendly messages

    Args:
        error: Telegram API error
        context: Additional context (user_id, action, etc)

    Returns:
        User-friendly error message or None
    """
    if isinstance(error, TelegramForbiddenError):
        logger.warning(
            f"Bot blocked by user: {context.get('user_id')}", extra=context
        )
        return None  # Silent fail - user blocked bot

    if isinstance(error, TelegramBadRequest):
        logger.warning(
            f"Bad request to Telegram API: {error.message}", extra=context
        )
        return "Произошла ошибка. Попробуйте позже."

    if isinstance(error, TelegramRetryAfter):
        retry_after = error.retry_after
        logger.warning(
            f"Rate limited by Telegram. Retry after {retry_after}s", extra=context
        )
        return f"Слишком много запросов. Попробуйте через {retry_after} сек."

    if isinstance(error, TelegramNetworkError):
        logger.error(f"Telegram network error: {error}", exc_info=True, extra=context)
        return "Проблемы с соединением. Попробуйте позже."

    # Unknown Telegram error
    logger.error(
        f"Unknown Telegram error: {error}", exc_info=True, extra=context
    )
    if SENTRY_AVAILABLE:
        sentry_sdk.capture_exception(error)
    return "Произошла ошибка. Попробуйте позже."


# === DATABASE ERROR HANDLERS ===


async def handle_database_error(error: Exception, context: dict[str, Any]) -> bool:
    """Handle database errors

    Args:
        error: Database error
        context: Additional context

    Returns:
        True if error was handled and operation can be retried
    """
    if isinstance(error, aiosqlite.IntegrityError):
        logger.warning(
            f"Database integrity error: {error.args[0] if error.args else 'unknown'}",
            extra=context,
        )
        return False  # Don't retry integrity errors

    if isinstance(error, aiosqlite.OperationalError):
        logger.error(
            f"Database operational error: {error}", exc_info=True, extra=context
        )
        return True  # Can retry

    if isinstance(error, aiosqlite.DatabaseError):
        logger.error(
            f"Database error: {error}", exc_info=True, extra=context
        )
        if SENTRY_AVAILABLE:
            sentry_sdk.capture_exception(error)
        return True  # Can retry

    # Unknown database error
    logger.critical(
        f"Unknown database error: {error}", exc_info=True, extra=context
    )
    if SENTRY_AVAILABLE:
        sentry_sdk.capture_exception(error)
    return False


# === VALIDATION ERROR HANDLERS ===


def format_validation_error(error: ValidationError) -> str:
    """Format Pydantic validation error to user-friendly message

    Args:
        error: Pydantic ValidationError

    Returns:
        User-friendly error message
    """
    errors = error.errors()
    if not errors:
        return "Неверные данные"

    # Get first error
    first_error = errors[0]
    field = " → ".join(str(loc) for loc in first_error["loc"])
    msg = first_error["msg"]

    return f"Ошибка в поле '{field}': {msg}"
