import pandas as pd
import numpy as np
import requests
from dataclasses import dataclass
import warnings
import os

SCHEDULE_URL = 'https://statsapi.mlb.com/api/v1/schedule'
TEAMS_URL = 'https://statsapi.mlb.com/api/v1/teams'
params = {'sportId': 1, 'season': 2024}

__CACHE_DIR = 'mlbapi_cache'

@dataclass
class __internal_cache_struct:
    cur: pd.DataFrame
    remain: pd.DataFrame
    ratings: pd.Series

__internal_cache = __internal_cache_struct(None, None, None)

def __get_games_impl():
    # Get the MLB schedule from the MLB stats API
    schedule_data = requests.get(SCHEDULE_URL, params | {'hydrate': 'team'}).json()
    all_gms = pd.json_normalize(schedule_data['dates'], record_path=['games'])
    reg = all_gms.query('gameType=="R"')

    # Remove the stubs of games that were rescheduled or suspended
    if 'resumeDate' in reg:
        reg = reg.loc[reg.fillna(0).query('resumeDate==0 and rescheduleDate==0').index]
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
    
    return (played, remain)


# Pull rest-of-season and strength-of-schedule from FG to compute true talent
# Map from FG abbreviations to MLB's
# For compatibility with the rest of the system, return ratings on the ELO scale
# by converting regressed w% to ELO (based on research I've done in
# elo_vs_wpct.ipynb)
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

def __read_table_from_cache(filename_prefix, index_col):
    try:
        df = pd.read_csv(f'{__CACHE_DIR}/{filename_prefix}.csv').set_index(index_col)
    except FileNotFoundError:
        warnings.warn("mlbapi_cache files missing; run datasource_mlb::rebuild_cache() to rebuild", Warning)
        df = None
    return df


def __write_table_to_cache(df, filename_prefix):
    if not os.path.exists (__CACHE_DIR):
        os.makedirs(__CACHE_DIR)
    cache_file_path = f'{__CACHE_DIR}/{filename_prefix}.csv'
    if df is not None:
        df.to_csv(cache_file_path)
    elif os.path.exists(cache_file_path):
        os.remove(cache_file_path)

def __get_games_from_cache():
    played = __read_table_from_cache('cur', 'gamePk')
    remain = __read_table_from_cache('remain', 'gamePk')
    # This is a temporary workaround for when the season is completed
    # It pretends some games are still unplayed
    if remain is not None and len(remain) == 0:
        total_gms = len(played)
        played = played.head(total_gms-400)
        remain = played.tail(400)[['team1', 'team2']]

    return (played, remain)

def __get_ratings_from_cache():
    ratings_df = __read_table_from_cache('ratings', 'team')
    if ratings_df is not None:
        return ratings_df['rating']
    else:
        return None

def rebuild_cache():
    __internal_cache.cur, __internal_cache.remain = __get_games_impl()
    __internal_cache.ratings = __get_ratings_impl()

    __write_table_to_cache(__internal_cache.cur, 'cur')
    __write_table_to_cache(__internal_cache.remain, 'remain')
    __write_table_to_cache(__internal_cache.ratings, 'ratings')

(__internal_cache.cur, __internal_cache.remain) = __get_games_from_cache()
__internal_cache.ratings = __get_ratings_from_cache()

def get_games():
    return (__internal_cache.cur, __internal_cache.remain)

def get_ratings():
    return __internal_cache.ratings


# This is the source data for the mapping of teams to divisions/leagues
def __get_league_structure_impl():
    div_text = '''
    NLW: AZ COL LAD SD SF
    NLE: ATL MIA NYM PHI WSH
    ALW: SEA LAA HOU OAK TEX
    ALE: TB TOR BAL NYY BOS
    ALC: MIN CWS CLE KC DET
    NLC: STL MIL CHC PIT CIN
    '''

    lines = [line.strip().split(': ') for line in div_text.strip().split('\n')]
    div_map = {l[0]: l[1].split(' ') for l in lines} # a map of div names to lists of team names
    div = pd.concat([pd.Series({team: div for team in teams}) for (div, teams) in div_map.items()])
    teams = pd.DataFrame()
    teams['div'] = div
    teams['lg'] = teams['div'].str[0]
    return teams

league_structure = __get_league_structure_impl()
