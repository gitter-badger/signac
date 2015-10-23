import warnings

from . import conversion
from . import formats
from .project import Project, get_project
from .crawler import BaseCrawler, RegexFileCrawler, JSONCrawler,\
    SignacProjectCrawler, MasterCrawler, fetch, fetched,\
    export, export_pymongo


__all__ = [
    'conversion', 'formats',
    'Project', 'get_project',
    'BaseCrawler', 'RegexFileCrawler', 'JSONCrawler', 'SignacProjectCrawler',
    'MasterCrawler', 'fetch', 'fetched', 'export', 'export_pymongo',
]

try:
    import networkx  # noqa
except ImportError:
    warnings.warn("Failed to import networkx. formats_network will "
                  "not be available.", ImportWarning)
else:
    from .formats_network import get_formats_network, get_conversion_network  # noqa
    __all__.extend(['get_formats_network', 'get_conversion_network'])

try:
    import mpi4py  # noqa
except ImportError:
    warnings.warn("Failed to import mpi4py. MPIPool will not be available.",
                  ImportWarning)
else:
    from .mpi_pool import MPIPool  # noqa
    __all__.extend(['MPIPool'])
