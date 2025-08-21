import random
import logging
import tiebreaker_impls
import tiebreakers_clinched

logger = logging.getLogger(__name__)
logging.basicConfig(filename='logs/tiebreaker.log', level=logging.INFO)


def break_tie(teams, games):
    tms = tuple(sorted(teams))
    if tms in tiebreakers_clinched.__clinched_tie_breakers:
        tb = tiebreakers_clinched.__clinched_tie_breakers[tms] 
        logger.info(f'broke tie among {teams} as {tb} based on clinched h2h tie-breaker')
        return tb

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
            elif t01[1] == t02[1]: # 0 has lost both h2hs
                tb = list(t12) + [tms[0]]
            elif t01[1] == t12[1]: # 1 has lost both h2hs
                tb = list(t02) + [tms[1]]
            elif t02[1] == t12[1]: # 2 has lost both h2hs
                tb = list(t01) + [tms[2]]
            
            if tb is not None:
                logger.info(f'broke tie among {teams} as {tb} based on multiple two-way tiebreakers')
                return tb

    tie_breaker_funcs = [tiebreaker_impls.h2h_standings, 
                         tiebreaker_impls.intradivisional_records,
                         tiebreaker_impls.interdivisional_records
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


    # We have to return something when the tie is not broken, so return a random ordering
    logger.warn(f"unbroken tie {teams}")
    ordering = list(teams)
    random.shuffle(ordering)
    return ordering


