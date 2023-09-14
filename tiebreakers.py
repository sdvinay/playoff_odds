import datasource_mlb as ds
import sim_utils

def check_tie_breaker(teams):
    cur, remain = ds.get_games()
    h2h = sim_utils.h2h_standings(cur, teams)
    if len(h2h) > 0:
        leader = h2h.iloc[0]
        gap = leader['W'] - leader['L']
        num_remaining = len(remain.query('team1 in @teams and team2 in @teams'))
        if gap > num_remaining:
            return leader.name
        

def find_all_clinched_tie_breakers():
    clinched_tie_breakers = {}
    for lg in ds.league_structure['lg'].unique():
        tms = ds.league_structure.query("lg==@lg").index
        for tm1 in tms:
            for tm2 in tms:
                if tm1 < tm2:
                    tb = check_tie_breaker([tm1, tm2])
                    if tb:
                        clinched_tie_breakers[(tm1, tm2)] = tb
    return clinched_tie_breakers

clinched_tie_breakers = find_all_clinched_tie_breakers()
clinched_tie_breakers[('SEA', 'TOR')] = 'SEA'
clinched_tie_breakers[('BOS', 'SEA')] = 'SEA'
clinched_tie_breakers[('BAL', 'TEX')] = 'BAL'
clinched_tie_breakers[('CIN', 'MIA')] = 'MIA'
clinched_tie_breakers[('MIA', 'SF')] = 'SF'

