import pandas as pd
import numpy as np
import datasource as ds
import sim_utils as su


# Count the number of div/wc/playoff appearances by team from a set of results
# Compute other probabilities (pennant, championship, home game)
def summarize_sim_results(df_results):
    counts = df_results.query('lg_rank <= 6').reset_index()[['team', 'lg_rank']].value_counts().unstack()
    wins = df_results.groupby('team')['W'].agg(['mean', 'max', 'min'])
    summary = pd.merge(left=wins, right=counts, on='team', how='left')
    for col in counts.columns:
        summary[col] = summary[col].fillna(0).astype(int)
    summary['pennant_shares'] = df_results.groupby('team')['pennant_shares'].sum()
    summary['pennant_shares'] = df_results.groupby('team')['pennant_shares'].sum()
    return summary

def get_tm_ranks(standings):
    tms_by_rank = standings[['lg', 'lg_rank']].reset_index().set_index(['run_id', 'lg', 'lg_rank'])['team'].unstack(level='lg_rank')
    return tms_by_rank.rename(columns={i: f'r{i}' for i in range(100)})


def augment_summary(summary):
    summary['div_wins'] = summary[[f'r{i}' for i in range(1, 4)]].sum(axis=1)
    summary['byes'] = summary[[f'r{i}' for i in range(1, 3)]].sum(axis=1)
    summary['playoffs'] = summary[[f'r{i}' for i in range(1, 7)]].sum(axis=1)

    summary['mean'] = summary['sum']/summary['len']

    # Get ratings for display purposes
    ratings = ds.get_ratings()
    summary = pd.merge(left=summary, right=ratings.astype(int), left_index=True, right_index=True)

    # Get standings
    standings = get_standings_for_display()
    summary = pd.merge(left=standings, right=summary, left_index=True, right_index=True)
    cols = ['W', 'L', 'GB', 'rating', 'mean', 'max', 'min'] + ['div_wins', 'byes', 'playoffs', 'lds_shares', 'lcs_shares', 'pennant_shares', 'ws_shares', 'p_home_game']
    return summary[cols].sort_values(['ws_shares', 'mean'], ascending=False)


def get_standings_for_display():
    (cur, remain) = ds.get_games()
    standings = pd.merge(left=ds.league_structure, right=su.compute_standings(cur),left_index=True, right_index=True)
    standings = standings.sort_values(by=['div', 'wpct'], ascending=[True, False])
    standings['over500'] = standings['W'] - standings['L']

    # compute GB
    div_leaders = standings.groupby('div')['over500'].transform(max)
    standings['GB'] = (div_leaders - standings['over500'])/2
    return standings
    

def restructure_results(sim_results):
    wins = sim_results['W'].unstack(level='team')
    lg_ranks = sim_results['lg_rank'].unstack(level='team')
    tms_by_rank = sim_results[['lg', 'lg_rank']].reset_index().set_index(['run_id', 'lg', 'lg_rank'])['team'].unstack(level='lg_rank')
    wins_by_rank = sim_results.reset_index().set_index(['run_id', 'lg', 'lg_rank'])['W'].unstack(level='lg_rank')
    return (wins, lg_ranks, tms_by_rank, wins_by_rank)
