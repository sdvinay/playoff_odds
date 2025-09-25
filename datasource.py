import pandas as pd

__INPUT_DIR = 'input_data'

# This is the source data for the mapping of teams to divisions/leagues
def __get_league_structure_impl():
    div_text = '''
    NLW: AZ COL LAD SD SF
    NLE: ATL MIA NYM PHI WSH
    ALW: SEA LAA HOU ATH TEX
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

def __read_input_table(filename_prefix, index_col):
    df = pd.read_csv(f'{__INPUT_DIR}/{filename_prefix}.csv').set_index(index_col)
    return df

def get_games():
    played = __read_input_table('cur', 'gamePk')
    remain = __read_input_table('remain', 'gamePk')
    # This is a temporary workaround for when the season is completed
    # It pretends some games are still unplayed
    if remain is not None and len(remain) == 0:
        total_gms = len(played)
        played = played.head(total_gms-400)
        remain = played.tail(400)[['team1', 'team2']]

    return (played, remain)

def get_ratings():
    ratings_df = __read_input_table('ratings', 'team')
    if ratings_df is not None:
        return ratings_df['rating']
    else:
        return None