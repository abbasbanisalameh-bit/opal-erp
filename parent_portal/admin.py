from django.contrib import admin
from .models import ParentProfile
from .messages_models import ParentMessage
from .notifications import Notification

admin.site.register(ParentProfile)

admin.site.register(ParentMessage)

admin.site.register(Notification)
