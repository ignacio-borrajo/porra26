"""Token de reset de contraseña con TTL distinto por propósito.

Subclase de ``PasswordResetTokenGenerator`` de Django que:

- Codifica ``purpose`` en el material firmado → un token de welcome no
  vale como reset y viceversa.
- Aplica TTL por propósito (24h para reset, 7d para welcome) en vez del
  global ``PASSWORD_RESET_TIMEOUT`` de Django.

La invalidación por cambio de contraseña sigue siendo automática:
``user.password`` está en el hash, así que cualquier ``set_password``
rompe los tokens previos. Uso único de facto.
"""

from datetime import timedelta

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import base36_to_int, int_to_base36


class PorraPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "porra26.accounts.PasswordResetTokenGenerator"

    TIMEOUTS = {
        "reset": int(timedelta(hours=24).total_seconds()),
        "welcome": int(timedelta(days=7).total_seconds()),
    }

    def make_token(self, user, purpose="reset"):
        if purpose not in self.TIMEOUTS:
            raise ValueError(f"purpose desconocido: {purpose!r}")
        return self._make_token_with_timestamp(
            user,
            self._num_seconds(self._now()),
            self.secret,
            purpose,
        )

    def check_token(self, user, token, purpose="reset"):
        if not (user and token) or purpose not in self.TIMEOUTS:
            return False
        try:
            ts_b36, _ = token.split("-")
        except ValueError:
            return False
        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False
        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(
                self._make_token_with_timestamp(user, ts, secret, purpose),
                token,
            ):
                break
        else:
            return False
        if (self._num_seconds(self._now()) - ts) > self.TIMEOUTS[purpose]:
            return False
        return True

    def _make_token_with_timestamp(self, user, timestamp, secret, purpose):
        ts_b36 = int_to_base36(timestamp)
        hash_string = salted_hmac(
            self.key_salt,
            self._make_hash_value(user, timestamp, purpose),
            secret=secret,
            algorithm=self.algorithm,
        ).hexdigest()[::2]
        return f"{ts_b36}-{hash_string}"

    def _make_hash_value(self, user, timestamp, purpose="reset"):
        login_ts = (
            "" if user.last_login is None else user.last_login.replace(microsecond=0, tzinfo=None)
        )
        return f"{user.pk}{user.password}{login_ts}{timestamp}{user.email}{purpose}"


token_generator = PorraPasswordResetTokenGenerator()
