import time
import functools
import warnings
import asyncio
import logging

def tictoc(func):
    """Prints the runtime of the decorated function."""
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()
        value = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        logging.info(f'{func.__name__!r} done in {run_time:.3f}s')
        return value
    return wrapper_timer

def debug(func):
    """Print the function signature and return value"""
    @functools.wraps(func)
    def wrapper_debug(*args, **kwargs):
        args_repr = [repr(a) for a in args]
        kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
        signature = ", ".join(args_repr + kwargs_repr)
        print(f"Calling {func.__name__}({signature})")
        value = func(*args, **kwargs)
        print(f"{func.__name__!r} returned {value!r}")
        return value
    return wrapper_debug

def verifyrun(func):
    """Prints whether the decorated function ran."""
    @functools.wraps(func)
    def wrapper_verifyrun(*args, **kwargs):
        print(f'Ran {func.__name__!r} from {func.__module__}.')
        value = func(*args, **kwargs)
        return value
    return wrapper_verifyrun

def shutupwarnings(func):
    """Stops warnings for the decorated function."""
    @functools.wraps(func)
    def wrapper_shutupwarnings(*args, **kwargs):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('ignore')
            response = func(*args, **kwargs)
        return response
    return wrapper_shutupwarnings

def run_in_executor(func):
    """Runs a blocking operation from a seperate thread."""
    @functools.wraps(func)
    def wrapper_run_in_executor(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))
    return wrapper_run_in_executor