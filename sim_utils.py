import pandas as pd
import numpy as np

def compute_standings(gms_played, groupby = []):
    standings = pd.concat([gms_played.groupby(groupby + [dec])[dec].count() for dec in ['W', 'L']], axis=1)
    standings.index.names = groupby + ['team']
    
    for col in standings.columns:
        standings[col] = standings[col].fillna(0).astype(int)

    standings['wpct'] = standings['W']/standings.sum(axis=1)
    return standings.sort_values('wpct', ascending=False)


def h2h_standings(games, teams):
    return compute_standings(games.query('team1 in @teams and team2 in @teams'))


def compute_standings_from_results(sim_results, incoming_standings):
    sim_standings = compute_standings(sim_results, ['iter'])

    incoming_standings['iter'] = 0 # so we can just add the 'iter' columns from the two tables to keep the one from the sim
    full_standings = incoming_standings.reset_index().set_index('team') + sim_standings.reset_index().set_index('team')

    return full_standings

def add_run_ids(df):
    df['run_id'] = df['job_id'].astype(int)*10000 + df['iter']
    return df