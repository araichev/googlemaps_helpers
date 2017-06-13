from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE.txt') as f:
    license = f.read()

setuptools.setup(
    name="googlemaps_extras",
    version="0.0.0",
    url="https://github.com/araichev/xxx",
    author="Alex Raichev",
    author_email="araichev@users.noreply.github.com",
    description="Some tools built on top of Google's Python API client",
    long_description=readme,
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),   
    install_requires=[
        'googlemaps>=2.5.0',
        'geopandas>=0.2.1',
    ],
)
