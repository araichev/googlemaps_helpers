from itertools import product
import math
from collections import OrderedDict
from pathlib import Path
import logging

import pandas as pd
import numpy as np
import geopandas as gpd
import shapely.geometry as sg
import googlemaps


# Configure logging
logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter(
  '%(asctime)s %(name)-12s %(levelname)-8s \n%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

WGS84 = {'init': 'epsg:4326'}
# Maximum number of elements in a Google Maps Distance Matrix API query
MAX_ELEMENTS = 100

def flip_coords(xy_list):
    """
    Given a list of coordinate pairs, swap the first and second
    coordinates and return the resulting list.
    """
    return [(y, x) for (x, y) in xy_list]

def make_ids(n, prefix='row_'):
    """
    Return a list of ``n`` (integer) unique strings of the form
    ``prefix``<number>.
    """
    k = int(math.log10(n)) + 1  # Number of digits for padding
    return [prefix + '{num:0{pad}d}'.format(num=i, pad=k) for i in range(n)]

def to_df(distance_matrix_response, origin_ids=None, destination_ids=None):
    """
    Given a (decoded) JSON response to a Google Maps
    Distance Matrix API call, convert it into a DataFrame with the
    following columns.

    - ``'origin_address'``
    - ``'origin_id'``: ID of origin; defaults to an element of
      :func:`make_ids`
    - ``'destination_address'``
    - ``'destination_id'``: ID of destination; defaluts to an element of
      :func:`make_ids`
    - ``'duration'``: time from origin to destination; includes
      time in traffic if that's available in the response
    - ``'distance'``: distance from origin to destination

    The origin and destination addresses in the response can optionally
    be assigned IDs by setting ``origin_ids`` (list of strings) and
    ``destination_ids`` (list of strings).
    """
    # Initialize
    r = distance_matrix_response
    columns = ['origin_address', 'destination_address', 'origin_id',
      'destination_id', 'duration', 'distance']
    f = pd.DataFrame([], columns=columns)

    # Append addresses
    if not r['rows']:
        return f

    f['origin_address'], f['destination_address'] =  zip(
      *product(r['origin_addresses'], r['destination_addresses']))

    # Append IDs
    if origin_ids is None:
        origin_ids = make_ids(len(r['origin_addresses']))

    if destination_ids is None:
        destination_ids = make_ids(len(r['destination_addresses']))

    f['origin_id'], f['destination_id'] =  zip(
      *product(origin_ids, destination_ids))

    # Append durations and distances
    durs = []
    dists = []
    for row in r['rows']:
        for e in row['elements']:
            if e['status'] == 'OK':
                if 'duration_in_traffic' in e:
                    dur_key = 'duration_in_traffic'
                else:
                    dur_key = 'duration'
                durs.append(e[dur_key]['value'])
                dists.append(e['distance']['value'])
            else:
                durs.append(np.nan)
                dists.append(np.nan)
    f['duration'] = durs
    f['distance'] = dists

    return f

def point_df_to_gdf(f, x_col='lon', y_col='lat', from_crs=WGS84):
    """
    Given a DataFrame of points with x coordinates
    in the column ``x_col`` and y coordinates in the column ``y_col``,
    with respect to the GeoPandas coordinate reference system
    ``from_crs`` (dictionary), convert the DataFrame into a GeoDataFrame
    with that coordinate reference system and with a ``'geometry'``
    column that corresponds to the points.
    Delete the original x and y columns, and return the result.
    """
    f = f.copy()
    f['geometry'] = f[[x_col, y_col]].apply(lambda p: sg.Point(p), axis=1)
    f = f.drop([x_col, y_col], axis=1)
    f = gpd.GeoDataFrame(f)
    f.crs = from_crs
    return f

def point_gdf_to_df(f, x_col='lon', y_col='lat', to_crs=WGS84):
    """
    The inverse of :func:`point_df_to_gdf`.
    Given a GeoDataFrame of points, convert to the coordinate reference
    system ``to_crs`` (dictionary), then split its ``'geometry'`` column
    into x coordinates in the column ``x_col`` and y coordinates in the
    columns ``y_col``, deleting the ``'geometry'`` column afterwards.
    Coerce the result into a DataFrame and return it.
    """
    f = f.copy()
    if f.crs is None:
        raise ValueError('GeoDataFrame needs a crs attribute')
    if f.crs != to_crs:
        f = f.to_crs(to_crs)

    f[x_col], f[y_col] = zip(*f['geometry'].map(lambda p: p.coords[0]))
    del f['geometry']
    return pd.DataFrame(f)

def build_distance_matrix_df(client, origins_gdf, destinations_gdf,
  origin_id_col=None, destination_id_col=None,
  max_elements=MAX_ELEMENTS, **distance_matrix_kwargs):
    """
    Compute the duration-distance matrix between the given origins
    and destinations, assuming that the number of origins multiplied
    by the number of destinations is at most ``max_elements``.
    To do this, call the Google Maps Distance Matrix API once.

    INPUT:

    - ``client``: google-maps-services-python Client instance
    - ``origins_gdf``: GeoDataFrame of point; the origins
    - ``destinations_gdf``: GeoDataFrame of points; the destinations
    - ``origin_id_col``: string; name of ID column in ``origins_gdf``
    - ``destination_id_col``: string; name of ID column in
      ``destinations_gdf``
    - ``max_elements``: integer; max number of elements allowable in
      one Google Maps Distance Matrix API call
    - ``distance_matrix_kwargs``: dictionary; keyword arguments for
      Google Maps Distance Matrix API

    OUTPUT:

    A DataFrame of the form output by :func:`to_df` where the origins
    come from ``origins_gdf`` and the destinations come from
    ``destinations_gdf``.

    Return an empty DataFrame with the expected column names if an
    HTTPError on Timeout exception occurs.
    """
    # Initialize origin and destinations GeoDataFrames
    o_gdf = origins_gdf.copy()
    d_gdf = destinations_gdf.copy()

    n = o_gdf.shape[0]*d_gdf.shape[0]
    if n > max_elements:
        raise ValueError('Number of origins times number of destinations '
          'is {}, which exceeds threshold of {} elements'.format(
          n, max_elements))

    # Prepare origin data
    if o_gdf.crs != WGS84:
        o_gdf = o_gdf.to_crs(WGS84)
    if origin_id_col is None:
        origin_id_col = 'temp_id'
        o_gdf[origin_id_col] = make_ids(o_gdf.shape[0])

    o_locs = [geo.coords[0] for geo in o_gdf['geometry']]
    o_ids = o_gdf[origin_id_col].values

    # Prepare destination data
    if d_gdf.crs != WGS84:
        d_gdf = d_gdf.to_crs(WGS84)
    if destination_id_col is None:
        destination_id_col = 'temp_id'
        d_gdf[destination_id_col] = make_ids(d_gdf.shape[0])

    d_locs = [geo.coords[0] for geo in d_gdf['geometry']]
    d_ids = d_gdf[destination_id_col].values

    # Get matrix info
    try:
        r = client.distance_matrix(flip_coords(o_locs),
          flip_coords(d_locs), **distance_matrix_kwargs)
        f = to_df(r, o_ids, d_ids)
    except (googlemaps.exceptions.HTTPError, googlemaps.exceptions.Timeout):
        # Empty DataFrame
        f =  pd.DataFrame(columns=[
            'origin_address',
            'origin_id',
            'destination_address',
            'destination_id',
            'duration',
            'distance',
        ])

    return f

def run_distance_matrix_job(client, origins_gdf, destinations_gdf, out_dir,
  origin_id_col=None, destination_id_col=None,
  max_elements=MAX_ELEMENTS, **distance_matrix_kwargs):
    """
    Compute the duration-distance matrix between the given origins
    and destinations.
    To do this, call the Google Maps Distance Matrix API repeatedly,
    ensuring that each call uses no more than ``max_elements`` elements.

    INPUT:

    - ``client``: google-maps-services-python Client instance
    - ``origins_gdf``: GeoDataFrame of points; the origins
    - ``destinations_gdf``: GeoDataFrame of points; the destinations
    - ``out_dir``: string or Path object of a directory at which
      to store the output files; create the directory if it does not
      exist
    - ``origin_id_col``: string; name of ID column in ``origins_gdf``
    - ``destination_id_col``: string; name of ID column in
      ``destinations_gdf``
    - ``max_elements``: integer; max number of elements allowable in
      one Google Maps Distance Matrix API call
    - ``distance_matrix_kwargs``: dictionary; keyword arguments for
      Google Maps Distance Matrix API

    OUTPUT:

    A collection of CSV files located at ``out_dir`` of the form output
    by :func:`to_df`, where the origins comes from ``origins_gdf`` and
    the destinations come from ``destinations_gdf``.
    Each file will contains one origin points and at most
    ``max_elements`` destination points, for a total of at most
    ``max_elements`` rows.
    An empty DataFrame with the expected column names will be saved to
    file if an HTTPError on Timeout exception occurs.
    This can happen if, for example, the daily query limit is exceeded.
    """
    o_gdf = origins_gdf.copy()
    d_gdf = destinations_gdf.copy()

    n_o = o_gdf.shape[0]
    n_d = d_gdf.shape[0]

    # Create IDs if necessary
    if origin_id_col is None:
        origin_id_col = 'ersatz_origin_id'
        o_gdf[origin_id_col] = make_ids(n_o, 'orig_row_')

    if destination_id_col is None:
        destination_id_col = 'ersatz_destination_id'
        d_gdf[destination_id_col] = make_ids(n_d, 'dest_row_')

    # Get mode for logging
    mode = distance_matrix_kwargs.get('mode', 'driving')

    # Make output directory if it does not exist
    out_dir = Path(out_dir)
    if not out_dir.exists():
        out_dir.mkdir(parents=True)

    # Iterate through origins.
    # For each origin segment all destinations into chunks of size
    # at most ``max_elements``.
    # For each destination chunk, build a one-to-many matrix from the
    # origin to all the destinations in the chunk and save it to file.
    for ix, orig_id in o_gdf[[origin_id_col]].itertuples():
        logger.info('Working on origin {} of {} (id {})'.format(
          ix + 1, n_o, orig_id))

        # Chunk destinations and build one-to-many matrices from origin
        # to destination chunks.
        # A failed attempt (e.g. through API usage over limit)
        # will build an empty matrix
        for j in range(math.ceil(n_d/max_elements)):
            n1 = max_elements*j
            n2 = min(max_elements*(j + 1), n_d)
            dest_id1, dest_id2 = (
                d_gdf[destination_id_col].iat[n1],
                d_gdf[destination_id_col].iat[n2 - 1]
            )
            path = Path(out_dir)/'{}_from_{}_to_{}--{}.csv'.format(
              mode, orig_id, dest_id1, dest_id2)
            f = build_distance_matrix_df(client, o_gdf.loc[ix:ix],
              d_gdf.iloc[n1:n2],
              origin_id_col=origin_id_col,
              destination_id_col=destination_id_col,
              **distance_matrix_kwargs)
            f.to_csv(path, index=False)

            if f.empty:
                logger.info('* Failed to get data for ' + path.stem)

def compute_cost(n, cost=0.5/1000, num_freebies=0,
  daily_limit=100000, chunk_size=MAX_ELEMENTS):
    """
    Estimate the cost of a sequence of Google Maps Distance Matrix
    queries comprising a total of n elements at ``cost`` USD per
    element, where the first ``num_freebies`` (integer) elements are
    free.
    Return a Series that includes the cost and some other metadata.
    """
    d = OrderedDict()
    d['#elements'] = n
    d['exceeds {!s}-element daily limit?'.format(daily_limit)] = (
        n > daily_limit)
    d['estimated cost for job in USD'] = max(0, n - num_freebies)*cost
    d['estimated duration for job in minutes'] = n/chunk_size/60
    return pd.Series(d)
