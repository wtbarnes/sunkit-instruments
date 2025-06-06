import os.path
import datetime

import numpy as np
import pandas
import pytest

import astropy.units as u
from astropy.time import TimeDelta

from sunpy import timeseries
from sunpy.time import is_time_equal, parse_time

from sunkit_instruments import lyra
from sunkit_instruments.data.test import rootdir

# Define location for test LYTAF database files
TEST_DATA_PATH = rootdir

# Define some test data for test_remove_lytaf_events()
TIME = parse_time(
    np.array(
        [
            datetime.datetime(2013, 2, 1) + datetime.timedelta(minutes=i)
            for i in range(120)
        ]
    )
)
CHANNELS = [np.zeros(len(TIME)) + 0.4, np.zeros(len(TIME)) + 0.1]
EMPTY_LYTAF = np.empty(
    (0,),
    dtype=[
        ("insertion_time", object),
        ("begin_time", object),
        ("reference_time", object),
        ("end_time", object),
        ("event_type", object),
        ("event_definition", object),
    ],
)
LYTAF_TEST = np.append(
    EMPTY_LYTAF,
    np.array(
        [
            (
                parse_time(datetime.datetime.fromtimestamp(1371459961)),
                parse_time(datetime.datetime.fromtimestamp(1359677220)),
                parse_time(datetime.datetime.fromtimestamp(1359677250)),
                parse_time(datetime.datetime.fromtimestamp(1359677400)),
                "LAR",
                "Large Angle Rotation.",
            )
        ],
        dtype=EMPTY_LYTAF.dtype,
    ),
)
LYTAF_TEST = np.append(
    LYTAF_TEST,
    np.array(
        [
            (
                parse_time(datetime.datetime.fromtimestamp(1371460063)),
                parse_time(datetime.datetime.fromtimestamp(1359681764)),
                parse_time(datetime.datetime.fromtimestamp(1359682450)),
                parse_time(datetime.datetime.fromtimestamp(1359683136)),
                "UV occ.",
                "Occultation in the UV spectrum.",
            )
        ],
        dtype=LYTAF_TEST.dtype,
    ),
)


@pytest.mark.remote_data
@pytest.mark.xfail
def test_split_series_using_lytaf():
    """
    test the downloading of the LYTAF file and subsequent queries.
    """
    # test split_series_using_lytaf
    # construct a dummy signal for testing purposes
    basetime = parse_time("2020-06-13 10:00")
    seconds = 3600*1
    dummy_time = basetime + TimeDelta(range(seconds) * u.second)
    dummy_data = np.random.random(seconds)
    lytaf_tmp = lyra.get_lytaf_events(
        "2020-06-13 10:00", "2020-06-13 23:00", combine_files=["ppt"]
    )
    split = lyra.split_series_using_lytaf(dummy_time, dummy_data, lytaf_tmp)
    assert isinstance(split, list)
    assert len(split) == 5
    assert is_time_equal(split[0]["subtimes"][0], parse_time("2020-06-13T10:00:00"))
    assert is_time_equal(split[0]["subtimes"][-1], parse_time("2020-06-13T10:01:51"))
    assert is_time_equal(split[-1]["subtimes"][0], parse_time("2020-06-13T10:54:22"))
    assert is_time_equal(split[-1]["subtimes"][-1], parse_time("2020-06-13T10:59:58"))

    # Test case when no LYTAF events found in time series.
    split_no_lytaf = lyra.split_series_using_lytaf(dummy_time, dummy_data, LYTAF_TEST)
    assert isinstance(split_no_lytaf, list)
    assert isinstance(split_no_lytaf[0], dict)
    assert not set(split_no_lytaf[0].keys()).symmetric_difference(
        {"subtimes", "subdata"}
    )
    assert np.all(split_no_lytaf[0]["subtimes"] == dummy_time)
    assert np.all(split_no_lytaf[0]["subdata"] == dummy_data)


@pytest.fixture
def lyra_ts():
    # Create sample TimeSeries
    lyrats = timeseries.TimeSeries(
        os.path.join(rootdir, "lyra_20150101-000000_lev3_std_truncated.fits.gz"),
        source="LYRA",
    )
    lyrats._data = pandas.DataFrame(
        index=TIME,
        data={
            "CHANNEL1": CHANNELS[0],
            "CHANNEL2": CHANNELS[1],
            "CHANNEL3": CHANNELS[0],
            "CHANNEL4": CHANNELS[1],
        },
    )
    return lyrats


@pytest.mark.remote_data
@pytest.mark.xfail
def test_remove_lytaf_events_from_timeseries(lyra_ts):
    """
    Test if artifact are correctly removed from a TimeSeries.
    """
    # Check correct errors are raised due to bad input
    with pytest.raises(AttributeError):
        ts_test = lyra.remove_lytaf_events_from_timeseries(
            [], force_use_local_lytaf=True
        )

    # Run remove_artifacts_from_timeseries, returning artifact status
    ts_test, artifact_status_test = lyra.remove_lytaf_events_from_timeseries(
        lyra_ts,
        artifacts=["LAR", "Offpoint"],
        return_artifacts=True,
        force_use_local_lytaf=True,
    )
    # Generate expected data by calling _remove_lytaf_events and
    # constructing expected dataframe manually.
    lyra_df = lyra_ts.to_dataframe()
    time, channels, artifact_status_expected = lyra._remove_lytaf_events(
        lyra_df.index,
        channels=[
            np.asanyarray(lyra_df["CHANNEL1"]),
            np.asanyarray(lyra_df["CHANNEL2"]),
            np.asanyarray(lyra_df["CHANNEL3"]),
            np.asanyarray(lyra_df["CHANNEL4"]),
        ],
        artifacts=["LAR", "Offpoint"],
        return_artifacts=True,
        force_use_local_lytaf=True,
    )
    dataframe_expected = pandas.DataFrame(
        index=time,
        data={
            "CHANNEL1": channels[0],
            "CHANNEL2": channels[1],
            "CHANNEL3": channels[2],
            "CHANNEL4": channels[3],
        },
    )
    # Assert expected result is returned
    pandas.testing.assert_frame_equal(ts_test.to_dataframe(), dataframe_expected)
    assert artifact_status_test.keys() == artifact_status_expected.keys()
    np.testing.assert_array_equal(
        artifact_status_test["lytaf"], artifact_status_expected["lytaf"]
    )
    np.testing.assert_array_equal(
        artifact_status_test["removed"], artifact_status_expected["removed"]
    )
    np.testing.assert_array_equal(
        artifact_status_test["not_removed"], artifact_status_expected["not_removed"]
    )
    assert artifact_status_test["not_found"] == artifact_status_expected["not_found"]

    # Run remove_artifacts_from_timeseries, without returning
    # artifact status
    ts_test = lyra.remove_lytaf_events_from_timeseries(
        lyra_ts, artifacts=["LAR", "Offpoint"], force_use_local_lytaf=True
    )
    # Assert expected result is returned
    pandas.testing.assert_frame_equal(ts_test.to_dataframe(), dataframe_expected)


@pytest.fixture
def local_cache(sunpy_cache):
    sunpy_cache = sunpy_cache("sunkit_instruments.lyra.lyra.cache")
    sunpy_cache.add(
        "http://proba2.oma.be/lyra/data/lytaf/annotation_lyra.db",
        os.path.join(TEST_DATA_PATH, "annotation_lyra.db"),
    )
    sunpy_cache.add(
        "http://proba2.oma.be/lyra/data/lytaf/annotation_manual.db",
        os.path.join(TEST_DATA_PATH, "annotation_manual.db"),
    )
    sunpy_cache.add(
        "http://proba2.oma.be/lyra/data/lytaf/annotation_ppt.db",
        os.path.join(TEST_DATA_PATH, "annotation_ppt.db"),
    )
    sunpy_cache.add(
        "http://proba2.oma.be/lyra/data/lytaf/annotation_science.db",
        os.path.join(TEST_DATA_PATH, "annotation_science.db"),
    )


def test_remove_lytaf_events_1(local_cache):
    """
    Test _remove_lytaf_events() with some artifacts found and others not.
    """
    # Run _remove_lytaf_events
    time_test, channels_test, artifacts_status_test = lyra._remove_lytaf_events(
        TIME,
        channels=CHANNELS,
        artifacts=["LAR", "Offpoint"],
        return_artifacts=True,
        force_use_local_lytaf=True,
    )
    # Generated expected result
    bad_indices = np.logical_and(
        TIME >= LYTAF_TEST["begin_time"][0], TIME <= LYTAF_TEST["end_time"][0]
    )
    bad_indices = np.arange(len(TIME))[bad_indices]
    time_expected = np.delete(TIME, bad_indices)
    channels_expected = [
        np.delete(CHANNELS[0], bad_indices),
        np.delete(CHANNELS[1], bad_indices),
    ]
    artifacts_status_expected = {
        "lytaf": LYTAF_TEST,
        "removed": LYTAF_TEST[0],
        "not_removed": LYTAF_TEST[1],
        "not_found": ["Offpoint"],
    }
    # Assert test values are same as expected
    np.testing.assert_array_equal(time_test, time_expected)
    assert (channels_test[0]).all() == (channels_expected[0]).all()
    assert (channels_test[1]).all() == (channels_expected[1]).all()
    assert artifacts_status_test.keys() == artifacts_status_expected.keys()
    np.testing.assert_array_equal(
        artifacts_status_test["lytaf"], artifacts_status_expected["lytaf"]
    )
    np.testing.assert_array_equal(
        artifacts_status_test["removed"], artifacts_status_expected["removed"]
    )
    np.testing.assert_array_equal(
        artifacts_status_test["not_removed"], artifacts_status_expected["not_removed"]
    )
    assert artifacts_status_test["not_found"] == artifacts_status_expected["not_found"]

    # Test that correct values are returned when channels kwarg not
    # supplied.
    # Run _remove_lytaf_events
    time_test, artifacts_status_test = lyra._remove_lytaf_events(
        TIME,
        artifacts=["LAR", "Offpoint"],
        return_artifacts=True,
        force_use_local_lytaf=True,
    )
    # Assert test values are same as expected
    assert np.all(time_test == time_expected)
    assert artifacts_status_test.keys() == artifacts_status_expected.keys()
    np.testing.assert_array_equal(
        artifacts_status_test["lytaf"], artifacts_status_expected["lytaf"]
    )
    np.testing.assert_array_equal(
        artifacts_status_test["removed"], artifacts_status_expected["removed"]
    )
    np.testing.assert_array_equal(
        artifacts_status_test["not_removed"], artifacts_status_expected["not_removed"]
    )
    assert artifacts_status_test["not_found"] == artifacts_status_expected["not_found"]


@pytest.mark.filterwarnings("ignore:unclosed database")
def test_remove_lytaf_events_2(local_cache):
    """
    Test _remove_lytaf_events() with no user artifacts found.
    """
    with pytest.warns(UserWarning, match="None of user supplied artifacts were found."):
        time_test, channels_test, artifacts_status_test = lyra._remove_lytaf_events(
            TIME,
            channels=CHANNELS,
            artifacts="Offpoint",
            return_artifacts=True,
            force_use_local_lytaf=True,
        )
    time_expected = TIME
    channels_expected = CHANNELS
    artifacts_status_expected = {
        "lytaf": LYTAF_TEST,
        "removed": EMPTY_LYTAF,
        "not_removed": LYTAF_TEST,
        "not_found": ["Offpoint"],
    }
    np.testing.assert_array_equal(time_test, time_expected)
    assert (channels_test[0]).all() == (channels_expected[0]).all()
    assert (channels_test[1]).all() == (channels_expected[1]).all()
    assert artifacts_status_test.keys() == artifacts_status_expected.keys()
    np.testing.assert_array_equal(
        artifacts_status_test["lytaf"], artifacts_status_expected["lytaf"]
    )
    np.testing.assert_array_equal(
        artifacts_status_test["removed"], artifacts_status_expected["removed"]
    )
    np.testing.assert_array_equal(
        artifacts_status_test["not_removed"], artifacts_status_expected["not_removed"]
    )
    assert artifacts_status_test["not_found"] == artifacts_status_expected["not_found"]

    # Test correct values are returned when return_artifacts kwarg not
    # supplied.
    # Case 1: channels kwarg is True
    # Run _remove_lytaf_events
    with pytest.warns(UserWarning, match="None of user supplied artifacts were found."):
        time_test, channels_test = lyra._remove_lytaf_events(
            TIME, channels=CHANNELS, artifacts=["Offpoint"], force_use_local_lytaf=True
        )
    assert np.all(time_test == time_expected)
    assert (channels_test[0]).all() == (channels_expected[0]).all()
    assert (channels_test[1]).all() == (channels_expected[1]).all()
    # Case 2: channels kwarg is False
    # Run _remove_lytaf_events
    with pytest.warns(UserWarning, match="None of user supplied artifacts were found."):
        time_test = lyra._remove_lytaf_events(
            TIME, artifacts=["Offpoint"], force_use_local_lytaf=True
        )
    assert np.all(time_test == time_expected)


def test_remove_lytaf_events_3(local_cache):
    """
    Test if correct errors are raised by _remove_lytaf_events().
    """
    with pytest.raises(TypeError):
        lyra._remove_lytaf_events(
            TIME, channels=6, artifacts=["LAR"], force_use_local_lytaf=True
        )
    with pytest.raises(ValueError):
        lyra._remove_lytaf_events(TIME, force_use_local_lytaf=True)
    with pytest.raises(TypeError):
        lyra._remove_lytaf_events(TIME, artifacts=[6], force_use_local_lytaf=True)
    with pytest.raises(ValueError):
        lyra._remove_lytaf_events(
            TIME,
            artifacts=["LAR", "incorrect artifact type"],
            force_use_local_lytaf=True,
        )


def test_get_lytaf_events(local_cache):
    """
    Test if LYTAF events are correctly downloaded and read in.
    """
    # Run get_lytaf_events
    lytaf_test = lyra.get_lytaf_events(
        "2008-01-01", "2014-01-01", force_use_local_lytaf=True
    )
    # Form expected result of extract_combined_lytaf
    insertion_time = [
        datetime.datetime.fromtimestamp(1371459961),
        datetime.datetime.fromtimestamp(1371460063),
        datetime.datetime.fromtimestamp(1371460411),
        datetime.datetime.fromtimestamp(1371460493),
        datetime.datetime.fromtimestamp(1371460403),
        datetime.datetime.fromtimestamp(1371470988),
        datetime.datetime.fromtimestamp(1371211791),
        datetime.datetime.fromtimestamp(1371212303),
    ]
    begin_time = [
        datetime.datetime.fromtimestamp(1359677220),
        datetime.datetime.fromtimestamp(1359681764),
        datetime.datetime.fromtimestamp(1360748513),
        datetime.datetime.fromtimestamp(1361115900),
        datetime.datetime.fromtimestamp(1361980964),
        datetime.datetime.fromtimestamp(1368581100),
        datetime.datetime.fromtimestamp(1371032084),
        datetime.datetime.fromtimestamp(1371158167),
    ]
    reference_time = [
        datetime.datetime.fromtimestamp(1359677250),
        datetime.datetime.fromtimestamp(1359682450),
        datetime.datetime.fromtimestamp(1360751528),
        datetime.datetime.fromtimestamp(1361116200),
        datetime.datetime.fromtimestamp(1361983979),
        datetime.datetime.fromtimestamp(1368582480),
        datetime.datetime.fromtimestamp(1371045475),
        datetime.datetime.fromtimestamp(1371162600),
    ]
    end_time = [
        datetime.datetime.fromtimestamp(1359677400),
        datetime.datetime.fromtimestamp(1359683136),
        datetime.datetime.fromtimestamp(1360754543),
        datetime.datetime.fromtimestamp(1361116320),
        datetime.datetime.fromtimestamp(1361986994),
        datetime.datetime.fromtimestamp(1368583080),
        datetime.datetime.fromtimestamp(1371050025),
        datetime.datetime.fromtimestamp(1371167100),
    ]
    event_type = [
        "LAR",
        "UV occ.",
        "Vis LED on",
        "M Flare",
        "UV LED on",
        "X Flare",
        "Off-limb event",
        "Unexplained feature",
    ]
    event_description = [
        "Large Angle Rotation.",
        "Occultation in the UV spectrum.",
        "Visual LED is turned on.",
        "M class solar flare.",
        "UV LED is turned on.",
        "X class solar flare.",
        "Off-limb event in SWAP.",
        "Unexplained feature.",
    ]
    lytaf_expected = np.empty(
        (8,),
        dtype=[
            ("insertion_time", object),
            ("begin_time", object),
            ("reference_time", object),
            ("end_time", object),
            ("event_type", object),
            ("event_definition", object),
        ],
    )
    lytaf_expected["insertion_time"] = insertion_time
    lytaf_expected["begin_time"] = begin_time
    lytaf_expected["reference_time"] = reference_time
    lytaf_expected["end_time"] = end_time
    lytaf_expected["event_type"] = event_type
    lytaf_expected["event_definition"] = event_description
    # Assert that extract_combined_lytaf gives the right result
    np.testing.assert_array_equal(lytaf_test, lytaf_expected)

    # Check correct error is raised if names of different lytaf files
    # are incorrectly input.
    with pytest.raises(ValueError):
        lytaf_test = lyra.get_lytaf_events(
            "2008-01-01",
            "2014-01-01",
            combine_files=["gigo"],
            force_use_local_lytaf=True,
        )


def test_get_lytaf_event_types(local_cache):
    """
    Test that LYTAF event types are printed.
    """
    lyra.get_lytaf_event_types()


def test_lytaf_event2string():
    """
    Test _lytaf_event2string() associates correct numbers and events.
    """
    out_test = lyra._lytaf_event2string(list(range(12)))
    assert out_test == [
        "LAR",
        "N/A",
        "UV occult.",
        "Vis. occult.",
        "Offpoint",
        "SAA",
        "Auroral zone",
        "Moon in LYRA",
        "Moon in SWAP",
        "Venus in LYRA",
        "Venus in SWAP",
    ]
    out_test_single = lyra._lytaf_event2string(1)
    assert out_test_single == ["LAR"]


def test_prep_columns():
    """
    Test whether _prep_columns correctly prepares data.
    """
    # Generate simple input data
    time_input = TIME[0:2]
    time_input.precision = 9
    channels_input = [CHANNELS[0][0:2], CHANNELS[1][0:2]]
    filecolumns_input = ["time", "channel0", "channel1"]

    # Test case when channels and filecolumns are supplied by user.
    string_time_test, filecolumns_test = lyra._prep_columns(
        time_input, channels_input, filecolumns_input
    )
    # Generate expected output and verify _prep_columns() works
    string_time_expected = np.array(time_input.isot)
    filecolumns_expected = ["time", "channel0", "channel1"]
    np.testing.assert_array_equal(string_time_test, string_time_expected)
    assert filecolumns_test == filecolumns_expected

    # Test case when channels supplied by user by not filecolumns
    string_time_test, filecolumns_test = lyra._prep_columns(time_input, channels_input)
    np.testing.assert_array_equal(string_time_test, string_time_expected)
    assert filecolumns_test == filecolumns_expected

    # Test case when neither channels nor filecolumns supplied by user
    string_time_test, filecolumns_test = lyra._prep_columns(time_input)
    np.testing.assert_array_equal(string_time_test, string_time_expected)
    assert filecolumns_test == ["time"]

    # Test correct exceptions are raised
    with pytest.raises(TypeError):
        string_time_test, filecolumns_test = lyra._prep_columns(
            time_input, channels_input, ["channel0", 1]
        )
    with pytest.raises(ValueError):
        string_time_test = lyra._prep_columns(time_input, filecolumns=filecolumns_input)
