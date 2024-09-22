import datasource as ds
import random
import logging
import tiebreaker_impls

logger = logging.getLogger(__name__)
logging.basicConfig(filename='tiebreaker.log', level=logging.INFO)

# This checks whether a tie can definitively be broken among a set of teams
# And if so, it returns the tie order. Returns None otherwise
# For now this only considers H2H record in played games
# Does not consider intradvisional records
def __check_tie_breaker(teams):
    cur, remain = ds.get_games()
    h2h = tiebreaker_impls.h2h_standings(cur, teams)
    if h2h is not None and len(h2h) == 2:
        leader = h2h.iloc[0]
        gap = leader['W'] - leader['L']
        num_remaining = len(remain.query('team1 in @teams and team2 in @teams'))
        # This checks if one team has a clinched a >.500 record in H2H games
        # This logic is only correct in a 2-way tie
        # In a multi-way tie, this may yield a false positive (since multiple teams can finish >.500)
        if gap > num_remaining:
            return h2h.index.values

# This iterates over all possible two-way ties, checks if any are clinched, caching the values
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

# Adds a given tie-breaker ordering to the set of known tie-breakers
def __add_tie_breaker(tb, teams):
    k = tuple(sorted(teams))
    if k not in tb:
        val = list(teams)
        tb[k] = val

# This adds a set of "known" hard-coded tie-breakers, that can't be computed
def add_known_tie_breakers(tb):
    known_tie_breakers = [
    ]

    for tms in known_tie_breakers:
        __add_tie_breaker(tb, tms)


__clinched_tie_breakers = __find_all_clinched_tie_breakers()
add_known_tie_breakers(__clinched_tie_breakers)

def break_tie(teams, games):
    tms = tuple(sorted(teams))
    if tms in __clinched_tie_breakers:
        return __clinched_tie_breakers[tms]

    # For three-way ties, per MLB rules (https://www.mlb.com/news/mlb-playoff-tiebreaker-rules)
    # First see if any team wins both two-way tie-breakers
    # Then see if any team loses both two-way tie breakers
    if len(tms) == 3:
        t01 = break_tie(tuple((tms[0], tms[1])), games)
        t02 = break_tie(tuple((tms[0], tms[2])), games)
        t12 = break_tie(tuple((tms[1], tms[2])), games)

        # First see if any team wins both two-way tie-breakers
        if t01 is not None and t02 is not None and t12 is not None:
            tb = None
            if t01[0] == t02[0]: # 0 has both h2hs
                tb = [tms[0]] + list(t12)
            elif t01[0] == t12[0]: # 1 has both h2hs
                tb = [tms[1]] + list(t02)
            elif t02[0] == t12[0]: # 2 has both h2hs
                tb = [tms[2]] + list(t01)
            
            # Now see if either team has lost both tie-breakers
            if t01[1] == t02[1]: # 0 has lost both h2hs
                tb = list(t12) + [tms[0]]
            if t01[1] == t12[1]: # 1 has lost both h2hs
                tb = list(t02) + [tms[1]]
            if t02[1] == t12[1]: # 2 has lost both h2hs
                tb = list(t01) + [tms[2]]
            
            if tb is not None:
                return tb

    tie_breaker_funcs = [tiebreaker_impls.h2h_standings, 
                         lambda g, t: tiebreaker_impls.intradivisional_records(g, t, ds.league_structure),
                         lambda g, t: tiebreaker_impls.interdivisional_records(g, t, ds.league_structure)
                         ]

    # Recursively break ties of sub-groups
    def process_group(grp):
        if len(grp) == 1:
            return list(grp)
        else:
            return list(break_tie(set(grp), games))
    
    ordering = None
    for tb_func in tie_breaker_funcs:
        tb_output = tb_func(games, teams).reset_index()
        # If we have more than one unique value, then we don't need to iterate into further tie-breakers
        if tb_output['wpct'].nunique() > 1:
            # If any sub-groups of teams are still tied, we break the tie recursively
            grps = tb_output.groupby('wpct')
            if len(grps) == len(teams):
                ordering = tb_output['team'].values
            else:
                # sum() will make a list from a list of lists
                ordering = sum(grps['team'].apply(process_group).values, [])
            break;
    
    if ordering is not None:
        logger.info(f'broke tie among {teams} as {ordering} based on {tb_func}')
        return ordering


    # We have to return something when the tie is not broken
    logger.warn(f"unbroken tie {teams}")
    return random.shuffle(list(teams))


