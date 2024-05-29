import concurrent.futures
import pandas as pd
import typer
import random
import shutil
import os
from typing import List
from rich.progress import Progress, MofNCompleteColumn, TimeElapsedColumn

import season_simulator as sim
import summarize_results as sr
import sim_output
from perf_utils import print_perf_counter 


def sim_seasons(num_seasons: int, id: int, rating_variation_amt: int):
    sim.main(id = str(id), show_summary=False, num_seasons=num_seasons, rating_variation_amt = rating_variation_amt)
    return [id, num_seasons]


# We want the jobs to be of varying size, to stagger their start/end times
# This returns a distribution of 10 job sizes, ranging from roughly .5 to 1.5
# times num_seasons_on_avg
# The first number in the distribution is always num_seasons_on_avg,
# so running one job will work properly (along with every multiple of 10)
@print_perf_counter
def get_job_size_distribution(num_seasons_on_avg: int) -> List[int]:
    num_steps = 9
    step_size = int(num_seasons_on_avg/(num_steps+1))
    one_way_range = int((num_steps-1)/2)*step_size
    lo = num_seasons_on_avg-one_way_range
    hi = num_seasons_on_avg+one_way_range
    num_seasons_distribution = list(range(lo, hi+step_size, step_size))
    random.shuffle(num_seasons_distribution)
    return [num_seasons_on_avg] + num_seasons_distribution


@print_perf_counter
def summarize_data():
    summary = sim_output.gather_summaries()
    with pd.option_context('display.float_format', '{:,.2f}'.format):
        print(sr.augment_summary(summary))


@print_perf_counter
def parallel_driver(num_jobs: int, num_seasons_per_job: int, rating_variation_amt: int):
    num_seasons_distribution = get_job_size_distribution(num_seasons_per_job)
    with concurrent.futures.ProcessPoolExecutor() as executor:
        def submit_job(id):
            num_seasons = num_seasons_distribution[id%len(num_seasons_distribution)]
            return executor.submit(sim_seasons, num_seasons, id, rating_variation_amt)

        futures = [submit_job(id) for id in range(num_jobs)]

        with Progress(*Progress.get_default_columns(), TimeElapsedColumn(), MofNCompleteColumn()) as progress:
            simming = progress.add_task("Simulating seasons", total=num_jobs*num_seasons_per_job)

            for f in concurrent.futures.as_completed(futures):
                progress.update(simming, advance=f.result()[1])


def main(num_jobs: int = 1000, num_seasons_per_job: int = 100, rating_variation_amt: int = 30, clear_output: bool = True):
    if clear_output and os.path.exists('output'):
        shutil.rmtree('output')

    parallel_driver(num_jobs, num_seasons_per_job, rating_variation_amt)
    summarize_data()


if __name__ == '__main__':
    typer.run(main)
