import datasource as ds
import tiebreaker_impls

# This checks whether a team has clinced the H2H season series vs another team
# And if so, it returns the tie order. Returns None otherwise
def __check_tie_breaker(teams):
    cur, remain = ds.get_games()
    h2h = tiebreaker_impls.h2h_standings(cur, teams)
    if h2h is not None and len(teams) == 2:
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