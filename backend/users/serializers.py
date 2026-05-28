from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the default JWT serializer to embed tenant_slug in the token payload.

    TenantMiddleware reads this claim on every request to resolve request.tenant
    without an extra DB query per request (the slug is already in the signed token).
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_slug"] = user.tenant.slug
        token["full_name"]   = user.full_name
        token["role"]        = user.role
        return token
