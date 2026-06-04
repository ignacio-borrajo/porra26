import os
import time

from django.shortcuts import render

# Versión del service worker. Se calcula al importar el módulo (una vez
# por proceso): así todos los workers de gunicorn comparten la misma
# versión durante la vida del deploy, pero al hacer un release nuevo el
# proceso arranca con otra versión y los clientes detectan que el SW ha
# cambiado.
_VERSION = (
    os.environ.get("GIT_SHA")
    or os.environ.get("RAILWAY_GIT_COMMIT_SHA")
    or str(int(time.time()))
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
