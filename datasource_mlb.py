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


def get_ratings_impl():
    teams_resp = requests.get(TEAMS_URL, params | {'hydrate': 'standings'}).json()
    teams_df = pd.json_normalize(teams_resp['teams'])
    ratings = teams_df.set_index('abbreviation')['record.winningPercentage'].rename('rating').astype(float)
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
