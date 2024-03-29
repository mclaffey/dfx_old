from setuptools import setup, find_packages

setup(
    name='dfx',
    version='0.1',
    packages=find_packages(exclude=['tests*']),
    license='MIT',
    description='Explore data tables',
    long_description=open('README.md').read(),
    install_requires=['pandas', 'flask', 'matplotlib', 'scipy', 'statsmodels'],
    url='https://github.com/mclaffey/dfx',
    author='Mike Claffey',
    author_email='mpclaffey@gmail.com',
    include_package_data=True,
    scripts = ['bin/dfx'],
)
