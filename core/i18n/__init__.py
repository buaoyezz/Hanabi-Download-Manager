"""
国际化模块，提供多语言支持
"""

# 从client中导入i18n单例实例
from client.I18N.i18n import i18n

# 重新导出供其他模块使用
__all__ = ['i18n'] 