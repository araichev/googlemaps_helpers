from itertools import product
import math
import json

import numpy as np
import pandas as pd
import googlemaps


CRS_WGS84 = {'init' :'epsg:4326'}

def get_secret(key, secrets_path):
    """
    Open the JSON file at ``secrets_path``,
    and return the value corresponding to the given key.
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

def make_ids(n):
    """
    Return a list of ``n`` (integer) unique strings.
    """
    k = int(math.log10(n)) + 1  # Number of digits for padding IDs
    return ['s{num:0{pad}d}'.format(num=i, pad=k) for i in range(n)]

def to_df(matrix, origin_ids=None, destination_ids=None):
    """
    Given ``matrix``, a (decoded) JSON response to a Google Maps
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
    # Initialize DataFrame
    columns = ['origin_address', 'destination_address', 'origin_id',
      'destination_id', 'duration', 'distance']
    f = pd.DataFrame([], columns=columns)

    # Append addresses
    if not matrix['rows']:
        return f

    f['origin_address'], f['destination_address'] =  zip(
      *product(matrix['origin_addresses'], matrix['destination_addresses']))

    # Append IDs
    if origin_ids is None:
        origin_ids = make_ids(len(matrix['origin_addresses']))

    if destination_ids is None:
        destination_ids = make_ids(len(matrix['destination_addresses']))

    f['origin_id'], f['destination_id'] =  zip(
      *product(origin_ids, destination_ids))

    # Append durations and distances
    if 'duration_in_traffic' in matrix['rows'][0]['elements'][0]:
        dur_key = 'duration_in_traffic'
    else:
        dur_key = 'duration'
    durs = []
    dists = []
    for r in matrix['rows']:
        for e in r['elements']:
            if e['status'] == 'OK':
                durs.append(e[dur_key]['value'])
                dists.append(e['distance']['value'])
            else:
                durs.append(None)
                dists.append(None)
    f['duration'] = durs
    f['distance'] = dists

    return f

def build_distance_matrix_df(client, origin_gdf, destination_gdf,
  origin_id_col=None, destination_id_col=None,
  include_selfies=False, chunk_size=100, **distance_matrix_kwargs):
    """
    Compute the duration-distance matrix between all pairs of origin
    and destination points given.
    To do this, call the Google Maps Distance Matrix API repeatedly.
    Group the calls into ``chunk_size``-to-1 chunks.
    If ``include_selfies``, then skip entries where the origin equals the destination.

    INPUT:
        - client: google-maps-services-python Client instance
        - orig_gdf: GeoDataFrame; origin points
        - dest_gdf: GeoDataFrame; destination points
        - orig_id_col: string; name of ID column in ``orig_gdf``
        - dest_id_col : string; name of ID column in ``dest_gdf``
        - departure_time: string; see :func:`get_matrix`
        - chunk_size: integer; max number of origin-destination rows per matrix query
        - matrix_kwargs: dictionary; keyword arguments for Google Maps Distance Matrix API

    OUTPUT:
        A DataFrame of the form...

    NOTES:
        - Sleeps for 1 second after every call to :func:`get_matrix` to stay within API usage limits
    """
    # Initialize origin and destination GeoDataFrames
    o_gdf = origin_gdf.copy()
    if o_gdf.crs != CRS_WGS84:
        o_gdf = o_gdf.to_crs(CRS_WGS84)
    if origin_id_col is None:
        origin_id_col = 'temp_id'
        o_gdf[origin_id_col] = make_ids(o_gdf.shape[0])

    d_gdf = destination_gdf.copy()
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
