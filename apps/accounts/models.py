import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from config.constants import DEFAULT_COUNTRY

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(
        unique=True,
        error_messages={
            'unique': 'A user with this email already exists.'
        }
    )
    phone = models.CharField(max_length=15, blank=True, null=True)
    is_store_owner = models.BooleanField(
        default=False,
        help_text='Designates whether user can create/manage stores'
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return self.email

    def get_full_name(self):
        """Return first_name + last_name or email if names not set"""
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email
