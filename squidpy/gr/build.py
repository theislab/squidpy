"""Functions for building gr from spatial coordinates."""
from typing import Tuple, Union, Optional
import warnings

from scanpy import logging as logg
from anndata import AnnData

from scipy.sparse import csr_matrix, SparseEfficiencyWarning
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from squidpy._docs import d, inject_docs
from squidpy.gr._utils import _save_data, _assert_positive, _assert_spatial_basis
from squidpy.constants._constants import CoordType, Transform
from squidpy.constants._pkg_constants import Key


@d.dedent
@inject_docs(t=Transform, c=CoordType)
def spatial_neighbors(
    adata: AnnData,
    spatial_key: str = Key.obsm.spatial,
    coord_type: Optional[Union[str, CoordType]] = None,
    n_rings: int = 1,
    n_neigh: int = 6,
    radius: Optional[float] = None,
    transform: Optional[Union[str, Transform]] = None,
    key_added: Optional[str] = None,
) -> None:
    """
    Create a graph from spatial coordinates.

    Parameters
    ----------
    %(adata)s
    %(spatial_key)s
    coord_type
        Type of coordinate system. Can be one of the following:

            - `{c.VISIUM!r}`: [Visium]_ coordinates.
            - `{c.GENERIC!r}`: generic coordinates.

        If `None`, use `{c.VISIUM!r}` if ``spatial_key`` is present in :attr:`anndata.AnnData.obsm`,
        otherwise use `{c.GENERIC!r}`.
    n_rings
        Number of rings of neighbors for [Visium]_ data.
    n_neigh
        Number of neighborhoods to consider for non-Visium data.
    radius
        Radius of neighbors for non-Visium data.
    transform
        Type of adjacency matrix transform. Valid options are:

            - `{t.SPECTRAL.s!r}` - TODO
            - `{t.COSINE.s!r}` - TODO
            - `{t.NONE.v}` - TODO

    key_added
        Key which controls where the results are saved.

    Returns
    -------
    Modifies the ``adata`` with the following keys:

        - :attr:`anndata.AnnData.obsp` ``['{{key_added}}_connectivities']`` - TODO
        - :attr:`anndata.AnnData.obsp` ``['{{key_added}}_distances']`` - TODO
        - :attr:`anndata.AnnData.uns`  ``['{{key_added}}']`` - TODO
    """
    _assert_positive(n_rings, name="n_rings")
    _assert_positive(n_neigh, name="n_neigh")
    _assert_spatial_basis(adata, spatial_key)

    transform = Transform.NONE if transform is None else Transform(transform)
    if coord_type is None:
        coord_type = CoordType.VISIUM if Key.uns.spatial in adata.uns else CoordType.GENERIC
    else:
        coord_type = CoordType(coord_type)

    start = logg.info(f"Creating graph using `{coord_type}` coordinates and `{transform}` transform")

    coords = adata.obsm[spatial_key]
    if coord_type == CoordType.VISIUM:
        if n_rings > 1:
            Adj: csr_matrix = _build_connectivity(coords, 6, neigh_correct=True, set_diag=True, return_distance=False)
            Res = Adj
            Walk = Adj
            for i in range(n_rings - 1):
                Walk = Walk @ Adj
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", SparseEfficiencyWarning)
                    Walk[Res.nonzero()] = 0.0
                Walk.eliminate_zeros()
                Walk.data[:] = i + 2.0
                Res = Res + Walk
            Adj = Res
            Adj.setdiag(0.0)
            Adj.eliminate_zeros()

            Dst = Adj.copy()
            Adj.data[:] = 1.0
        else:
            Adj = _build_connectivity(coords, 6, neigh_correct=True)
            Dst = None

    elif coord_type == CoordType.GENERIC:
        Adj, Dst = _build_connectivity(coords, n_neigh, radius, return_distance=True)
    else:
        raise NotImplementedError(coord_type)

    # check transform
    if transform == Transform.SPECTRAL:
        Adj = _transform_a_spectral(Adj)
    elif transform == Transform.COSINE:
        Adj = _transform_a_cosine(Adj)
    elif transform == Transform.NONE:
        pass
    else:
        raise NotImplementedError(transform)

    key_added = Key.uns.spatial_neighs(key_added)
    conns_key = Key.obsp.spatial_conn(key_added)
    dists_key = Key.obsp.spatial_dist(key_added)

    neighbors_dict = {
        "connectivities_key": conns_key,
        "params": {"n_neighbors": n_neigh, "coord_type": coord_type.v, "radius": radius, "transform": transform.v},
    }

    _save_data(adata, attr="obsp", key=conns_key, data=Adj)
    if Dst is not None:
        _save_data(adata, attr="obsp", key=dists_key, data=Dst, prefix=False)
        neighbors_dict["distances_key"] = dists_key

    _save_data(adata, attr="uns", key=key_added, data=neighbors_dict, prefix=False, time=start)


def _build_connectivity(
    coords: np.ndarray,
    n_neigh: int,
    radius: Optional[float] = None,
    neigh_correct: bool = False,
    set_diag: bool = False,
    return_distance: bool = False,
) -> Union[Tuple[csr_matrix, csr_matrix], csr_matrix]:
    """Build connectivity matrix from spatial coordinates."""
    N = coords.shape[0]

    dists_m = None

    tree = NearestNeighbors(n_neighbors=n_neigh or 6, radius=radius or 1, metric="euclidean")
    tree.fit(coords)

    if radius is not None:
        results = tree.radius_neighbors()
        dists = np.concatenate(results[0])
        row_indices = np.concatenate(results[1])
        lengths = [len(x) for x in results[1]]
        col_indices = np.repeat(np.arange(N), lengths)
    else:
        results = tree.kneighbors()
        dists, row_indices = (result.reshape(-1) for result in results)
        col_indices = np.repeat(np.arange(N), n_neigh or 6)
        if neigh_correct:
            dist_cutoff = np.median(dists) * 1.3  # There's a small amount of sway
            mask = dists < dist_cutoff
            row_indices, col_indices = row_indices[mask], col_indices[mask]
            dists = dists[mask]

    if return_distance:
        dists_m = csr_matrix((dists, (row_indices, col_indices)), shape=(N, N))

    if set_diag:
        row_indices = np.concatenate((row_indices, np.arange(N)))
        col_indices = np.concatenate((col_indices, np.arange(N)))

    conns_m = csr_matrix((np.ones(len(row_indices)), (row_indices, col_indices)), shape=(N, N))

    return (conns_m, dists_m) if return_distance else conns_m


def _transform_a_spectral(a: Union[csr_matrix, np.ndarray]) -> np.ndarray:
    degrees = np.squeeze(np.array(np.sqrt(1.0 / a.sum(axis=0))))
    return a.multiply(np.outer(degrees, degrees))


def _transform_a_cosine(a: Union[csr_matrix, np.ndarray]) -> np.ndarray:
    return cosine_similarity(a, dense_output=False)
