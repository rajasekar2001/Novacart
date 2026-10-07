from django.conf import settings
from django.db import models


class KnowledgeSource(models.Model):
    SOURCE_TYPES = [
        ("text", "Text"),
        ("document", "Document"),
        ("website", "Website"),
    ]

    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("ready", "Ready"),
        ("failed", "Failed"),
    ]

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_sources",
    )

    title = models.CharField(
        max_length=200,
    )

    source_type = models.CharField(
        max_length=20,
        choices=SOURCE_TYPES,
    )

    source_url = models.URLField(
        blank=True,
    )

    file = models.FileField(
        upload_to="knowledge/",
        blank=True,
    )

    raw_text = models.TextField(
        blank=True,
    )

    # The complete structured FAQ JSON array.
    faq_json = models.JSONField(
        default=list,
        blank=True,
    )

    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default="ready",
        db_index=True,
    )

    error_message = models.TextField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.title


class FAQ(models.Model):
    source = models.ForeignKey(
        KnowledgeSource,
        on_delete=models.CASCADE,
        related_name="faqs",
    )

    question = models.TextField()

    answer = models.TextField()

    keywords = models.JSONField(
        default=list,
        blank=True,
    )

    faq_type = models.CharField(
        max_length=40,
        default="general",
        db_index=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    source_url = models.URLField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["faq_type"]),
            models.Index(fields=["source", "faq_type"]),
        ]

    def __str__(self):
        return self.question[:80]


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    session_id = models.CharField(
        max_length=80,
        db_index=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chat_messages",
    )

    role = models.CharField(
        max_length=12,
        choices=ROLE_CHOICES,
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "created_at",
        ]

    def __str__(self):
        return (
            f"{self.role}: "
            f"{self.content[:60]}"
        )
