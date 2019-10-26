import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='nutcracker',
    version='0.3.11',
    author='Niv Baehr (BLooperZ)',
    description='Tools for editing resources in SCUMM games.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/blooperz/nutcracker',
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3',
        'Environment :: Console',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Games/Entertainment',
        'Topic :: Utilities'
    ],
    python_requires='>=3.6',
    keywords='game resource edit extract parse chunk index scumm sputm smush lucasarts humongous entertainment'
)
