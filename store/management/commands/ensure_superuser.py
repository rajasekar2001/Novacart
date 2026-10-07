import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the production Django superuser."

    def handle(self, *args, **options):
        username = os.getenv(
            "DJANGO_SUPERUSER_USERNAME",
            "",
        ).strip()

        email = os.getenv(
            "DJANGO_SUPERUSER_EMAIL",
            "",
        ).strip()

        password = os.getenv(
            "DJANGO_SUPERUSER_PASSWORD",
            "",
        )

        if not username:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_SUPERUSER_USERNAME is not set. "
                    "Skipping superuser creation."
                )
            )
            return

        if not password:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_SUPERUSER_PASSWORD is not set. "
                    "Skipping superuser creation."
                )
            )
            return

        User = get_user_model()

        lookup_field = User.USERNAME_FIELD

        lookup = {
            lookup_field: username,
        }

        user, created = User.objects.get_or_create(
            **lookup
        )

        changed = False

        if hasattr(user, "email") and email:
            if user.email != email:
                user.email = email
                changed = True

        if not user.is_staff:
            user.is_staff = True
            changed = True

        if not user.is_superuser:
            user.is_superuser = True
            changed = True

        # Set password from the Render environment variable.
        #
        # This also means you can temporarily set the variable
        # again later if you need to reset the admin password.
        user.set_password(password)
        changed = True

        if hasattr(user, "is_active"):
            if not user.is_active:
                user.is_active = True
                changed = True

        if changed:
            user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Superuser '{username}' created successfully."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Superuser '{username}' updated successfully."
                )
            )