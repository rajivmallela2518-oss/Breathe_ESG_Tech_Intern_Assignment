from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create demo tenant and analyst user if they do not exist"

    def handle(self, *args, **kwargs):
        from tenants.models import Tenant
        from users.models import TenantUser

        tenant, created = Tenant.objects.get_or_create(
            slug="demo", defaults={"name": "Demo Corp"}
        )
        if created:
            self.stdout.write("Created tenant: Demo Corp")

        if not TenantUser.objects.filter(email="analyst@democorp.com").exists():
            TenantUser.objects.create_user(
                email="analyst@democorp.com",
                password="changeme123",
                full_name="Demo Analyst",
                tenant=tenant,
                role="ANALYST",
            )
            self.stdout.write("Created user: analyst@democorp.com")
        else:
            self.stdout.write("Demo data already exists, skipping.")
