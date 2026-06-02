web: DJANGO_SETTINGS_MODULE=porra26.settings.prod python manage.py collectstatic --no-input && gunicorn porra26.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 2 --timeout 60 --log-file -
