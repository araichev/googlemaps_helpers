import geopandas as gpd
import responses

from .context import googlemaps_helpers, DATA_DIR
from googlemaps_helpers import *


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

def test_point_df_to_gdf():
    f = pd.DataFrame([
        ['bingo', 172.5, -36],
        ['bongo', 172.7 -36.5],
    ], columns=['id', 'lon', 'lat'])
    g = point_df_to_gdf(f)
    assert isinstance(g, gpd.GeoDataFrame)
    assert g.shape[0] == f.shape[0]
    assert set(g.columns) == set(['id', 'geometry'])
    assert g.crs == CRS_WGS84

def test_point_gdf_to_df():
    g = gpd.GeoDataFrame([
        ['bingo', sg.Point([172.5, -36])],
        ['bongo', sg.Point([172.7, -36.5])],
    ], columns=['id', 'geometry'])
    g.crs = CRS_WGS84
    f = point_gdf_to_df(g, x_col='x', y_col='y', to_crs={'init': 'epsg:2193'})
    assert isinstance(f, pd.DataFrame)
    assert f.shape[0] == g.shape[0]
    assert set(f.columns) == set(['id', 'x', 'y'])

@responses.activate
def test_build_distance_matrix_df():
    # Load test points
    path = DATA_DIR/'points.geojson'
    points = gpd.read_file(str(path))
    n = points.shape[0]

    # Create mock response to Google Matrix API call
    path = DATA_DIR/'points_response.json'
    with path.open() as src:
        body = src.read()

    responses.add(responses.GET,
      'https://maps.googleapis.com/maps/api/distancematrix/json',
      body=body, status=200, content_type='application/json'
    )

    f = build_distance_matrix_df(client, points, points)
    assert isinstance(f, pd.DataFrame)
    assert f.shape[0] == n**2 - n
    expect_cols = ['origin_address', 'destination_address',
      'origin_id', 'destination_id', 'duration', 'distance']
    assert set(f.columns) == set(expect_cols)

    # Create different mock response to Google Matrix API call
    path = DATA_DIR/'points_response_include_selfies.json'
    with path.open() as src:
        body = src.read()

    responses.reset()
    responses.add(responses.GET,
      'https://maps.googleapis.com/maps/api/distancematrix/json',
      body=body, status=200, content_type='application/json'
    )

    f = build_distance_matrix_df(client, points, points, include_selfies=True)
    assert isinstance(f, pd.DataFrame)
    assert f.shape[0] == n**2
    expect_cols = ['origin_address', 'destination_address',
      'origin_id', 'destination_id', 'duration', 'distance']
    assert set(f.columns) == set(expect_cols)

def test_cost_build_distance_matrix_df():
    s = cost_build_distance_matrix_df(10)
    assert isinstance(s, pd.Series)
    assert s.size == 4