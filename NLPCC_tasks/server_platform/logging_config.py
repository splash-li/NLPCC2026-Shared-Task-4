import logging

class StaticAssetFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Filter out logs for static assets
        message = record.getMessage()
        if "/ui/assets/" in message and "304 Not Modified" in message:
            return False
        return True

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "static_asset_filter": {
            "()": StaticAssetFilter,
        },
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["static_asset_filter"],
        },
    },
    "formatters": {
        "default": {
            "fmt": "%(levelprefix)s %(message)s",
            "use_colors": True,
        },
    },
    "loggers": {
        "uvicorn.access": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
}