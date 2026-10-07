from django.contrib import admin

from .models import ChatMessage, FAQ, KnowledgeSource


@admin.register(KnowledgeSource)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("title", "source_type", "status", "created_by", "created_at")
    list_filter = ("source_type", "status")
    search_fields = ("title", "source_url", "raw_text")
    readonly_fields = ("created_at", "updated_at")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "faq_type", "source")
    list_filter = ("faq_type", "source__source_type")
    search_fields = ("question", "answer", "source_url")


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("session_id", "user", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("session_id", "content", "user__username")
