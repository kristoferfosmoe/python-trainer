from django.contrib import admin
from django.urls import path

from accounts.forms import ProtectedAdminLoginForm

from .api import api

admin.site.site_header = "Python Trainer admin"
admin.site.site_title = "Python Trainer admin"
admin.site.index_title = "Lessons, teams and students"
admin.site.login_form = ProtectedAdminLoginForm

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
