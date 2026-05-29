import uuid
from django.db import models


class UUIDModel(models.Model):
    """
    Abstract base model that uses UUID as primary key.
    All models should inherit from this for better security.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    class Meta:
        abstract = True
