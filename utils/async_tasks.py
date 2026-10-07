"""
utils/async_tasks.py
Unified asynchronous task executor and background worker utilities for
Pawnshop Management System.

Provides non-blocking execution for:
- Email notification dispatch (customer receipts, demand notices, admin alerts)
- PDF rendering and pre-caching (loan agreements, vouchers, payment receipts)
- Database connection lifecycle management in background worker threads
"""

import os
import sys
import logging
import hashlib
import functools
from concurrent.futures import ThreadPoolExecutor
from django.db import close_old_connections, connection
from django.conf import settings

logger = logging.getLogger(__name__)

# Global thread pool executor with daemon worker threads
_MAX_WORKERS = getattr(settings, 'ASYNC_TASK_MAX_WORKERS', 6)
_TASK_EXECUTOR = ThreadPoolExecutor(
    max_workers=_MAX_WORKERS,
    thread_name_prefix="PawnshopAsyncWorker"
)

# In-memory LRU cache for PDF bytes
_PDF_MEM_CACHE = {}
_MAX_PDF_CACHE_ITEMS = 128


def run_in_background(func, *args, **kwargs):
    """
    Submits a callable to run asynchronously in a managed background thread.
    Safely handles Django database connections before and after execution.
    """
    def _wrapper():
        close_old_connections()
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            logger.error(
                "[AsyncWorker] Background task failed: %s with args=%s kwargs=%s error: %s",
                getattr(func, '__name__', str(func)), args, kwargs, exc,
                exc_info=True
            )
        finally:
            close_old_connections()

    future = _TASK_EXECUTOR.submit(_wrapper)
    return future


def async_task(func):
    """
    Decorator to execute any function asynchronously in the background.
    """
    @functools.wraps(func)
    def _inner(*args, **kwargs):
        return run_in_background(func, *args, **kwargs)
    return _inner


def async_send_mail(email_message_or_func, *args, **kwargs):
    """
    Asynchronously sends an EmailMessage / EmailMultiAlternatives instance
    or executes an email-sending function in a background worker thread.
    """
    if hasattr(email_message_or_func, 'send'):
        # Direct EmailMessage instance
        def _send():
            try:
                sent = email_message_or_func.send(fail_silently=False)
                if sent:
                    logger.info("[AsyncMail] Email successfully sent to %s", getattr(email_message_or_func, 'to', 'recipients'))
                else:
                    logger.warning("[AsyncMail] Email dispatch returned 0 sent messages for %s", getattr(email_message_or_func, 'to', 'recipients'))
            except Exception as e:
                logger.error("[AsyncMail] Error sending email to %s: %s", getattr(email_message_or_func, 'to', 'recipients'), e, exc_info=True)

        return run_in_background(_send)
    elif callable(email_message_or_func):
        return run_in_background(email_message_or_func, *args, **kwargs)


def compute_html_hash(html_content, extra_key=''):
    """Generate SHA256 hex digest for HTML string and parameters."""
    hasher = hashlib.sha256()
    hasher.update(str(extra_key).encode('utf-8'))
    hasher.update(html_content.encode('utf-8'))
    return hasher.hexdigest()


def get_cached_pdf_bytes(cache_key):
    """Retrieve pre-rendered PDF bytes from memory cache if present."""
    return _PDF_MEM_CACHE.get(cache_key)


def set_cached_pdf_bytes(cache_key, pdf_bytes):
    """Store rendered PDF bytes in cache with LRU eviction."""
    global _PDF_MEM_CACHE
    if not pdf_bytes or len(pdf_bytes) < 500:
        return
    if len(_PDF_MEM_CACHE) >= _MAX_PDF_CACHE_ITEMS:
        # Evict oldest entry
        try:
            oldest_key = next(iter(_PDF_MEM_CACHE))
            del _PDF_MEM_CACHE[oldest_key]
        except Exception:
            _PDF_MEM_CACHE.clear()
    _PDF_MEM_CACHE[cache_key] = pdf_bytes


def async_render_loan_pdf(loan_id, current_language='en'):
    """
    Asynchronously pre-renders and caches a loan agreement PDF in the background
    so that user document download / preview requests are instantaneous.
    """
    def _render():
        try:
            from transactions.models import Loan
            loan = Loan.objects.select_related('customer', 'branch', 'scheme', 'branch__organization').prefetch_related('loanitem_set', 'loanitem_set__item').get(pk=loan_id)
            pdf_bytes, filename = loan.generate_loan_pdf_bytes()
            if pdf_bytes:
                cache_key = f"loan_pdf_{loan_id}_{current_language}"
                set_cached_pdf_bytes(cache_key, pdf_bytes)
                logger.info("[AsyncPDF] Pre-rendered and cached agreement PDF for loan #%s (%s bytes)", loan.loan_number, len(pdf_bytes))
        except Exception as exc:
            logger.warning("[AsyncPDF] Background pre-rendering failed for loan_id=%s: %s", loan_id, exc)

    return run_in_background(_render)
