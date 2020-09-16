"""Functions for neighborhood enrichment analysis (permutation test, assortativity measures etc.)
"""

import numpy as np
from itertools import product, combinations
import pandas as pd

def _count_observations_by_pairs(conn, leiden, positions):
    obs = []
    leiden_labels_unique = set(leiden)
    for i, j in combinations(leiden_labels_unique, r=2):
        x = positions[leiden == i]
        y = positions[leiden == j]
        x, y = np.array(list(product(x, y)))[:, 0].flatten(), np.array(list(product(x, y)))[:, 1].flatten()
        # print(conn[x, y])
        obs.append([i, j, int(sum(conn[x, y]).sum())])

    obs = pd.DataFrame(obs, columns=['leiden.i', 'leiden.j', 'n.obs'])
    obs['k'] = obs['leiden.i'].astype(str) + ":" + obs['leiden.j'].astype(str) 
    obs = obs.sort_values('n.obs', ascending=False)
    return obs

def permutation_test_leiden_pairs(adata: "AnnData",
                            n_permutations: int = 10,
                            key_added: str ='nhood_permutation_test'
                           ):
    leiden = adata.obs['leiden']
    conn = adata.obsp['spatial_connectivity']
    
    """
    Calculate enrichment/depletion of observed leiden pairs in the spatial connectivity graph, versus permutations as background.
    Params
    ------
    adata
        The AnnData object.
    n_permutations
        Number of shuffling and recalculations to be done.
    key_added
        Key added to output dataframe in adata.uns.
    """
    
    conn = adata.obsp['spatial_connectivity']
    N = adata.shape[0]
    positions = np.arange(N) # .reshape(w, h)
    X = np.array(leiden).astype(int) # np.random.randint(1, 10, size=(w, h))

    # real observations
    print('calculating pairwise enrichment/depletion on real data...')
    df = _count_observations_by_pairs(conn, leiden, positions)
    
    # permutations
    leiden_rand = leiden.copy()
    perm = []
    print('calculating pairwise enrichment/depletion permutations...')
    for pi in range(n_permutations):
        if (pi + 1) % 2 == 0:
            print('%i out of %i permutations' % (pi, n_permutations))
        np.random.shuffle(leiden_rand)
        obs_perm = _count_observations_by_pairs(conn, leiden_rand, positions)
        obs_perm['permutation.i'] = True
        perm.append(obs_perm)
    perm = pd.concat(perm)
    
    # statistics
    n_by_leiden = leiden.to_dict()
    mean_by_k = perm.groupby('k').mean()['n.obs'].to_dict()
    std_by_k = perm.groupby('k').std()['n.obs'].to_dict()
    
    
    mu = df['k'].map(mean_by_k)
    sigma = df['k'].map(std_by_k)
    df['n.i'] = df['leiden.i'].map(n_by_leiden)
    df['n.j'] = df['leiden.j'].map(n_by_leiden)
    df['z.score'] = (df['n.obs'] - mu) / sigma
    df['n.exp'] = mu
    df['sigma'] = sigma
    df.sort_values('z.score', ascending=False)
    
    adata.uns[key_added] = df