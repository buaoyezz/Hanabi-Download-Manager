# Core module initialization
from .config import cfg
from .methods import getProxy, getReadableSize, getLinkInfo, createSparseFile

__all__ = ['cfg', 'getProxy', 'getReadableSize', 'getLinkInfo', 'createSparseFile'] 