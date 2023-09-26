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
    # two-way ties with tied h2h records, broken by intradivisional record
    tb[('SEA', 'TOR')] = ['SEA', 'TOR']
    tb[('MIN', 'TOR')] = ['MIN', 'TOR']
    tb[('BOS', 'SEA')] = ['SEA', 'BOS']
    tb[('BAL', 'TEX')] = ['BAL', 'TEX']
    tb[('CIN', 'MIA')] = ['MIA', 'CIN']
    tb[('MIA', 'SF')]  = ['SF', 'MIA']
    tb[('CIN', 'SD')]  = ['SD', 'CIN']
    tb[('DET', 'LAA')]  = ['DET', 'LAA']

    # two-way ties that haven't been clinched yet, but will for the tie be to relevant
    tb[('CHC', 'MIL')]  = ['CHC', 'MIL']
    tb[('HOU', 'SEA', 'TEX')] = ['SEA', 'TEX', 'HOU']


    # three-ways where all the two-ways are cycles, broken by h2h record (and clinched)
    tb[('AZ', 'MIA', 'SD')] = ['SD', 'MIA', 'AZ']
    tb[('CHC', 'MIA', 'SD')] = ['SD', 'MIA', 'CHC']
    tb[('CHC', 'MIA', 'SF')] = ['CHC', 'MIA', 'SF'] # this one came to intradivision record
    tb[('AZ', 'CIN', 'SD')] = ['CIN', 'SD', 'AZ']
    tb[('AZ', 'CIN', 'SF')] = ['AZ', 'SF', 'CIN']
    tb[('CHC', 'CIN', 'SD')] = ['CIN', 'CHC', 'SD']
    tb[('CHC', 'CIN', 'SF')] = ['CHC', 'CIN', 'SF']
    tb[('HOU', 'TEX', 'TOR')] = ['HOU', 'TEX', 'TOR']
    tb[('HOU', 'MIN', 'TOR')] = ['MIN', 'TOR', 'HOU']
    tb[('MIN', 'SEA', 'TEX')] = ['TEX', 'MIN', 'SEA']

    # four-ways settled on common h2h records (I'm not sure this is correct)
    tb[('AZ', 'CIN', 'MIA', 'SD')] = ['CIN', 'SD', 'MIA', 'AZ']
    tb[('AZ', 'CHC', 'MIA', 'SD')] = ['AZ', 'MIA', 'SD', 'CHC']
    tb[('AZ', 'CHC', 'MIA', 'SF')] = ['MIA', 'AZ', 'CHC', 'SF']
    tb[('AZ', 'CHC', 'CIN', 'SD')] = ['AZ', 'CIN', 'SD', 'CHC']
    tb[('CHC', 'CIN', 'MIA', 'SD')] = ['SD', 'CIN', 'MIA', 'CHC']
    tb[('AZ', 'CHC', 'CIN', 'SF')] = ['AZ', 'CIN', 'CHC', 'SF']
    tb[('AZ', 'CHC', 'CIN', 'MIA')] = ['MIA', 'AZ', 'CIN', 'CHC']
    tb[('MIN', 'SEA', 'TEX', 'TOR')] = ['TEX', 'MIN', 'TOR', 'SEA'] #not sure this one is clinched
    tb[('HOU', 'MIN', 'SEA', 'TOR')] = ['SEA', 'MIN', 'TOR', 'HOU'] #not sure this one is clinched


    # five-way (same)
    tb[('AZ', 'CHC', 'CIN', 'MIA', 'SD')] = ['AZ', 'MIA', 'CIN', 'SD', 'CHC']
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
            elif t01[0] == t12[0]: # 1 has both h2hs
                tb = [tms[1]] + list(t02)
            elif t02[0] == t12[0]: # 2 has both h2hs
                tb = [tms[2]] + list(t01)
            else: # That means we have a cycle, so look at common h2h record
                tb = __check_tie_breaker(tms)
            
            if tb is not None:
                __clinched_tie_breakers[tms] = tb
                return tb
            
            # Now see if either team has lost both tie-breakers
            if t01[1] == t02[1]: # 0 has lost both h2hs
                tb = list(t12) + [tms[0]]
            if t01[1] == t12[1]: # 1 has lost both h2hs
                tb = list(t02) + [tms[1]]
            if t02[1] == t12[1]: # 2 has lost both h2hs
                tb = list(t01) + [tms[2]]
            
            if tb is not None:
                __clinched_tie_breakers[tms] = tb
                return tb
    #print(f'Breaking tie randomly among {tms}')
    return random.sample(tms, len(teams))

