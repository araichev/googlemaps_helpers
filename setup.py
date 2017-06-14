from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE.txt') as f:
    license = f.read()

setuptools.setup(
    name="googlemaps_helpers",
    version="0.0.0",
    url="https://github.com/araichev/googlemaps_helpers",
    author="Alex Raichev",
    author_email="araichev@users.noreply.github.com",
    description="Some helpers for the Google Maps API Python client",
    long_description=readme,
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=[
        'googlemaps>=2.5.0',
        'geopandas>=0.2.1',
    ],
)
