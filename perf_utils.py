import time

def print_perf_counter(func):
    '''
    create a timing decorator function
    use
    @print_perf_counter
    just above the function you want to time
    '''
    def wrapper(*arg):
        start = time.perf_counter()
        result = func(*arg)
        end = time.perf_counter()
        print(f'{func.__name__} took {round(end-start, 2)} second(s)')
        return result
    return wrapper