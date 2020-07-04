import time
import functools

# __all__ = ['tictoc', 'debug']

def tictoc(func):
    """Prints the runtime of the decorated function."""
    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()
        value = func(*args, **kwargs)
        end_time = time.perf_counter()
        run_time = end_time - start_time
        print(f'{func.__name__!r} done in {run_time:.3f}s')
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