import sys
import os
# 设置环境变量以过滤Qt的字体警告日志
os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts=false"

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont, QIcon
from client.ui.client_interface.main_window import DownloadManagerWindow
# 使用FallbackConnector替代DownloadConnector
try:
    # 尝试导入原始连接器
    from connect.download_manager import DownloadConnector as Connector
    print("使用原始DownloadConnector")
except ImportError:
    # 如果失败，则使用备用连接器
    from connect.fallback_connector import FallbackConnector as Connector
    print("使用FallbackConnector")
from core.font.font_manager import FontManager
from core.log.log_manager import log

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # app.setStyle("Fusion")
    
    # 设置应用图标
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "logo.png")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)
        log.info(f"已设置应用图标: {icon_path}")
    else:
        log.warning(f"图标文件不存在: {icon_path}")
    
    # 先记录系统字体情况
    system_fonts = QFontDatabase.families()
    log.info(f"系统可用字体数量: {len(system_fonts)}")
    log.info(f"常用字体是否可用: Microsoft YaHei: {'Microsoft YaHei' in system_fonts}, "
             f"Arial: {'Arial' in system_fonts}, SimSun: {'SimSun' in system_fonts}")
    
    # 初始化字体管理器 - 这应该在所有其他字体设置之前
    # 让FontManager加载和注册外部字体
    font_manager = FontManager()
    
    # 设置应用默认等宽字体，避免使用Fixedsys
    available_monospace = ["Consolas", "Courier New", "Source Code Pro", "SimSun"]
    
    for font_name in available_monospace:
        if font_name in system_fonts:
            mono_font = QFont(font_name, 10)
            app.setFont(mono_font, "QFontDialog::FixedFont")
            log.info(f"已设置默认等宽字体: {font_name}")
            break
    
    # 现在我们让FontManager来处理应用字体设置
    # 它会使用已注册的外部字体
    font_manager.apply_font(app)
    
    # 再次检查字体注册情况
    updated_fonts = QFontDatabase.families()
    log.info(f"字体管理器加载后字体数: {len(updated_fonts)}")
    
    # 记录新增加的字体
    new_fonts = set(updated_fonts) - set(system_fonts)
    if new_fonts:
        log.info(f"新加载的字体: {', '.join(new_fonts)}")
    
    window = DownloadManagerWindow()
    
    # 创建连接器 - 使用FallbackConnector
    connector = Connector()
    # 设置下载处理程序
    connector.downloadRequestReceived.connect(window.add_download_from_extension)
    connector.start()
    
    window.show()
    sys.exit(app.exec())
