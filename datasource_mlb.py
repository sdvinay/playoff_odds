import pandas as pd
import numpy as np
import requests
import os
import typer

from perf_utils import print_perf_counter 

SCHEDULE_URL = 'https://statsapi.mlb.com/api/v1/schedule'
TEAMS_URL = 'https://statsapi.mlb.com/api/v1/teams'
params = {'sportId': 1, 'season': 2025}

__INPUT_DIR = 'input_data'

app = typer.Typer(no_args_is_help=True)

@print_perf_counter
def __get_games_impl():
    # Get the MLB schedule from the MLB stats API
    schedule_data = requests.get(SCHEDULE_URL, params | {'hydrate': 'team'}).json()
    all_gms = pd.json_normalize(schedule_data['dates'], record_path=['games'])
    reg = all_gms.query('gameType=="R"')

    # Remove the stubs of games that were rescheduled or suspended
    if 'resumeDate' in reg:
        reg = reg.loc[reg.infer_objects().fillna(0).query('resumeDate==0 and rescheduleDate==0').index]
    reg = reg.set_index('gamePk')

    # Split out the games that have been played vs those remaining
    played_col_mapper = {'teams.home.team.abbreviation': 'team1', 'teams.away.team.abbreviation': 'team2', 
                        'teams.home.score': 'score1', 'teams.away.score': 'score2'}
    remain_col_mapper = {'teams.home.team.abbreviation': 'team1', 'teams.away.team.abbreviation': 'team2'}
    if 'isTie' in reg:
        played = reg.dropna(subset=['isTie']).copy() # filter to include only completed/current games
        played = played[played_col_mapper.keys()].rename(columns=played_col_mapper)
        for col in ['score1', 'score2']:
            played[col] = played[col].astype(int)
        played['margin'] = played['score1']-played['score2']
        played['W'] = np.where(played['margin']>0, played['team1'], played['team2'])
        played['L']  = np.where(played['margin']<0, played['team1'], played['team2'])

        remain = reg[~reg.index.isin(played.index)][remain_col_mapper.keys()].rename(columns=remain_col_mapper)
    else:
        played = None
        remain = reg[remain_col_mapper.keys()].rename(columns=remain_col_mapper)

    print(f'Schedule updated: {len(played)} games played and {len(remain)} games remaining') 
    return (played, remain)


# Pull rest-of-season and strength-of-schedule from FG to compute true talent
# Map from FG abbreviations to MLB's
# For compatibility with the rest of the system, return ratings on the ELO scale
# by converting regressed w% to ELO (based on research I've done in
# elo_vs_wpct.ipynb)
@print_perf_counter
def __get_ratings_mlb():
    teams_resp = requests.get(TEAMS_URL, params | {'hydrate': 'standings'}).json()
    records = pd.json_normalize(teams_resp['teams'], 
                            record_path=['record', 'records', 'expectedRecords'], 
                            meta=['abbreviation', ['record', 'wins'], ['record', 'losses']]).query('type=="xWinLoss"')
    records = records.rename(columns = {'abbreviation': 'team'}).set_index('team')
    comb_wins = records[['wins', 'record.wins']].mean(axis=1) # 'wins' is pythag wins
    g = records[['wins', 'losses']].sum(axis=1)
    regressed_wpct = (comb_wins+35)/(g+70)
    
    # Go from regressed wpct to ELO
    # ELO scales at 706*proj_wpct
    # We'll center it at 1500, so add 1147
    elo = regressed_wpct*706+1147
    ratings = elo.rename('rating')
    ratings.index.name = 'team'
    return ratings

@print_perf_counter
def __get_ratings_fangraphs():
    url = 'https://www.fangraphs.com/api/playoff-odds/odds?dateDelta=&projectionMode=2&standingsType=mlb'
    json_response = requests.get(url).json()
    proj = pd.json_normalize(json_response, max_level=1)
    df = proj[['abbName', 'endData.rosW', 'endData.sos']].rename(columns={'abbName': 'team'})
    df = df.replace({'team': {'SDP': 'SD', 'SFG': 'SF', 'ARI': 'AZ', 'TBR': 'TB', 'CHW': 'CWS', 'WSN': 'WSH', 'KCR': 'KC'}}).set_index(['team'])
    df['quality'] = df['endData.rosW'] + df['endData.sos'] - .5
    ratings = (df['quality']*706+1147).rename('rating')
    return ratings

__get_ratings_impl = __get_ratings_fangraphs


def __write_input_table(df, filename_prefix):
    if not os.path.exists (__INPUT_DIR):
        os.makedirs(__INPUT_DIR)
    input_file_path = f'{__INPUT_DIR}/{filename_prefix}.csv'
    if df is not None:
        df.to_csv(input_file_path)
    elif os.path.exists(input_file_path):
        os.remove(input_file_path)

@app.command()
def update_input_data():
    cur, remain = __get_games_impl()
    ratings = __get_ratings_impl()

    __write_input_table(cur, 'cur')
    __write_input_table(remain, 'remain')
    __write_input_table(ratings, 'ratings')

# this is a dummy; we need at least two Typer actions to avoid having a default behavior
@app.callback()
def callback():
    pass

if __name__ == "__main__":
    app()
