from itertools import product
import math
import json
from pathlib import Path
from collections import OrderedDict

import numpy as np
import pandas as pd
import geopandas as gpd
import shapely.geometry as sg


CRS_WGS84 = {'init' :'epsg:4326'}

def get_secret(key, secrets_path):
    """
    Open the JSON file at ``secrets_path``,
    and return the value corresponding to the given key.
    Good for retrieving your API key.
    """
    secrets_path = Path(secrets_path)
    with secrets_path.open() as src:
        secrets = json.load(src)
    return secrets[key]

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
    if 'duration_in_traffic' in r['rows'][0]['elements'][0]:
        dur_key = 'duration_in_traffic'
    else:
        dur_key = 'duration'
    durs = []
    dists = []
    for row in r['rows']:
        for e in row['elements']:
            if e['status'] == 'OK':
                durs.append(e[dur_key]['value'])
                dists.append(e['distance']['value'])
            else:
                durs.append(None)
                dists.append(None)
    f['duration'] = durs
    f['distance'] = dists

    return f

def point_df_to_gdf(f, x_col='lon', y_col='lat', from_crs=CRS_WGS84):
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

def point_gdf_to_df(f, x_col='lon', y_col='lat', to_crs=CRS_WGS84):
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
  include_selfies=False, chunk_size=100, **distance_matrix_kwargs):
    """
    Compute the duration-distance matrix between all pairs of origin
    and destination points given.
    To do this, call the Google Maps Distance Matrix API repeatedly
    with calls of size ``one-to-chunk_size``.

    INPUT:

    - ``client``: google-maps-services-python Client instance
    - ``origins_gdf``: GeoDataFrame of points; the origins
    - ``destinations_gdf``: GeoDataFrame of points; the destinations
    - ``origin_id_col``: string; name of ID column in ``origins_gdf``
    - ``destination_id_col``: string; name of ID column in
      ``destinations_gdf``
    - ``include_selfies``: boolean; include entries where the origin
      equals the destination if and only if this is true
    - ``chunk_size``: integer; max number of origin-destination rows
      per matrix query
    - ``matrix_kwargs``: dictionary; keyword arguments for Google Maps
      Distance Matrix API

    OUTPUT:

    A DataFrame of the form output by :func:`to_df` where the origins
    come from ``origins_gdf`` and the destinations come from
    ``destinations_gdf``.
    """
    # Initialize origin and destination GeoDataFrames
    o_gdf = origins_gdf.copy()
    if o_gdf.crs != CRS_WGS84:
        o_gdf = o_gdf.to_crs(CRS_WGS84)
    if origin_id_col is None:
        origin_id_col = 'temp_id'
        o_gdf[origin_id_col] = make_ids(o_gdf.shape[0])

    d_gdf = destinations_gdf.copy()
    if d_gdf.crs != CRS_WGS84:
        d_gdf = d_gdf.to_crs(CRS_WGS84)
    if destination_id_col is None:
        destination_id_col = 'temp_id'
        d_gdf[destination_id_col] = make_ids(d_gdf.shape[0])

    # Call Google Maps Distance Matrix API
    frames = []
    status = 'OK'
    num_chunks = math.ceil(o_gdf.shape[0]/chunk_size)
    for o_id, o_geom in o_gdf[[origin_id_col, 'geometry']].itertuples(
      index=False):
        # Get single origin
        o_locs = [o_geom.coords[0]]
        o_ids = [o_id]

        # Get destinations in chunks
        if include_selfies:
            f = d_gdf.copy()
        else:
            cond = d_gdf['geometry'] != o_geom
            f = d_gdf[cond].copy()

        for chunk in np.array_split(f, num_chunks):
            d_locs = [geo.coords[0] for geo in chunk['geometry']]
            d_ids = chunk[destination_id_col].values

            # Quit if bad status
            if status != 'OK':
                print('Quitting because of bad status:', status)
                break

            # Get matrix
            try:
                r = client.distance_matrix(flip_coords(o_locs),
                  flip_coords(d_locs), **distance_matrix_kwargs)
                if r['status'] != 'OK':
                    break
                df = to_df(r, o_ids, d_ids)
            except:
                df = pd.DataFrame()
                df['origin_address'] = np.nan
                df['origin_id'] = o_ids
                df['destination_address'] = np.nan
                df['destination_id'] = d_ids
                df['duration_address'] = np.nan
                df['distance'] = np.nan
            frames.append(df)

    # Concatenate matrices
    return pd.concat(frames)

def cost_build_distance_matrix_df(n, cost=0.5/1000, num_freebies=0,
  daily_limit=10000, chunk_size=100):
    """
    Estimate the cost of a Google Maps Distance Matrix query
    with n elements at ``cost`` USD per element where the first
    ``num_freebies`` (integer) elements are free.
    Return a Series that includes the cost and some other metadata.
    """
    d = OrderedDict()
    d['#elements'] = n
    d['exceeds {!s}-element daily limit?'.format(daily_limit)
      ] = n > daily_limit
    d['estimated cost for job in USD'] = max(0, n - num_freebies)*cost
    d['estimated duration for job in minutes'] = n/chunk_size/60
    return pd.Series(d)
