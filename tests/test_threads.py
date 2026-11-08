"""Tests for the threading module."""

import time
from threading import Thread

from utils.threads import threaded


class TestThreaded:
    """Tests for utils.threads.threaded decorator."""

    def test_spawns_thread(self):
        """Decorator wraps function to run in a new thread."""

        class Container:
            threads = []

            @threaded
            def dummy_method(self):
                import time
                time.sleep(0.1)

        container = Container()
        result = container.dummy_method()

        assert isinstance(result, Thread)
        assert result.is_alive()

    def test_thread_starts_immediately(self):
        """Thread starts execution right away."""

        class Container:
            threads = []
            executed = False

            @threaded
            def flag_method(self):
                Container.executed = True

        container = Container()
        container.flag_method()
        container.threads[0].join(timeout=1)

        assert Container.executed is True

    def test_thread_added_to_list(self):
        """Thread is appended to the instance's threads list."""

        class Container:
            threads = []

            @threaded
            def dummy_method(self):
                pass

        container = Container()
        container.dummy_method()

        assert len(container.threads) == 1
        assert container.threads[0] is not None

    def test_passes_arguments(self):
        """Arguments are correctly passed to the wrapped function."""

        class Container:
            threads = []
            received_args = ()
            received_kwargs = {}

            @threaded
            def arg_method(self, a, b, c=None):
                Container.received_args = (a, b)
                Container.received_kwargs = {"c": c} if c is not None else {}

        container = Container()
        container.arg_method(1, 2, c=3)
        container.threads[0].join(timeout=1)

        assert Container.received_args == (1, 2)
        assert Container.received_kwargs == {"c": 3}

    def test_preserves_function_name(self):
        """@wraps preserves the original function's name."""

        class Container:
            threads = []

            @threaded
            def named_function(self):
                pass

        container = Container()
        assert container.named_function.__name__ == "named_function"

    def test_multiple_threads(self):
        """Multiple threaded calls create multiple threads."""

        class Container:
            threads = []

            @threaded
            def dummy_method(self):
                time.sleep(0.01)

        container = Container()
        for _ in range(3):
            container.dummy_method()

        assert len(container.threads) == 3
        for thread in container.threads:
            thread.join(timeout=1)
