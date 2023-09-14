import pandas as pd
import requests

SCHEDULE_URL = 'https://statsapi.mlb.com/api/v1/schedule'
TEAMS_URL = 'https://statsapi.mlb.com/api/v1/teams'
params = {'sportId': 1, 'season': 2023}

def get_games_impl():
    # Get the MLB schedule from the MLB stats API
    schedule_data = requests.get(SCHEDULE_URL, params | {'hydrate': 'team'}).json()
    all_gms = pd.json_normalize(schedule_data['dates'], record_path=['games']).set_index('gamePk')
    reg = all_gms.query('gameType=="R"')

    # Remove the stubs of games that were rescheduled or suspended
    remove = pd.concat([reg['resumeDate'].dropna(), reg['rescheduleDate'].dropna()]).index
    reg = reg[~reg.index.isin(remove)]

    # Split out the games that have been played vs those remaining
    played_col_mapper = {'teams.home.team.abbreviation': 'team1', 'teams.away.team.abbreviation': 'team2', 
                        'teams.home.score': 'score1', 'teams.away.score': 'score2'}
    played = reg.dropna(subset=['isTie']).copy() # filter to include only completed/current games
    played = played[played_col_mapper.keys()].rename(columns=played_col_mapper)
    for col in ['score1', 'score2']:
        played[col] = played[col].astype(int)

    remain_cols = {'teams.home.team.abbreviation': 'team1', 'teams.away.team.abbreviation': 'team2'}
    remain = reg[~reg.index.isin(played.index)][remain_cols.keys()].rename(columns=remain_cols)

    return (played, remain)


# For the teams' quality ratings, take the mean of actual w% and pythag w%,
# and regress by 35 wins and 35 losses (based on research I've done)
# For compatibility with the rest of the system, return ratings on the ELO scale
# by converting regressed w% to ELO (based on research I've done in
# elo_vs_wpct.ipynb)
def get_ratings_impl():
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


(cur, remain) = get_games_impl()
ratings = get_ratings_impl()

def get_games():
    return (cur, remain)

def get_ratings():
    return ratings


# This is the source data for the mapping of teams to divisions/leagues
def get_league_structure_impl():
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

league_structure = get_league_structure_impl()
