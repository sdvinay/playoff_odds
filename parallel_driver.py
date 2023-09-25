import concurrent.futures
import time
import pandas as pd
import typer
import random
import shutil
import os
from typing import List

import season_simulator as sim
import summarize_results as sr
import sim_output


def print_perf_counter(func):
    '''
    create a timing decorator function
    use
    @print_timing
    just above the function you want to time
    '''
    def wrapper(*arg):
        start = time.perf_counter()
        result = func(*arg)
        end = time.perf_counter()
        print(f'{func.__name__} took {round(end-start, 2)} second(s)')
        return result
    return wrapper

def sim_seasons(num_seasons: int, id: int, vary_ratings: bool):
    sim.main(id = str(id), show_summary=False, num_seasons=num_seasons, vary_ratings=vary_ratings)
    return id


# We want the jobs to be of varying size, to stagger their start/end times
# This returns a distribution of 10 job sizes, ranging from roughly .5 to 1.5
# times num_seasons_on_avg
# The first number in the distribution is always num_seasons_on_avg,
# so running one job will work properly (along with every multiple of 10)
@print_perf_counter
def get_job_size_distribution(num_seasons_on_avg: int) -> List[int]:
    num_steps = 9
    step_size = int(num_seasons_on_avg/num_steps)
    one_way_range = int((num_steps-1)/2)*step_size
    lo = num_seasons_on_avg-one_way_range
    hi = num_seasons_on_avg+one_way_range
    num_seasons_distribution = list(range(lo, hi+step_size, step_size))
    random.shuffle(num_seasons_distribution)
    return [num_seasons_on_avg] + num_seasons_distribution


@print_perf_counter
def summarize_data():
    summary = sim_output.gather_summaries()
    standings = sim_output.gather_results()
    tms_by_rank = sr.get_tm_ranks(standings)
    with pd.option_context('display.float_format', '{:,.2f}'.format):
        print(sr.augment_summary(summary, tms_by_rank))


@print_perf_counter
def parallel_driver(num_jobs: int, num_seasons_per_job: int, vary_ratings: bool):
    num_seasons_distribution = get_job_size_distribution(num_seasons_per_job)
    with concurrent.futures.ProcessPoolExecutor() as executor:
        def submit_job(id):
            num_seasons = num_seasons_distribution[id%len(num_seasons_distribution)]
            return executor.submit(sim_seasons, num_seasons, id, vary_ratings)

        futures = [submit_job(id) for id in range(num_jobs)]

        for f in concurrent.futures.as_completed(futures):
            print(f'Job {f.result()} completed')


def main(num_jobs: int = 100, num_seasons_per_job: int = 1000, vary_ratings: bool = True, clear_output: bool = True):
    if clear_output and os.path.exists('output'):
        shutil.rmtree('output')

    parallel_driver(num_jobs, num_seasons_per_job, vary_ratings)
    summarize_data()


if __name__ == '__main__':
    typer.run(main)
