import django
from django.conf import settings


def pytest_configure():
    settings.configure(
        MEDIA_URL="/files/",
        ZMEDIA={
            "ORG": "cg",
            "BASE_URL": "https://media.example",
            "SIZE": 1000,
            "SFTP_HOST": "h",
            "KEY_FILE": "k",
            "KNOWN_HOSTS": "kh",
        },
    )
    django.setup()
