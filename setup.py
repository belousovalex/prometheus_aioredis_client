from distutils.core import setup

setup(
    name='prometheus_aioredis_client',
    packages=['prometheus_aioredis_client'],
    version='0.1.0',
    description='Python prometheus multiprocessing client which used redis as metric storage.',
    author='Belousov Alex',
    author_email='belousov.aka.alfa@gmail.com',
    url='https://github.com/belousovalex/prometheus_aioredis_client',
    install_requires=['aioredis>=1.1.0,<2.0.0', ],
    license='Apache 2',
)
