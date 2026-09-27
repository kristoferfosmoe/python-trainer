from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from .sessions import on_sign_in

        user_logged_in.connect(on_sign_in, dispatch_uid="accounts.sessions.on_sign_in")
