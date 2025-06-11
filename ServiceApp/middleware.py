from django.db import transaction, OperationalError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
import time
import logging

logger = logging.getLogger(__name__)


class TransactionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        max_retries = 3
        retry_delay = 0.1  # 100ms delay between retries
        
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    response = self.get_response(request)
                return response
            except OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retry {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    # Final attempt failed or different error
                    logger.error(f"Database operation failed: {str(e)}")
                    
                    # Return user-friendly error instead of Django debug page
                    if request.is_ajax() or request.content_type == 'application/json':
                        return JsonResponse({
                            'error': 'Database temporarily unavailable. Please try again.',
                            'details': 'The system is currently processing other requests. Please wait a moment and retry.'
                        }, status=503)
                    else:
                        # For regular HTTP requests, render a user-friendly error page
                        return render(request, 'error_pages/database_locked.html', {
                            'error_message': 'Database temporarily unavailable',
                            'error_details': 'The system is currently busy. Please wait a moment and try again.',
                            'retry_url': request.get_full_path()
                        }, status=503)
        
        # This should never be reached, but just in case
        return HttpResponse("Service temporarily unavailable", status=503)