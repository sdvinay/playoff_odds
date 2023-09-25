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

    # For three-way ties, per MLB rules (https://www.mlb.com/news/mlb-playoff-tiebreaker-rules)
    # First see if any team wins both two-way tie-breakers
    # Then see if any team loses both two-way tie breakers TODO
    if len(tms) == 3:
        t01 = __clinched_tie_breakers.get(tuple((tms[0], tms[1])))
        t02 = __clinched_tie_breakers.get(tuple((tms[0], tms[2])))
        t12 = __clinched_tie_breakers.get(tuple((tms[1], tms[2])))

        # First see if any team wins both two-way tie-breakers
        if t01 is not None and t02 is not None and t12 is not None:
            tb = None
            if t01[0] == t02[0]: # 0 has both h2hs
                tb = [tms[0]] + list(t12)
            if t01[0] == t12[0]: # 1 has both h2hs
                tb = [tms[1]] + list(t02)
            if t02[0] == t12[0]: # 2 has both h2hs
                tb = [tms[2]] + list(t01)
            
            if tb is not None:
                __clinched_tie_breakers[tms] = tb
                return tb
    return random.sample(tms, len(teams))

