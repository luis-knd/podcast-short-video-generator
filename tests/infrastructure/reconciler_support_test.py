import signal
from contextlib import contextmanager


@contextmanager
def watchdog(seconds: float = 0.2):
    if not hasattr(signal, "SIGALRM") or not hasattr(signal, "setitimer"):
        yield
        return

    def _raise_timeout(_signum, _frame):
        raise TimeoutError("reconciler did not finish")

    previous_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def run_reconcile_with_watchdog(reconciler, cues, aligned_words, *, seconds: float = 0.2):
    with watchdog(seconds):
        return reconciler.reconcile(cues, aligned_words)
