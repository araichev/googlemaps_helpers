Google Maps Helpers
********************
.. image:: https://travis-ci.org/mrcagney/googlemaps_helpers.svg?branch=master
    :target: https://travis-ci.org/mrcagney/googlemaps_helpers

A tiny Python 3.5+ library of helpers that use the `Google Maps API Python client <https://github.com/googlemaps/google-maps-services-python>`_.
Only incorporates the Distance Matrix API at present.
Use the library to run small or large jobs with inputs as GeoPandas GeoDataFrames and outputs as Pandas DataFrames.


Installation
=============
``pipenv install git+https://github.com/mrcagney/googlemaps_helpers#egg=googlemaps_helpers``


Usage
======
See the Jupyter notebook at ``ipynb/examples.ipynb``.


Authors
========
- Alex Raichev, 2017-06-13


Notes
======
- Development status is Alpha
- This project uses semantic versioning


History
========

1.1.0, 2018-05-15
------------------
- Added the function ``run_distance_matrix_job`` to run a job requiring multiple API calls


1.0.2, 2018-05-14
------------------
- Replace ``None`` with ``numpy.nan`` in function ``to_df``.


1.0.1, 2018-05-14
------------------
- Bugfixed the handling of ``'duration_in_traffic'`` key in the function ``to_df``.


1.0.0, 2018-05-11
------------------
- Simplified API


0.1.0, 2018-05-09
------------------
- Switched to Pipenv


0.0.0, 2017-06-14
-------------------
- First release