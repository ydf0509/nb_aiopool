"""
nb_aiopool.contrib - 扩展功能模块

提供基于 NbAioPool 的扩展功能
"""

from .nb_aio_task import aio_task, batch_consume, AioTask

__all__ = ['aio_task', 'batch_consume', 'AioTask']

