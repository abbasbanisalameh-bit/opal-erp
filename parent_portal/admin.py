from django.contrib import admin
from .models import ParentProfile
from .messages_models import ParentMessage

admin.site.register(ParentProfile)

admin.site.register(ParentMessage)
