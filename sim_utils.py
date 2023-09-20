import pandas as pd
import numpy as np

def compute_standings(gms_played):
    margins = gms_played['score1']-gms_played['score2']
    winners = pd.Series(np.where(margins>0, gms_played['team1'], gms_played['team2']))
    losers  = pd.Series(np.where(margins<0, gms_played['team1'], gms_played['team2']))
    standings = pd.concat([winners.value_counts().rename('W'), losers.value_counts().rename('L')], axis=1).fillna(0)
    standings.index.name = 'team'
    standings['wpct'] = standings['W']/standings.sum(axis=1)
    return standings.sort_values('wpct', ascending=False)


def h2h_standings(games, teams):
    return compute_standings(games.query('team1 in @teams and team2 in @teams'))



def compute_standings_from_results(sim_results, incoming_standings):
    W = sim_results.groupby(['iter', 'W'])['W'].count()
    L = sim_results.groupby(['iter', 'L'])['L'].count()
    standings = pd.concat([W, L], axis=1)

    standings.index.names = ['iter', 'team']
    for col in standings.columns:
        standings[col] = standings[col].fillna(0).astype(int)

    incoming_standings['iter'] = 0
    full_standings = incoming_standings.reset_index().set_index('team') + standings.reset_index().set_index('team')

    return full_standings

def add_run_ids(df):
    df['run_id'] = df['job_id'].astype(int)*10000 + df['iter']
    return df