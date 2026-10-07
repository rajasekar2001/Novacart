import json
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import ChatMessage, FAQ, KnowledgeSource
from .services import (
    answer,
    crawl,
    extract_document,
    generate_faqs,
    generate_website_faqs,
)


@staff_member_required
def ingest_page(request):
    sources = KnowledgeSource.objects.order_by(
        "-created_at"
    )[:20]

    return render(
        request,
        "knowledge/ingest.html",
        {
            "sources": sources,
        },
    )


@transaction.atomic
def save_source(
    title,
    source_type,
    text,
    url="",
    upload=None,
    faqs=None,
    created_by=None,
):
    """
    Save the complete JSON array in KnowledgeSource.faq_json.

    Every FAQ is also stored in an individual FAQ row
    for retrieval.
    """

    if faqs is None:
        faqs = generate_faqs(
            text=text,
            title=title,
            source_url=url,
        )

    source = KnowledgeSource.objects.create(
        title=title,
        source_type=source_type,
        source_url=url,
        file=upload or "",
        raw_text=text[:100000],
        faq_json=faqs,
        created_by=created_by,
        status="ready",
    )

    faq_objects = []

    for row in faqs:
        question = row.get(
            "question",
            "",
        ).strip()

        faq_answer = row.get(
            "answer",
            "",
        ).strip()

        if not question or not faq_answer:
            continue

        faq_objects.append(
            FAQ(
                source=source,
                question=question,
                answer=faq_answer,
                keywords=row.get(
                    "keywords",
                    [],
                ),
                faq_type=row.get(
                    "faq_type",
                    "general",
                ),
                metadata=row.get(
                    "metadata",
                    {},
                ),
                source_url=row.get(
                    "source_url",
                    url,
                ),
            )
        )

    FAQ.objects.bulk_create(
        faq_objects
    )

    return source


@require_POST
@staff_member_required
def ingest_text(request):
    title = request.POST.get(
        "title",
        "Pasted text",
    ).strip()

    text = request.POST.get(
        "text",
        "",
    ).strip()

    if not text:
        messages.error(
            request,
            "Please enter some text.",
        )

        return redirect("ingest")

    source = save_source(
        title=title,
        source_type="text",
        text=text,
        created_by=request.user,
    )

    messages.success(
        request,
        (
            f"Text converted and saved as "
            f"{source.faqs.count()} structured "
            "FAQ records."
        ),
    )

    return redirect("ingest")


@require_POST
@staff_member_required
def ingest_document(request):
    uploaded_file = request.FILES.get(
        "document"
    )

    if not uploaded_file:
        messages.error(
            request,
            "Please choose a document.",
        )

        return redirect("ingest")

    maximum_bytes = (
        settings.MAX_UPLOAD_MB
        * 1024
        * 1024
    )

    if uploaded_file.size > maximum_bytes:
        messages.error(
            request,
            (
                "The selected file exceeds the "
                f"{settings.MAX_UPLOAD_MB} MB limit."
            ),
        )

        return redirect("ingest")

    try:
        extracted_text = extract_document(
            uploaded_file
        )

        if not extracted_text.strip():
            messages.error(
                request,
                "No readable text was found in the document.",
            )

            return redirect("ingest")

        source = save_source(
            title=uploaded_file.name,
            source_type="document",
            text=extracted_text,
            upload=uploaded_file,
            created_by=request.user,
        )

        messages.success(
            request,
            (
                "Document converted and saved as "
                f"{source.faqs.count()} structured "
                "FAQ records."
            ),
        )

    except ValueError as exc:
        messages.error(
            request,
            str(exc),
        )

    except Exception:
        messages.error(
            request,
            "The document could not be processed.",
        )

    return redirect("ingest")


@require_POST
@staff_member_required
def ingest_website(request):
    url = request.POST.get(
        "url",
        "",
    ).strip()

    if not url:
        messages.error(
            request,
            "Please enter a website URL.",
        )

        return redirect("ingest")

    try:
        pages = crawl(
            start_url=url,
            max_pages=settings.MAX_CRAWL_PAGES,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("ingest")

    if not pages:
        messages.error(
            request,
            "No readable website pages were found.",
        )

        return redirect("ingest")

    raw_text_parts = []

    for page in pages:
        raw_text_parts.append(
            (
                f"PAGE: {page['title']}\n"
                f"URL: {page['url']}\n"
                f"{page['text']}"
            )
        )

    raw_text = "\n\n".join(
        raw_text_parts
    )

    faqs = generate_website_faqs(
        pages
    )

    if not faqs:
        messages.error(
            request,
            (
                "Pages were found, but no useful "
                "FAQ records could be extracted."
            ),
        )

        return redirect("ingest")

    source = save_source(
        title=url,
        source_type="website",
        text=raw_text,
        url=url,
        faqs=faqs,
        created_by=request.user,
    )

    messages.success(
        request,
        (
            f"Crawled {len(pages)} pages and saved "
            f"{source.faqs.count()} structured "
            "FAQ records."
        ),
    )

    return redirect("ingest")


@require_POST
def chat_api(request):
    try:
        data = json.loads(
            request.body
        )

    except json.JSONDecodeError:
        return JsonResponse(
            {
                "error": "Invalid JSON request.",
            },
            status=400,
        )

    question = str(
        data.get("message", "")
    ).strip()

    if len(question) > getattr(settings, "CHAT_MAX_MESSAGE_CHARS", 2000):
        return JsonResponse(
            {"error": "Message is too long."},
            status=400,
        )

    if not question:
        return JsonResponse(
            {
                "error": "Message is required.",
            },
            status=400,
        )

    if not request.session.session_key:
        request.session.create()

    session_id = (
        request.session.session_key
        or str(uuid.uuid4())
    )

    history_rows = (
        ChatMessage.objects
        .filter(session_id=session_id)
        .order_by("-created_at")[:6]
        .values("role", "content")
    )

    conversation_history = list(
        history_rows
    )[::-1]

    ChatMessage.objects.create(
        session_id=session_id,
        user=request.user if request.user.is_authenticated else None,
        role="user",
        content=question,
    )

    try:
        response_text, sources = answer(
            question=question,
            history=conversation_history,
            user=request.user if request.user.is_authenticated else None,
        )
    except Exception:
        response_text = "I could not process that request right now. Please try again."
        sources = []

    ChatMessage.objects.create(
        session_id=session_id,
        user=request.user if request.user.is_authenticated else None,
        role="assistant",
        content=response_text,
    )

    return JsonResponse({
        "answer": response_text,
        "sources": sources,
    })
