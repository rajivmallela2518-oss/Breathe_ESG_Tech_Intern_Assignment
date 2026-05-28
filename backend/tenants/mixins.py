class TenantQuerySetMixin:
    """
    Automatically scopes every queryset to request.tenant.
    Any view that inherits this mixin cannot accidentally return cross-tenant data.
    """

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.tenant)
