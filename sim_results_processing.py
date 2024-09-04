import pandas as pd
import tiebreakers
import sim_utils
import numpy as np
import series_probs_approx as probs

# Merge in league structure, and compute playoff seeding
def process_sim_results(sim_results, played, league_structure, ratings):
    cur_standings = None
    if played is not None and len(played) > 0:
        cur_standings = sim_utils.compute_standings(played)

    standings = sim_utils.compute_standings_from_results(sim_results, cur_standings).reset_index()
    job_id = sim_results.iloc[0]['job_id']
    standings['job_id'] = job_id

    standings = sim_utils.add_run_ids(standings)

    # Merge in the div/lg data
    standings = pd.merge(left=standings, right=league_structure, left_on='team', right_index=True)
    standings = standings.set_index(['run_id', 'team'])[['W', 'L', 'wpct', 'div', 'lg']]

    # Merge in the ratings
    standings = pd.merge(left=standings, right=ratings, left_on='team', right_index=True)

    # compute div_wins and playoff seeds
    add_division_winners(standings, sim_results, played)
    add_lg_ranks(standings, sim_results, played)
    add_series_shares(standings, [], 'lds_shares', 0)
    add_series_shares(standings, ['lds_shares'], 'lcs_shares', 1)
    add_series_shares(standings, ['lcs_shares'], 'pennant_shares', 2)
    add_ws_shares(standings)
    add_p_home_game(standings)
    return standings

def summarize_results(standings):
    counts = standings.reset_index()[['team', 'lg_rank']].value_counts().unstack()
    wins = standings.groupby('team')['W'].agg(['sum', 'max', 'min', len])
    for col in ['pennant_shares', 'lds_shares', 'lcs_shares', 'ws_shares', 'p_home_game']:
        wins[col] = standings.groupby('team')[col].sum()
    summary = pd.merge(left=wins, right=counts, on='team', how='left')
    for col in counts.columns:
        summary[col] = summary[col].fillna(0).astype(int)
    
    return summary.rename(columns={i: f'r{i}' for i in range(100)})


def break_tie(tied_sets, sim_results, played):
    def get_games(row):
        cols = ['W', 'L']
        run_id = row['run_id']
        simmed = sim_results.query('run_id==@run_id')[cols]
        games = pd.concat([played[cols], simmed])
        return games

    def break_one_tie(row):
        games = get_games(row)
        h2h = sim_utils.h2h_standings(games, row['team'])
        return h2h.index
    
    tie_orders =  pd.Series(tied_sets.reset_index().apply(break_one_tie, axis=1)).rename('team')
    tie_orders.index = tied_sets.index
    return tie_orders


def add_division_winners(standings, sim_results, played):
    standings['div_win'] = False

    div_leading_wpct = standings.groupby(['run_id', 'div'])['wpct'].transform('max')
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
        # For each tied set, we just want the ['run_id', 'team'] of the winner, so we can set the div_win flag
        tie_winners = break_tie(tied_sets, sim_results, played).apply(lambda s: s[0]).reset_index().set_index(['run_id', 'team']).index
        standings.loc[tie_winners, 'div_win'] = True
    return standings


def add_lg_ranks(standings, sim_results, played):
    tied_tm_ct = standings.groupby(['run_id', 'lg', 'wpct'])['wpct'].transform('size')
    if sum(tied_tm_ct) > 0:
        tied_sets = standings[tied_tm_ct>1].reset_index().groupby(['run_id', 'lg', 'wpct'])['team'].apply(set)
        tie_orders = break_tie(tied_sets, sim_results, played).explode()
        # We need to take tie-orders (which are ordered lists) and convert them into a number we can use for sorting
        tiebreak = (15 - tie_orders.groupby(['run_id', 'lg', 'wpct']).cumcount())
        standings['tiebreak'] = pd.concat([tie_orders, tiebreak], axis=1).reset_index().set_index(['run_id', 'team'])[0]
        standings.fillna({'tiebreak': 0}, inplace=True)
    else:
        standings['tiebreak'] = 0

    standings['lg_rank'] = standings.sort_values(by=['div_win', 'wpct', 'tiebreak'], ascending=False).groupby(['run_id', 'lg']).cumcount()+1
    return standings

def add_p_home_game(standings):
    standings['p_home_game'] = np.where(standings['lg_rank']<=4, 1, standings['lds_shares'])


playoff_format = pd.read_csv('playoff_format.csv')

# This method computes the probabilities of advancement for a round of playoffs
# We've already enumerated all the possible matchups by seed (playoff_format). Then:
#   Merge that with the actual playoff fields from each run, to get
#     each possible team-vs-team matchup for each run.
#   Compute the likelihood of each team winning that series
#   Compute the probability of each series happening (e.g., both teams advancing to this round)
#   Combine the last two steps to compute the likelihood of each team advancing beyond this round
def add_series_shares(standings, likelihood_field_name, share_name, round_num):
    # Create a table with all the series to model
    potential_series = playoff_format.query('Round==@round_num')
    potential_series.columns = pd.MultiIndex.from_tuples([('Round', ''), ('Length', ''), ('h', 'seed'), ('a', 'seed')])
    series_teams = potential_series.reset_index().set_index(['index', 'Round', 'Length']).stack(0, future_stack=True)

    playoff_fields = standings.query('lg_rank<=6').rename(columns={'lg_rank': 'seed'})

    cols = ['run_id', 'team', 'wpct', 'lg', 'rating', 'seed', 'index', 'Round', 'Length', 'level_3'] + likelihood_field_name
    col_mapper = {'index': 'series_id', 'level_3': 'ha'}
    series_teams = pd.merge(left=playoff_fields.reset_index(), right=series_teams.reset_index(), on='seed')[cols].rename(columns=col_mapper)

    # compute the win probabilities
    index_cols = ['run_id', 'lg', 'series_id']

    # wrangle the teams back into a row per series, to compute the probs
    series_matchups = series_teams.set_index(index_cols + ['Length', 'ha'])[['rating'] + likelihood_field_name].unstack(-1)
    series_matchups = series_matchups.reset_index().set_index(index_cols)

    # now compute the win probs for each possible series matchup
    length = series_matchups['Length'].iloc[0]
    series_probs = probs.p_series(length, series_matchups['rating']['h'], series_matchups['rating']['a'])
    series_matchups[('p_win', 'h')] = series_probs
    series_matchups[('p_win', 'a')] = 1-series_probs

    # Now compute the actual likelihood of each matchup occurring, based on teams advancing this far
    likelihoods = 1 # If it's the first round, every series is 100% likely to happen
    if likelihood_field_name:
        likelihoods = series_matchups[likelihood_field_name].product(axis=1)

    # And each team's chance of winning by multiplying matchup likelihood by the team's win probability
    p_win_true = series_matchups['p_win'].multiply(likelihoods, axis=0).stack().rename('p_win')

    # now merge the probs back into the teams, and sum each team's probability from their various potential matchups
    series_teams = pd.merge(left=series_teams, right=p_win_true, left_on=index_cols+['ha'], right_index=True)
    p_advance = series_teams.groupby(['run_id', 'team'])['p_win'].sum().rename('p_advance')

    playoff_fields = pd.merge(left=playoff_fields, right=p_advance, how='left', left_index=True, right_index=True)
    playoff_fields.fillna({'p_advance': 1}, inplace=True)

    # Update the standings with the computed p_advance
    standings[share_name] = playoff_fields['p_advance']
    standings.fillna({share_name: 0}, inplace = True)
    return standings

# Every matchup between an NL team and an AL team is possible, so enumerate them
# Compute which team gets HFA
# Compute series win probability of each possible matchup
# Compute the likelihood of each possible matchup
# Combine the last two steps to compute the likelihood of each team advancing beyond this round
def add_ws_shares(standings):
    # Just get the run_id, team and lg of every playoff team
    playoff_fields = standings.query('lg_rank<=6')['lg'].reset_index()

    # Enumerate all the possible WS matchups
    series_matchups = pd.merge(left=playoff_fields.query('lg=="N"'), right=playoff_fields.query('lg=="A"'), on=['run_id'], suffixes=['_N', '_A'])
    series_matchups.index.name = 'series_id' # Use the default RangeIndex, but give it a name

    # Now break into one row per team per matchup, to merge in team data (['wpct', 'pennant_shares', 'lg', 'rating'])
    teams = pd.concat([series_matchups['team_N'].rename('team'), series_matchups['team_A'].rename('team')])
    teams_full  = pd.merge(left=teams, right=series_matchups['run_id'], on='series_id') # merge in run_id
    teams_full = pd.merge(left=teams_full.reset_index(), right=standings[['wpct', 'pennant_shares', 'lg', 'rating']], on=['team', 'run_id'])

    # Now back to one row per potential series
    all_ws = teams_full.set_index(['series_id', 'run_id', 'lg'])[['team', 'wpct', 'pennant_shares', 'rating']].unstack()

    # Compute the HFA for each matchup
    hfa = np.where(all_ws['wpct']['A'] > all_ws['wpct']['N'], 'A', 'N')

    # Compute the likelihood of each matchup occurring 
    likelihood = all_ws['pennant_shares'].product(axis=1)

    # Compute each team's w_prob in each potential matchup
    rating_home = pd.Series(np.where(hfa=="N", all_ws['rating']['N'], all_ws['rating']['A']))
    rating_away = pd.Series(np.where(hfa=="A", all_ws['rating']['N'], all_ws['rating']['A']))
    w_prob_h = probs.p_series(7, rating_home, rating_away)

    all_ws[('series_win_prob', 'A')] = np.where(hfa=="A", w_prob_h, 1-w_prob_h)
    all_ws[('series_win_prob', 'N')] = np.where(hfa=="N", w_prob_h, 1-w_prob_h)

    # Multiply each matchup's likelihood by each team's w_prob in that matchup, then sum by team
    ws_probs = all_ws['series_win_prob'].multiply(likelihood, axis=0)
    all_ws = pd.concat([all_ws, pd.concat([ws_probs], axis=1, keys=['ws_probs'])], axis=1)
    ws_shares = all_ws.stack(future_stack=True).groupby(['run_id', 'team'])['ws_probs'].sum()

    standings['ws_shares'] = ws_shares
    standings.fillna({'ws_shares': 0}, inplace=True)

    return standings