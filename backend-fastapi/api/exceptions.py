"""Global DRF exception handler — Fix 4.

Ensures every unhandled DRF error returns the same
{"error": "...", "message": "..."} shape used everywhere else in the API.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None  # non-DRF exception — let Django handle it

    status_code = response.status_code

    # Map HTTP status to a short error code
    if status_code == 400:
        error_code = "validation_error"
    elif status_code == 401:
        error_code = "unauthenticated"
    elif status_code == 403:
        error_code = "forbidden"
    elif status_code == 404:
        error_code = "not_found"
    elif status_code == 405:
        error_code = "method_not_allowed"
    else:
        error_code = "error"

    # Already formatted correctly — pass through unchanged
    if isinstance(response.data, dict) and "error" in response.data:
        return response

    # Flatten DRF's nested validation dict into a readable message
    if isinstance(response.data, dict):
        messages = []
        for field, errors in response.data.items():
            if isinstance(errors, list):
                messages.append(f"{field}: {' '.join(str(e) for e in errors)}")
            else:
                messages.append(str(errors))
        message = " | ".join(messages) if messages else "An error occurred."
    elif isinstance(response.data, list):
        message = " | ".join(str(e) for e in response.data)
    else:
        message = str(response.data)

    response.data = {"error": error_code, "message": message}
    return response
