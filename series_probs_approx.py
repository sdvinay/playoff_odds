# Approximate the probabilities instead of computing them
# Based on the analysis in approximate_series_probs.ipynb

def p_series(games, r_home, r_away):
    consts = {3: {'intercept': 0.55156, 'coeffs': [ 2.1364e-03, -7.7766e-07, -1.0786e-08]},
        5: {'intercept': 0.51293, 'coeffs': [ 2.6860e-03, -2.8315e-07, -2.0100e-08]},
        7: {'intercept': 0.51075, 'coeffs': [ 3.1303e-03, -3.0320e-07, -3.0410e-08]}}

    diff = r_home - r_away
    diff_sq = diff * diff
    diff_cu = diff * diff * diff

    cs = consts[games]
    p = cs['intercept'] + diff * cs['coeffs'][0] + diff_sq * cs['coeffs'][1] + diff_cu * cs['coeffs'][2]
    return p