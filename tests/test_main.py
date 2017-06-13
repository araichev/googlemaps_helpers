
import pytest
import geopandas as gpd
import responses

from .context import googlemaps_extras, DATA_DIR
from googlemaps_extras import *


client = googlemaps.Client(key='AIzaasdf')


def test_flip_coords():
    xy = [('a', 'b'), ('c', 'd')]
    yx = flip_coords(xy)
    assert yx == [('b', 'a'), ('d', 'c')]

def test_make_ids():
    n = 3
    ids = make_ids(n)
    assert len(ids) == n
    assert isinstance(ids[n - 1], str)

def test_to_df():
    r0 = {'status': 'OK', 'rows': []}
    r1 = {
        'destination_addresses': [
            '26 Ben Nevis Pl, Northpark, Auckland 2013, New Zealand'
        ],
        'origin_addresses': [
            '9 Waverley Ave, Glenfield, Auckland 0629, New Zealand',
            '919 Mount Eden Rd, Mount Eden, Auckland 1024, New Zealand'
        ],
        'rows': [
            {'elements': [{'distance': {'text': '31.5 km', 'value': 31495},
                'duration': {'text': '38 mins', 'value': 2304},
                'duration_in_traffic': {'text': '49 mins', 'value': 2936},
                'status': 'OK'}]},
            {'elements': [{'distance': {'text': '18.6 km', 'value': 18597},
                'duration': {'text': '29 mins', 'value': 1739},
                'duration_in_traffic': {'text': '41 mins', 'value': 2489},
                'status': 'OK'}]}
        ],
        'status': 'OK'
     }

    for r in [r0, r1]:
        f = to_df(r)
        assert isinstance(f, pd.DataFrame)
        assert f.shape[0] == len(r['rows'])
        expect_cols = ['origin_address', 'destination_address',
          'origin_id', 'destination_id', 'duration', 'distance']
        assert set(f.columns) == set(expect_cols)

@responses.activate
def test_build_matrix_df():
    # Create mock response to Google Matrix API call
    path = DATA_DIR/'points_response.json'
    with path.open() as src:
        body = src.read()

    responses.add(responses.GET,
      'https://maps.googleapis.com/maps/api/distancematrix/json',
      body=body, status=200, content_type='application/json'
    )

    # Test points
    path = DATA_DIR/'points.geojson'
    points = gpd.read_file(str(path))

    f = build_distance_matrix_df(client, points, points)
    n = points.shape[0]
    assert isinstance(f, pd.DataFrame)
    assert f.shape[0] == n**2 - n
    expect_cols = ['origin_address', 'destination_address',
      'origin_id', 'destination_id', 'duration', 'distance']
    assert set(f.columns) == set(expect_cols)

    f = build_distance_matrix_df(client, points, points, include_selfies=True)
    n = points.shape[0]
    assert isinstance(f, pd.DataFrame)
    assert f.shape[0] == n**2
    expect_cols = ['origin_address', 'destination_address',
      'origin_id', 'destination_id', 'duration', 'distance']
    assert set(f.columns) == set(expect_cols)

