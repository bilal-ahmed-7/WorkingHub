from rest_framework import permissions


class IsCompanyAdmin(permissions.BasePermission):
    """
    Custom permission allowing access only to authenticated Company Owners (ADMIN role).
    """

    message = "Only company administrators can perform this action."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "is_company_admin", False)
            and request.user.company is not None
        )


class IsCompanyMember(permissions.BasePermission):
    """
    Custom permission allowing access only to users who belong to a valid Company tenant.
    """

    message = "User is not assigned to an active company tenant."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.company is not None
        )
