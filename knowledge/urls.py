from django.urls import path
from . import views
urlpatterns=[path('',views.ingest_page,name='ingest'),path('text/',views.ingest_text,name='ingest_text'),path('document/',views.ingest_document,name='ingest_document'),path('website/',views.ingest_website,name='ingest_website'),path('chat/',views.chat_api,name='chat_api')]
