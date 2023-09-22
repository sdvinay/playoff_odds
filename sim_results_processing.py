import pandas as pd
import tiebreakers
import sim_utils
import playoff_simulator as psim

# Merge in league structure, and compute playoff seeding
def process_sim_results(sim_results, played, league_structure, ratings):
    cur_standings = sim_utils.compute_standings(played)
    standings = sim_utils.compute_standings_from_results(sim_results, cur_standings).reset_index()
    job_id = sim_results.iloc[0]['job_id']
    standings['job_id'] = job_id

    standings = sim_utils.add_run_ids(standings)
    standings['wpct'] = standings['W'] / (standings['W'] + standings['L'])

    # Merge in the div/lg data
    standings = pd.merge(left=standings, right=league_structure, left_on='team', right_index=True)
    standings = standings.set_index(['run_id', 'team'])[['W', 'L', 'wpct', 'div', 'lg']]

    # Merge in the ratings
    standings = pd.merge(left=standings, right=ratings, left_on='team', right_index=True)

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

