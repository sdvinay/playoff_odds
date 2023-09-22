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
            return leader.name
        

def __find_all_clinched_tie_breakers():
    clinched_tie_breakers = {}
    for lg in ds.league_structure['lg'].unique():
        tms = ds.league_structure.query("lg==@lg").index
        for tm1 in tms:
            for tm2 in tms:
                if tm1 < tm2:
                    tb = __check_tie_breaker([tm1, tm2])
                    if tb:
                        clinched_tie_breakers[(tm1, tm2)] = tb
    return clinched_tie_breakers

__clinched_tie_breakers = __find_all_clinched_tie_breakers()
__clinched_tie_breakers[('SEA', 'TOR')] = 'SEA'
__clinched_tie_breakers[('BOS', 'SEA')] = 'SEA'
__clinched_tie_breakers[('BAL', 'TEX')] = 'BAL'
__clinched_tie_breakers[('CIN', 'MIA')] = 'MIA'
__clinched_tie_breakers[('MIA', 'SF')] = 'SF'

def break_tie(teams):
    tms = tuple(sorted(teams))
    if tms in __clinched_tie_breakers:
        winner = __clinched_tie_breakers[tms]
        return [winner] + [tm for tm in tms if tm != winner]
    return random.sample(tms, len(teams))

