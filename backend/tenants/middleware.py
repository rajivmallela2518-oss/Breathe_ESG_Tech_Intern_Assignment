from .models import Tenant
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.http import JsonResponse


class TenantMiddleware:
    """
    Resolves tenant from JWT claim 'tenant_slug' and attaches to request.tenant.
    All downstream querysets filter on this value — never trust client-supplied tenant IDs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None

        if request.path.startswith("/admin/") or request.path.startswith("/api/v1/auth/"):
            return self.get_response(request)

        try:
            jwt_auth = JWTAuthentication()
            result = jwt_auth.authenticate(request)
            if result:
                user, token = result
                tenant_slug = token.get("tenant_slug")
                if tenant_slug:
                    request.tenant = Tenant.objects.get(slug=tenant_slug, is_active=True)
        except Exception:
            return JsonResponse({"detail": "Invalid or missing tenant."}, status=403)

        if not request.tenant:
            return JsonResponse({"detail": "Tenant not resolved."}, status=403)

        return self.get_response(request)
