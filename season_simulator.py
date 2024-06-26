# Functions that implement the logic for monte carlo playoff odds

import typer
import pandas as pd
import numpy as np
import series_probs_compute as probs
import datasource as ds
import sim_utils
import sim_results_processing
import sim_output
import summarize_results as sr



def sim_n_seasons(games, n):
    gms = pd.concat([games[['team1', 'team2', 'win_prob']]] * n)
    gms['iter'] = np.concatenate([np.repeat(i, len(games)) for i in range(n)])

    rands = np.random.rand(len(gms))
    gms['W'] = np.where(rands<gms['win_prob'], gms['team1'], gms['team2'])
    gms['L'] = np.where(rands>gms['win_prob'], gms['team1'], gms['team2'])
    return gms[['W', 'L', 'iter']]


def compute_probs(gms, ratings):
    rating1 = pd.merge(left=gms, right=ratings, left_on='team1', right_index=True, how='left')['rating']
    rating2 = pd.merge(left=gms, right=ratings, left_on='team2', right_index=True, how='left')['rating']
    return probs.p_game(rating1, rating2)    
    
def add_variation_to_ratings(ratings, variation_amt = 40):
    return ratings + np.random.normal(0, variation_amt, len(ratings))

def main(num_seasons: int = 100, save_output: bool = True, save_summary: bool = True, id: int = 0, show_summary: bool = True, rating_variation_amt: int = 0):
    (played, remain) = ds.get_games()
    if len(remain) == 0:
        raise NotImplementedError("Aborting: simulator doesn't function properly if no games are remaining")

    ratings = ds.get_ratings()
    if rating_variation_amt > 0:
        ratings = add_variation_to_ratings(ratings, rating_variation_amt)
    remain['win_prob'] = compute_probs(remain, ratings)

    sim_results = sim_n_seasons(remain, num_seasons)
    sim_results['job_id'] = id
    sim_results = sim_utils.add_run_ids(sim_results)

    standings = sim_results_processing.process_sim_results(sim_results, played, ds.league_structure, ratings)

    if save_output:
        sim_output.write_output(standings, 'standings', id)
        sim_output.write_output(sim_results, 'games', id)
    if save_summary:
        summary = sim_results_processing.summarize_results(standings)
        sim_output.write_output(summary, 'summaries', id)
    if show_summary:
        print(sr.augment_summary(summary))


if __name__ == "__main__":
    typer.run(main) 