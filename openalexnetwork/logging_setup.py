import logging
import contextlib


class ContextFilter(logging.Filter):
    """A logging filter that injects temporary context into log records."""

    def __init__(self):
        super().__init__()
        self.context_stack = []

    def set_context(self, context):
        """Push context onto stack."""
        self.context_stack.append(context)

    def pop_context(self):
        """Remove the last context."""
        if self.context_stack:
            self.context_stack.pop()

    def filter(self, record):
        """Modify log record to include context."""
        record.context = {}
        if self.context_stack:
            for ctx in self.context_stack:
                record.context.update(ctx)
        return True


context_filter = ContextFilter()

ROOT_LOGGER_NAME = __name__.split(".")[0]


def setup_logging(level=logging.INFO):
    """
    Initializes logging for the library.

    - Sets the logging level (default: INFO)
    - Adds a StreamHandler if none exist
    - Attaches ContextFilter for context injection
    """
    root_logger = logging.getLogger(ROOT_LOGGER_NAME)
    root_logger.setLevel(level)

    if not root_logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s - [%(context)s] %(message)s")
        handler.setFormatter(formatter)

        handler.addFilter(context_filter)
        root_logger.addHandler(handler)


@contextlib.contextmanager
def log_context(context_dict):
    """Temporarily set logging context."""
    context_filter.set_context(context_dict)
    try:
        yield
    finally:
        context_filter.pop_context()
