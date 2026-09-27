from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError

from .auth import SignInError, check_credentials


class ProtectedAdminLoginForm(AdminAuthenticationForm):
    """The admin's sign-in, with the same lockouts as the app's (accounts.auth).
    Without this, /admin/login/ would be a way to guess staff passwords
    without limits."""

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username is not None and password:
            try:
                self.user_cache = check_credentials(self.request, username, password)
            except SignInError as error:
                if error.status == 429:
                    raise ValidationError(str(error), code="locked")
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data
