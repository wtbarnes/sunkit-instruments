import os

import numpy as np
import pytest

import sunpy.map

from sunkit_instruments import iris
from sunkit_instruments.data.test import rootdir

try:
    from sunpy.util.exceptions import SunpyMetadataWarning
except ImportError:
    from sunpy.util.exceptions import SunpyUserWarning as SunpyMetadataWarning


def test_SJI_to_sequence():
    test_data = os.path.join(
        rootdir, "iris_l2_20130801_074720_4040000014_SJI_1400_t000.fits"
    )
    iris_cube = iris.SJI_to_sequence(test_data, start=0, stop=None, hdu=0)

    assert isinstance(iris_cube, sunpy.map.MapSequence)
    assert isinstance(iris_cube.maps[0], sunpy.map.sources.SJIMap)
    assert len(iris_cube.maps) == 2
    assert iris_cube.maps[0].meta["DATE-OBS"] != iris_cube.maps[1].meta["DATE-OBS"]


def test_iris_rot():
    test_data = os.path.join(
        rootdir, "iris_l2_20130801_074720_4040000014_SJI_1400_t000.fits"
    )
    iris_cube = iris.SJI_to_sequence(test_data, start=0, stop=None, hdu=0)
    irismap = iris_cube.maps[0]
    with pytest.warns(SunpyMetadataWarning, match="Missing metadata for observer"):
        irismap_rot = irismap.rotate()

    assert isinstance(irismap_rot, sunpy.map.sources.SJIMap)

    np.testing.assert_allclose(irismap_rot.meta["pc1_1"], 1)
    np.testing.assert_allclose(irismap_rot.meta["pc1_2"], 0, atol=1e-7)
    np.testing.assert_allclose(irismap_rot.meta["pc2_1"], 0, atol=1e-7)
    np.testing.assert_allclose(irismap_rot.meta["pc2_2"], 1)
