import os
import time

from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

# Versión del service worker. Se calcula al importar el módulo (una vez
# por proceso): así todos los workers de gunicorn comparten la misma
# versión durante la vida del deploy, pero al hacer un release nuevo el
# proceso arranca con otra versión y los clientes detectan que el SW ha
# cambiado.
_VERSION = (
    os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA") or str(int(time.time()))
)


def _sw_version() -> str:
    return _VERSION


def manifest(request):
    return render(
        request,
        "pwa/manifest.webmanifest",
        content_type="application/manifest+json",
    )


def service_worker(request):
    response = render(
        request,
        "pwa/service-worker.js",
        {"version": _sw_version()},
        content_type="application/javascript",
    )
    # Garantiza scope raíz incluso si algún proxy reescribe la ruta.
    response["Service-Worker-Allowed"] = "/"
    # El SW lo gestiona el navegador internamente; HTTP cache nos estorba
    # al desplegar (los clientes no detectarían cambios hasta expirar).
    response["Cache-Control"] = "no-cache"
    return response


def offline(request):
    """Página fallback que sirve el service worker cuando una navegación falla
    o el origen devuelve 5xx (típicamente, durante el redeploy de Railway).

    Render manual sin pasar `request`: así `render_to_string` no aplica los
    context processors, que tocan DB (`Payment.objects...`). El objetivo de
    esta página es justamente sobrevivir a momentos en los que la DB puede
    estar caída — no podemos depender de ella para renderizarla."""
    html = render_to_string("pwa/offline.html")
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    # Si tuviéramos `no-store`, el SW no podría guardar la respuesta. Un TTL
    # corto en HTTP cache evita que un cliente sin SW se quede con una
    # versión vieja indefinidamente.
    response["Cache-Control"] = "public, max-age=60"
    return response
