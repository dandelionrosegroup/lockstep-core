# Lockstep Chain Protocol — error response helpers
# Copyright (C) 2025-2026 Jack Daniel Williams / Dandelion Rose Group, LLC
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Structured error responses for Lockstep MCP tools.

All tools return errors as JSON strings with consistent structure:
  {"error": "<code>", "message": "<description>", "suggestion": "...", "details": {...}}
"""

import json
from typing import Optional


# Error codes
NOT_FOUND = "not_found"
INVALID_STATE = "invalid_state"
VALIDATION_ERROR = "validation_error"
IO_ERROR = "io_error"
ALREADY_EXISTS = "already_exists"


def error_response(
    code: str,
    message: str,
    suggestion: Optional[str] = None,
    details: Optional[dict] = None,
) -> str:
    """Build a structured error response JSON string."""
    response: dict = {
        "error": code,
        "message": message,
    }
    if suggestion:
        response["suggestion"] = suggestion
    if details:
        response["details"] = details
    return json.dumps(response, indent=2)


def success_response(data: dict) -> str:
    """Build a structured success response JSON string."""
    return json.dumps(data, indent=2, default=str)
