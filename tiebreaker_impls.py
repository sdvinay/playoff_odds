import pandas as pd
import sim_utils


def h2h_standings(games, teams):
    if games is not None:
        h2h_games = games[(games['W'].isin(teams)) & (games['L'].isin(teams))]
        return sim_utils.compute_standings(h2h_games)


def intradivisional_records(games, teams, league_structure):
    df = pd.merge(left=games, right=league_structure, left_on='W', right_index=True)
    df = pd.merge(left=df, right=league_structure, left_on='L', right_index=True, suffixes=["_W", "_L"])
    div_games = df.query('div_W==div_L')
    standings = sim_utils.compute_standings(div_games)
    return standings.query('team in @teams')


# interdivisional: same league but different division
def interdivisional_records(games, teams, league_structure):
    df = pd.merge(left=games, right=league_structure, left_on='W', right_index=True)
    df = pd.merge(left=df, right=league_structure, left_on='L', right_index=True, suffixes=["_W", "_L"])
    interdiv_games = df.query('lg_W==lg_L and div_W!=div_L')
    standings = sim_utils.compute_standings(interdiv_games)
    return standings.query('team in @teams')
