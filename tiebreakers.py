import datasource_mlb as ds
import sim_utils
import random

def __check_tie_breaker(teams):
    cur, remain = ds.get_games()
    h2h = sim_utils.h2h_standings(cur, teams)
    if len(h2h) > 0:
        leader = h2h.iloc[0]
        gap = leader['W'] - leader['L']
        num_remaining = len(remain.query('team1 in @teams and team2 in @teams'))
        if gap > num_remaining:
            return h2h.index.values
        

def __find_all_clinched_tie_breakers():
    clinched_tie_breakers = {}
    for lg in ds.league_structure['lg'].unique():
        tms = ds.league_structure.query("lg==@lg").index
        for tm1 in tms:
            for tm2 in tms:
                if tm1 < tm2:
                    tb = __check_tie_breaker([tm1, tm2])
                    if tb is not None:
                        clinched_tie_breakers[(tm1, tm2)] = tb
    return clinched_tie_breakers

def add_known_tie_breakers(tb):
    tb[('SEA', 'TOR')] = ['SEA', 'TOR']
    tb[('BOS', 'SEA')] = ['SEA', 'BOS']
    tb[('BAL', 'TEX')] = ['BAL', 'TEX']
    tb[('CIN', 'MIA')] = ['MIA', 'CIN']
    tb[('MIA', 'SF')]  = ['SF', 'MIA']

__clinched_tie_breakers = __find_all_clinched_tie_breakers()
add_known_tie_breakers(__clinched_tie_breakers)

def break_tie(teams):
    tms = tuple(sorted(teams))
    if tms in __clinched_tie_breakers:
        return __clinched_tie_breakers[tms]
    return random.sample(tms, len(teams))

