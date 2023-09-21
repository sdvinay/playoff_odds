# Functions that implement the logic for monte carlo playoff odds

import typer
import pandas as pd
import numpy as np
import series_probs_compute as probs
import datasource_mlb as ds
import tiebreakers
import sim_utils
import sim_output


# Merge in league structure, and compute playoff seeding
def process_sim_results(sim_results, played):
    cur_standings = sim_utils.compute_standings(played)
    standings = sim_utils.compute_standings_from_results(sim_results, cur_standings).reset_index()
    job_id = sim_results.iloc[0]['job_id']
    standings['job_id'] = job_id

    standings = sim_utils.add_run_ids(standings)
    standings['wpct'] = standings['W'] / (standings['W'] + standings['L'])

    # Merge in the div/lg data
    standings = pd.merge(left=standings, right=ds.league_structure, left_on='team', right_index=True)
    standings = standings.set_index(['run_id', 'team'])[['W', 'L', 'wpct', 'div', 'lg']]

    # compute div_wins and playoff seeds
    add_division_winners(standings)
    add_lg_ranks(standings)

    return standings

def summarize_results(standings):
    counts = standings.reset_index()[['team', 'lg_rank']].value_counts().unstack()
    wins = standings.groupby('team')['W'].agg(['sum', 'max', 'min', len])
    summary = pd.merge(left=wins, right=counts, on='team', how='left')
    for col in counts.columns:
        summary[col] = summary[col].fillna(0).astype(int)
    return summary.rename(columns={i: f'r{i}' for i in range(100)})



def add_division_winners(standings):
    standings['div_win'] = False

    div_leading_wpct = standings.groupby(['run_id', 'div'])['wpct'].transform(max)
    potential_div_winners = standings.query('wpct == @div_leading_wpct')
    tied_team_ct = potential_div_winners.reset_index()[['run_id', 'div']].value_counts().rename("tied_teams")
    potential_div_winners = pd.merge(left=potential_div_winners.reset_index(), right=tied_team_ct, on=['run_id', 'div']).set_index(['run_id', 'team'])
    # outright division winners
    outright_div_winners = potential_div_winners.query('tied_teams==1').index
    standings.loc[outright_div_winners, 'div_win'] = True
    # ties
    tied_teams = potential_div_winners.query('tied_teams>1').reset_index()
    if len(tied_teams)>0:
        tied_sets = tied_teams.groupby(['run_id', 'div'])['team'].apply(set)
        tie_winners = tied_sets.apply(lambda tms: tiebreakers.break_tie(tms)[0]).reset_index().set_index(['run_id', 'team']).index
        standings.loc[tie_winners, 'div_win'] = True
    return standings


def add_lg_ranks(standings):
    tied_tm_ct = standings.groupby(['run_id', 'lg', 'wpct'])['wpct'].transform('size')
    if sum(tied_tm_ct) > 0:
        tied_sets = standings[tied_tm_ct>1].reset_index().groupby(['run_id', 'lg', 'wpct'])['team'].apply(set)
        tie_orders = tied_sets.apply(lambda tms: tiebreakers.break_tie(tms)).explode()
        # We need to take tie-orders (which are ordered lists) and convert them into a number we can use for sorting
        tiebreak = (15 - tie_orders.groupby(['run_id', 'lg', 'wpct']).cumcount())
        standings['tiebreak'] = pd.concat([tie_orders, tiebreak], axis=1).reset_index().set_index(['run_id', 'team'])[0]
        standings['tiebreak'].fillna(0, inplace=True)
    else:
        standings['tiebreak'] = 0

    standings['lg_rank'] = standings.sort_values(by=['div_win', 'wpct', 'tiebreak'], ascending=False).groupby(['run_id', 'lg']).cumcount()+1
    return standings



def sim_n_seasons(games, n):
    gms = pd.concat([games[['team1', 'team2', 'win_prob']]] * n)
    gms['iter'] = np.concatenate([np.repeat(i, len(games)) for i in range(n)])

    rands = np.random.rand(len(gms))
    gms['W'] = np.where(rands<gms['win_prob'], gms['team1'], gms['team2'])
    gms['L'] = np.where(rands>gms['win_prob'], gms['team1'], gms['team2'])
    return gms[['W', 'L', 'iter']]

def get_tm_ranks(standings):
    tms_by_rank = standings[['lg', 'lg_rank']].reset_index().set_index(['run_id', 'lg', 'lg_rank'])['team'].unstack(level='lg_rank')
    return tms_by_rank.rename(columns={i: f'r{i}' for i in range(100)})


def compute_probs(gms, ratings):
    rating1 = pd.merge(left=gms, right=ratings, left_on='team1', right_index=True, how='left')['rating']
    rating2 = pd.merge(left=gms, right=ratings, left_on='team2', right_index=True, how='left')['rating']
    return probs.p_game(rating1, rating2)    
    
def add_variation_to_ratings(ratings):
    offsets = (-100, 100, 0, 0)
    return ratings + np.random.choice(offsets, len(ratings))

def main(num_seasons: int = 100, save_output: bool = True, save_summary: bool = True, save_ranks: bool = True, id: int = 0, show_summary: bool = True, vary_ratings: bool = False):
    print(f'Simulating {num_seasons} seasons as ID {id}')
    (played, remain) = ds.get_games()

    ratings = ds.get_ratings()
    if vary_ratings:
        ratings = add_variation_to_ratings(ratings)
    remain['win_prob'] = compute_probs(remain, ratings)

    sim_results = sim_n_seasons(remain, num_seasons)
    sim_results['job_id'] = id
    sim_results = sim_utils.add_run_ids(sim_results)

    standings = process_sim_results(sim_results, played)
    standings['job_id'] = id

    if save_output:
        sim_output.write_output(standings, 'standings', id)
        sim_output.write_output(sim_results, 'games', id)
    if save_summary:
        summary = summarize_results(standings)
        sim_output.write_output(summary, 'summaries', id)

    if save_ranks:
        tms_by_rank = get_tm_ranks(standings)
        sim_output.write_output(tms_by_rank, 'ranks', id)

if __name__ == "__main__":
    typer.run(main) 