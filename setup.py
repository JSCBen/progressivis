import os
import os.path
import versioneer
from setuptools import setup, Command
from setuptools.extension import Extension
from Cython.Build import cythonize
import numpy as np

packages = ['progressivis',
            'progressivis.core',
            'progressivis.core.storage',
            'progressivis.core.khash',
            'progressivis.io',
            'progressivis.stats',
            'progressivis.datasets',
            'progressivis.vis',
            'progressivis.cluster',
            #'progressivis.manifold',
            'progressivis.metrics',
            'progressivis.server',
            'progressivis.table',
            #'stool'
]


class run_bench(Command):
    """Runs all ProgressiVis benchmarks"""

    description = "run all benchmarks"
    user_options = []  # distutils complains if this is not here.

    def __init__(self, *args):
        self.args = args[0]  # so we can pass it to other classes
        Command.__init__(self, *args)

    def initialize_options(self):  # distutils wants this
        pass

    def finalize_options(self):    # this too
        pass

    def run(self):
        for root, _, files in os.walk("benchmarks"):
            for fname in files:
                if fname.startswith("bench_") and fname.endswith(".py"):
                    pathname = os.path.join(root, fname)
                    self.run_it(pathname)

    def run_it(self, pathname):
        if self.verbose:  # verbose is provided "automagically"
            print('Should be running bench "{0}"'.format(pathname))
        #TODO run the command with the right arguments

extensions = [
    Extension(
        "progressivis.core.fast",
        ["progressivis/core/fast.pyx"],
        include_dirs=[np.get_include(),],
        extra_compile_args=['-Wfatal-errors'],
    ),
    Extension("progressivis.core.khash.hashtable",
              ["progressivis/core/khash/hashtable.pyx",],
              include_dirs= ['progressivis/core/khash/klib',
                             'progressivis/core/khash',np.get_include(),],
              extra_compile_args=['-Wfatal-errors'],
    )
]

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "progressivis",
    version = versioneer.get_version(),
    author = "Jean-Daniel Fekete",
    author_email = "Jean-Daniel.Fekete@inria.fr",
    url="https://github.com/jdfekete/progressivis",
    description = "A Progressive Steerable Analytics Toolkit",
    license = "BSD",
    keywords = "Progressive analytics visualization",
    packages = packages,
    long_description = read('README.md'),
    classifiers=[
        "Development Status :: 2 - PRe-Alpha",
        "Topic :: Scientific/Engineering :: Visualization",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "License :: OSI Approved :: BSD License",
    ],
    platforms='any',
    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    #install_requires = required,
    install_requires = [
        "Pillow>=4.2.0",
        "numpy>=1.11.3",
        "scipy>=0.18.1",
        "numexpr>=2.6.1",
        "tables>=3.3.0",
        "pandas>=0.19.1",
        "scikit-learn>=0.18.1",
        "toposort>=1.4",
        "tdigest>=0.4.1.0",
        "flask>=0.11.1",
        "tornado>=4.4.2",
        "h5py>=2.6.0",
        "zarr>=2.1.4",
        "numcodecs>=0.5.2",
        "bcolz>=1.1.2",
        "datashape>=0.5.4",
        "pyroaring==0.0.7", # when pyroaring>0.0.5 => error
        "msgpack-python>=0.4.8",
        "boto",
        "s3fs",
        "sqlalchemy",
        "memory_profiler",
        "tabulate",
#        "pptable",
    ],
    setup_requires = [ 'cython', 'numpy', 'nose>=1.3.7', 'coverage'],
    #test_suite='tests',
    test_suite='nose.collector',
    cmdclass = versioneer.get_cmdclass({'bench': run_bench}),
    ext_modules = cythonize(extensions),
    package_data = {
        # If any package contains *.md, *.txt or *.rst files, include them:
        'doc': ['*.md', '*.rst'],
    },

)
