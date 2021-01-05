from anndata import AnnData

import numpy as np

from squidpy.gr import moran, ripley_k, co_occurrence


# dummy_adata is now in conftest.py
def test_ripley_k(dummy_adata: AnnData):
    """
    check ripley score and shape
    """
    ripley_k(dummy_adata, cluster_key="cluster")

    # assert ripley in adata.uns
    assert "ripley_k_cluster" in dummy_adata.uns.keys()
    # assert unique clusters in both
    assert np.array_equal(dummy_adata.obs["cluster"].unique(), dummy_adata.uns["ripley_k_cluster"]["cluster"].unique())

    # TO-DO assess length of distances


def test_moran(dummy_adata: AnnData):
    """
    check ripley score and shape
    """
    # spatial_connectivity is missing
    moran(dummy_adata)

    # assert fdr correction in adata.uns
    assert "pval_sim_fdr_bh" in dummy_adata.var.columns


def test_co_occurrence(dummy_adata: AnnData):
    """
    check ripley score and shape
    """
    co_occurrence(dummy_adata, cluster_key="cluster")

    # assert occurrence in adata.uns
    assert "cluster_co_occurrence" in dummy_adata.uns.keys()
    assert "occ" in dummy_adata.uns["cluster_co_occurrence"].keys()
    assert "interval" in dummy_adata.uns["cluster_co_occurrence"].keys()

    # assert shapes
    arr = dummy_adata.uns["cluster_co_occurrence"]["occ"]
    assert arr.ndim == 3
    assert arr.shape[2] == 49
    assert arr.shape[1] == arr.shape[0] == dummy_adata.obs["cluster"].unique().shape[0]
