# Licensed under a 3-clause BSD style license - see LICENSE.rst
import pytest
from numpy.testing import assert_allclose
from astropy.coordinates import Angle, SkyCoord
from regions import CircleSkyRegion
from gammapy.cube import MapDataset
from gammapy.cube.make import MapDatasetMaker, SafeMaskMaker, FoVBackgroundMaker
from gammapy.data import DataStore
from gammapy.maps import MapAxis, WcsGeom, WcsNDMap
from gammapy.utils.testing import requires_data

@pytest.fixture(scope="session")
def observations():
    """Example observation list for testing."""
    datastore = DataStore.from_dir("$GAMMAPY_DATA/hess-dl3-dr1/")
    obs_ids = [23523, 23526]
    return datastore.get_observations(obs_ids)


@pytest.fixture(scope="session")
def geom():
    energy_axis = MapAxis.from_edges([1, 10], unit="TeV", name="ENERGY", interp="log")
    return WcsGeom.create(
        skydir=SkyCoord(83.633, 22.014, unit="deg"),
        binsz=0.02,
        width=(10, 10),
        coordsys="GAL",
        proj="CAR",
        axes=[energy_axis],
    )


@pytest.fixture(scope="session")
def exclusion_mask(geom):
    """Example mask for testing."""
    pos = SkyCoord(83.633, 22.014, unit="deg", frame="icrs")
    region = CircleSkyRegion(pos, Angle(0.15, "deg"))
    exclusion = WcsNDMap.from_geom(geom)
    exclusion.data = geom.region_mask([region], inside=False)
    return exclusion

@requires_data()
def test_fov_bkg_maker(geom, observations, exclusion_mask):
    fov_bkg_maker = FoVBackgroundMaker(exclusion_mask=exclusion_mask)
    safe_mask_maker = SafeMaskMaker(methods=["offset-max"], offset_max="2 deg")
    map_dataset_maker = MapDatasetMaker(selection=["counts", "background", "exposure"])

    reference = MapDataset.create(geom)
    datasets = []

    for obs in observations:
        cutout = reference.cutout(obs.pointing_radec, width="4 deg")
        dataset = map_dataset_maker.run(cutout, obs)
        dataset = safe_mask_maker.run(dataset, obs)

        dataset = fov_bkg_maker.run(dataset)
        datasets.append(dataset)

    mask = dataset.mask_safe
    assert_allclose(datasets[0].counts_off.data[mask].sum(), 2511333)
    assert_allclose(datasets[1].counts_off.data[mask].sum(), 2143577.0)
    assert_allclose(datasets[0].acceptance_off.data[mask].sum(), 2961300, rtol=1e-5)
    assert_allclose(datasets[1].acceptance_off.data[mask].sum(), 2364657.2, rtol=1e-5)
    assert_allclose(datasets[0].alpha.data[0][100][100], 0.00063745599, rtol=1e-5)
    assert_allclose(
        datasets[0].exposure.data[0][100][100], 806254444.8480084, rtol=1e-5
    )
