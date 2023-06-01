from setuptools import setup, find_packages

setup(
  name = 'TPDNE-utils',
  packages = find_packages(exclude=[]),
  version = '0.0.1',
  license='MIT',
  description = 'TPDNE',
  author = 'Phil Wang',
  author_email = 'lucidrains@gmail.com',
  long_description_content_type = 'text/markdown',
  url = 'https://github.com/lucidrains/TPDNE',
  keywords = [],
  install_requires = [
    'beartype',
    'numpy',
    'pillow'
  ],
  classifiers=[
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Topic :: Scientific/Engineering :: Artificial Intelligence',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3.6',
  ],
)
