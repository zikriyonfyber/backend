from rest_framework.permissions import BasePermission

from .auth import RouterPrincipal


class IsAuthenticatedRouter(BasePermission):
    message = "This endpoint may only be called by an authenticated router."

    def has_permission(self, request, view):
        return isinstance(request.user, RouterPrincipal)
