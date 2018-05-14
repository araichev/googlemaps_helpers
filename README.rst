Google Maps Helpers
********************
.. image:: https://travis-ci.org/mrcagney/googlemaps_helpers.svg?branch=master
    :target: https://travis-ci.org/mrcagney/googlemaps_helpers

Some Python 3.4+ helpers for the `Google Maps API Python client <https://github.com/googlemaps/google-maps-services-python>`_.
Currently a tiny a hodgepodge incorporating GeoPandas.


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