from PySide6.QtGui import QFont, QFontDatabase, QColor, QPixmap, QPainter, QIcon
from PySide6.QtWidgets import QWidget, QApplication, QLabel, QPushButton
from PySide6.QtCore import Qt, QThread, Signal, QEventLoop, QSize, QRect
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
import platform
import re
import os
import sys
import json
from .icon_map import ICON_MAP
from core.log.log_manager import log
from core.thread.thread_manager import thread_manager

# 缓存常量和常用值
FONTS_DIR = "core/font/font"
ICONS_DIR = "core/font/icons"
DEFAULT_ICON_SIZE = 24
DEFAULT_FONT_SIZE = 16
COLOR_WHITE = "#FFFFFF"
COLOR_DARK = "#333333"

def resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境和打包环境"""
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

class WebFontLoader(QThread):
    """用于从网络加载Web字体的线程"""
    font_loaded = Signal(bool, str)  # 成功与否，错误信息
    
    def __init__(self, font_url, font_family):
        super().__init__()
        self.font_url = font_url
        self.font_family = font_family
        self.manager = QNetworkAccessManager()
        
    def run(self):
        try:
            request = QNetworkRequest(self.font_url)
            reply = self.manager.get(request)
            
            loop = QEventLoop()
            reply.finished.connect(loop.quit)
            loop.exec_()
            
            if reply.error() == QNetworkReply.NoError:
                font_data = reply.readAll()
                font_id = QFontDatabase.addApplicationFontFromData(font_data)
                
                if font_id >= 0:
                    log.info(f"Web字体加载成功：{self.font_family}")
                    self.font_loaded.emit(True, "")
                else:
                    log.error(f"Web字体加载失败：{self.font_family}")
                    self.font_loaded.emit(False, "字体加载失败")
            else:
                error_msg = reply.errorString()
                log.error(f"Web字体下载失败：{error_msg}")
                self.font_loaded.emit(False, f"下载失败：{error_msg}")
                
            reply.deleteLater()
        except Exception as e:
            log.error(f"Web字体加载异常：{str(e)}")
            self.font_loaded.emit(False, str(e))

class FontLoaderThread(QThread):
    finished = Signal(dict)  # 返回字典，包含加载结果信息
    progress = Signal(str, int)  # 添加进度百分比
    
    def __init__(self, fonts_to_load):
        super().__init__()
        self.fonts_to_load = fonts_to_load
        
    def run(self):
        loaded_fonts = {}
        total = len(self.fonts_to_load)
        
        def load_single_font(font_path, font_name):
            try:
                if os.path.exists(font_path):
                    font_id = QFontDatabase.addApplicationFont(font_path)
                    if font_id >= 0:
                        return {
                            'success': True,
                            'name': font_name,
                            'id': font_id,
                            'families': QFontDatabase.applicationFontFamilies(font_id)
                        }
                return {'success': False, 'name': font_name, 'error': '字体文件不存在'}
            except Exception as e:
                return {'success': False, 'name': font_name, 'error': str(e)}

        # 并行加载字体
        tasks = {}
        for i, (font_path, font_name) in enumerate(self.fonts_to_load):
            task_id = f"font_load_{font_name}_{i}"
            future = thread_manager.submit_task(task_id, load_single_font, font_path, font_name)
            tasks[task_id] = (future, font_name)
            self.progress.emit(f"提交字体加载任务: {font_name}", int((i + 1) * 50 / total))

        # 收集结果
        for i, (task_id, (future, font_name)) in enumerate(tasks.items()):
            try:
                result = future.result(timeout=3)  # 3秒超时
                loaded_fonts[font_name] = result
                self.progress.emit(f"完成字体加载: {font_name}", int(50 + (i + 1) * 50 / total))
            except Exception as e:
                loaded_fonts[font_name] = {
                    'success': False, 'name': font_name, 'error': f'加载超时: {str(e)}'
                }
                
        self.finished.emit(loaded_fonts)

class FontManager:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FontManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if FontManager._initialized:
            return
            
        # 字体名称初始化
        self.hmsans_fonts = "HarmonyOS_Sans_SC"
        self.hmsans_fonts_bold = "HarmonyOS_Sans_SC_Bold"
        self.mulish_font = "Mulish"
        self.mulish_bold = "Mulish-Bold"
        self.fluent_icons_font = "Fluent System Icons"
        
        # 字体路径初始化
        self.fluent_icon_path = resource_path(os.path.join(ICONS_DIR, "FluentSystemIcons-Regular.ttf"))
        self.hmsans_font_path = resource_path(os.path.join(FONTS_DIR, "HarmonyOS_Sans_SC_Regular.ttf"))
        self.hmsans_bold_path = resource_path(os.path.join(FONTS_DIR, "HarmonyOS_Sans_SC_Bold.ttf"))
        self.mulish_font_path = resource_path(os.path.join(FONTS_DIR, "Mulish-Regular.ttf"))
        self.mulish_bold_path = resource_path(os.path.join(FONTS_DIR, "Mulish-Bold.ttf"))
        
        # 图标缓存
        self._icon_cache = {}
        
        # 初始化
        self._load_fluent_icons_map()
        self._init_fonts()
        
        FontManager._initialized = True
    
    def _load_fluent_icons_map(self):
        """加载Fluent Icons字体映射"""
        try:
            fluent_map_path = resource_path(os.path.join(ICONS_DIR, "FluentSystemIcons-Regular.json"))
            if not os.path.exists(fluent_map_path):
                log.warning(f"Fluent图标映射文件不存在: {fluent_map_path}")
                return
                
            with open(fluent_map_path, 'r', encoding='utf-8') as f:
                fluent_map_data = json.load(f)
                
            # 将Unicode码点转换为字符并更新ICON_MAP
            fluent_icons_map = {key: chr(value) for key, value in fluent_map_data.items()}
            
            # 添加特殊图标映射
            fluent_icons_map["ic_fluent_restore_24_regular"] = fluent_icons_map.get("ic_fluent_maximize_24_regular", "")
            
            # 更新全局图标映射
            ICON_MAP.update(fluent_icons_map)
            log.info(f"已加载Fluent图标映射，共{len(fluent_icons_map)}个图标")
        except Exception as e:
            log.error(f"加载Fluent图标映射出错: {str(e)}")

    def _init_fonts(self):
        """初始化所有字体"""
        log.info("开始初始化字体")
        
        # 检查字体文件
        icon_font_exists = os.path.exists(self.fluent_icon_path)
        hmsans_exists = os.path.exists(self.hmsans_font_path)
        mulish_exists = os.path.exists(self.mulish_font_path)
        
        log.info(f"字体文件检查: Fluent图标字体:{icon_font_exists}, HarmonyOS:{hmsans_exists}, Mulish:{mulish_exists}")
        
        # 加载字体
        self._load_icon_fonts()
        self._load_fonts_sync()
        
        log.info("字体初始化完成")
        
    def _load_icon_fonts(self):
        """加载Fluent图标字体"""
        if not os.path.exists(self.fluent_icon_path):
            log.warning(f"Fluent图标字体文件不存在: {self.fluent_icon_path}")
            return
            
        try:
            font_db = QFontDatabase()
            initial_families = set(font_db.families())
            
            # 加载图标字体
            font_id = font_db.addApplicationFont(self.fluent_icon_path)
            if font_id < 0:
                log.error(f"加载Fluent图标字体失败，返回ID: {font_id}")
                return
                
            # 获取加载的字体族
            families = font_db.applicationFontFamilies(font_id)
            if not families:
                log.error("加载Fluent图标字体成功但未找到字体族")
                return
                
            # 设置字体名称
            self.fluent_icons_font = families[0]
            log.info(f"成功加载Fluent图标字体: {self.fluent_icons_font}")
            
            # 检查常用图标
            self._check_common_icons()
            
            # 显示新增的字体族
            new_families = set(font_db.families()) - initial_families
            if new_families:
                log.info(f"新增字体族: {', '.join(new_families)}")
        except Exception as e:
            log.error(f"加载Fluent图标字体出错: {str(e)}")
    
    def _check_common_icons(self):
        """检查常用图标是否存在"""
        common_icons = {
            "ic_fluent_maximize_24_regular": "最大化",
            "ic_fluent_dismiss_24_regular": "关闭",
            "ic_fluent_subtract_24_regular": "最小化"
        }
        
        for icon_name, desc in common_icons.items():
            icon_char = ICON_MAP.get(icon_name, "")
            if icon_char:
                unicode_value = f"U+{ord(icon_char):04X}"
                log.debug(f"图标样本 - {desc}({icon_name}): {unicode_value}")
            else:
                log.warning(f"未找到图标: {desc}({icon_name})")
    
    def _load_fonts_sync(self):
        """同步加载常规字体"""
        font_db = QFontDatabase()
        fonts_to_load = [
            (self.mulish_font_path, "Mulish Regular"),
            (self.mulish_bold_path, "Mulish Bold"), 
            (self.hmsans_font_path, "HarmonyOS Sans SC Regular"),
            (self.hmsans_bold_path, "HarmonyOS Sans SC Bold"),
        ]
        
        # 存储加载的字体族
        self.loaded_families = []
        
        for font_path, font_name in fonts_to_load:
            if not os.path.exists(font_path):
                log.error(f"字体文件不存在: {font_path}")
                continue
                
            try:
                # 加载字体
                font_id = font_db.addApplicationFont(font_path)
                if font_id < 0:
                    log.error(f"加载字体失败: {font_name}")
                    continue
                    
                # 获取字体族
                families = font_db.applicationFontFamilies(font_id)
                if not families:
                    log.error(f"加载字体成功但未找到字体族: {font_name}")
                    continue
                
                # 更新字体名称
                if "HarmonyOS" in font_name:
                    if "Bold" in font_name:
                        self.hmsans_fonts_bold = families[0]
                    else:
                        self.hmsans_fonts = families[0]
                elif "Mulish" in font_name:
                    if "Bold" in font_name:
                        self.mulish_bold = families[0]
                    else:
                        self.mulish_font = families[0]
                
                # 添加到已加载列表
                self.loaded_families.extend(families)
                log.info(f"成功加载字体: {font_name} -> {families}")
            except Exception as e:
                log.error(f"加载字体出错 {font_name}: {str(e)}")
        
        # 检测系统后备字体
        self._detect_backup_fonts()
    
    def _detect_backup_fonts(self):
        """检测系统中可用的后备字体"""
        font_db = QFontDatabase()
        system_fonts = ["Source Han Sans SC", "Source Han Sans CN", "Microsoft YaHei", "SimSun"]
        monospace_fonts = ["Consolas", "Courier New", "Source Code Pro"]
        
        available_fonts = set(font_db.families())
        self.available_backups = [f for f in system_fonts + monospace_fonts if f in available_fonts]
        
        if self.available_backups:
            log.info(f"可用后备字体: {', '.join(self.available_backups)}")
        else:
            log.warning("没有找到可用的后备字体")

    def _is_light_background(self, widget):
        """检测控件背景是否为亮色，优化性能"""
        # 应用程序默认为亮色
        if isinstance(widget, QApplication):
            return True
        
        # 获取背景色
        bg_color = widget.palette().color(widget.backgroundRole())
        
        # 背景透明时，查找父控件的背景色
        if bg_color.alpha() == 0:
            style = widget.styleSheet()
            if "background-color:" in style:
                color_match = re.search(r'background-color:\s*(.*?)(;|$)', style)
                if color_match:
                    color = color_match.group(1).strip().lower()
                    
                    # 处理常见颜色关键字
                    if color in {'white', 'transparent'}:
                        return True
                    if color == 'black':
                        return False
                    
                    # 处理RGB/RGBA格式
                    if color.startswith('rgb'):
                        rgb_match = re.search(r'(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color)
                        if rgb_match:
                            r, g, b = map(int, rgb_match.groups())
                            return (r * 299 + g * 587 + b * 114) / 1000 > 128
                    
                    # 处理十六进制格式
                    if color.startswith('#') and len(color) >= 7:
                        r = int(color[1:3], 16)
                        g = int(color[3:5], 16)
                        b = int(color[5:7], 16)
                        return (r * 299 + g * 587 + b * 114) / 1000 > 128
            
            # 递归检查父控件
            parent = widget.parentWidget()
            if parent:
                return self._is_light_background(parent)
            
            return True  # 默认亮色
        
        # 计算亮度
        return (bg_color.red() * 299 + bg_color.green() * 587 + bg_color.blue() * 114) / 1000 > 128
            
    def create_optimized_font(self, is_bold=False, size=DEFAULT_FONT_SIZE):
        """创建优化的字体对象"""
        font = QFont()
        
        # 设置字体族
        primary_font = self.hmsans_fonts_bold if is_bold else self.hmsans_fonts
        secondary_font = self.mulish_bold if is_bold else self.mulish_font
        
        font.setFamilies([primary_font, secondary_font, self.fluent_icons_font])
        
        # 设置渲染选项
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality)
        
        # 设置属性
        font.setKerning(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.3)
        font.setWeight(QFont.Weight.Bold if is_bold else QFont.Weight.Medium)
        font.setPixelSize(size)
        
        return font

    def create_icon_font(self, size=DEFAULT_ICON_SIZE):
        """创建图标字体对象"""
        font = QFont(self.fluent_icons_font)
        font.setPixelSize(size)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality)
        return font

    def get_icon_text(self, icon_name):
        """获取图标字符
        
        Args:
            icon_name: 图标名称，例如"ic_fluent_arrow_download_24_regular"
            
        Returns:
            str: 图标对应的Unicode字符，如果找不到则返回空字符串
        """
        try:
            # 标准化名称
            if not icon_name.startswith("ic_fluent_"):
                icon_name = f"ic_fluent_{icon_name}_24_regular"
            
            # 从映射中获取字符
            icon_char = ICON_MAP.get(icon_name, "")
            
            if not icon_char and "_24_" in icon_name:
                # 尝试查找其他尺寸
                for size in ["16", "20", "28", "32", "48"]:
                    alt_name = icon_name.replace("_24_", f"_{size}_")
                    icon_char = ICON_MAP.get(alt_name, "")
                    if icon_char:
                        break
            
            return icon_char
        except Exception as e:
            log.warning(f"获取图标文本失败: {icon_name}, {str(e)}")
            return ""
    
    def get_qicon(self, icon_name, color=COLOR_WHITE):
        """从字体图标创建QIcon对象
        
        Args:
            icon_name: 图标名称，例如"ic_fluent_window_24_regular"
            color: 图标颜色，默认为白色
            
        Returns:
            QIcon: 图标对象，如果无法创建则返回空图标
        """
        try:
            # 检查缓存
            cache_key = f"{icon_name}_{color}"
            if cache_key in self._icon_cache:
                return self._icon_cache[cache_key]
            
            # 获取图标文本
            icon_text = self.get_icon_text(icon_name)
            if not icon_text:
                log.warning(f"无法找到图标: {icon_name}")
                return QIcon()
            
            # 创建图标
            icon_font = self.create_icon_font()
            
            # 确定合适的大小
            icon_sizes = [16, 24, 32, 48]
            
            icon = QIcon()
            for size in icon_sizes:
                pixmap = QPixmap(size, size)
                pixmap.fill(Qt.transparent)
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setRenderHint(QPainter.TextAntialiasing)
                
                # 设置字体和颜色
                icon_font.setPointSize(size * 0.8)  # 稍微缩小一点以适应边界
                painter.setFont(icon_font)
                painter.setPen(QColor(color))
                
                # 绘制图标
                painter.drawText(QRect(0, 0, size, size), Qt.AlignCenter, icon_text)
                painter.end()
                
                # 添加到图标的不同尺寸
                icon.addPixmap(pixmap)
            
            # 缓存图标
            self._icon_cache[cache_key] = icon
            return icon
            
        except Exception as e:
            log.error(f"创建图标失败: {icon_name}, {str(e)}")
            return QIcon()

    def apply_font(self, widget, size=DEFAULT_FONT_SIZE, is_bold=False):
        """将字体应用到控件"""
        if not isinstance(widget, (QWidget, QApplication)):
            raise TypeError("不支持的类型，只能应用到QWidget或QApplication")
            
        # 创建字体
        font = self.create_optimized_font(is_bold, size)
        widget.setFont(font)
        
        if isinstance(widget, QApplication):
            # 应用程序样式
            widget.setStyleSheet("""
                QWidget { color: #333333; background-color: transparent; }
                QLabel, QPushButton { background-color: transparent; }
            """)
        else:
            # 控件样式
            style = widget.styleSheet()
            
            # 构建样式列表
            styles = [style] if style else []
            
            # 添加背景透明
            if "background-color:" not in style:
                styles.append("background-color: transparent;")
            
            # 设置文字颜色
            color = COLOR_DARK if self._is_light_background(widget) else COLOR_WHITE
            styles.append(f"color: {color};")
            
            # 应用样式
            widget.setStyleSheet("\n".join(styles))
            
            # 特定控件设置
            if isinstance(widget, (QLabel, QPushButton)):
                widget.setAttribute(Qt.WA_TranslucentBackground)

    def apply_icon_font(self, widget, icon_name="", size=DEFAULT_ICON_SIZE):
        """将图标字体应用到控件"""
        if not isinstance(widget, (QWidget, QLabel)):
            raise TypeError("不支持的类型，只能应用到QWidget或QLabel")
            
        # 设置字体
        widget.setFont(self.create_icon_font(size))
        
        # 设置图标文本
        icon_text = ""
        if icon_name:
            if isinstance(icon_name, int):
                # 整数参数直接转换为Unicode字符
                icon_text = chr(icon_name)
            else:
                # 字符串参数查找映射
                icon_text = self.get_icon_text(icon_name)
                
            widget.setText(icon_text)
            
        # 设置透明和颜色
        widget.setAttribute(Qt.WA_TranslucentBackground)
        widget.setStyleSheet("background-color: transparent; color: #FFFFFF;")
        
        return icon_text

    def create_icon_label(self, parent, icon_name, size=DEFAULT_ICON_SIZE, color=None):
        """创建包含图标的标签"""
        label = QLabel(parent)
        
        # 设置图标
        self.apply_icon_font(label, icon_name, size)
        
        # 设置颜色
        if color:
            if isinstance(color, QColor):
                rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()/255.0})"
                label.setStyleSheet(f"color: {rgba}; background-color: transparent;")
            else:
                label.setStyleSheet(f"color: {color}; background-color: transparent;")
            
        # 设置大小
        label.setFixedSize(size, size)
        
        return label
    
    def get_available_icons(self, prefix=""):
        """获取可用图标列表"""
        if prefix:
            return [k for k in ICON_MAP if k.startswith(prefix)]
        return list(ICON_MAP.keys())
    
    def get_fluent_icons(self):
        """获取所有Fluent图标"""
        return self.get_available_icons("ic_fluent_")

    def get_icon_font(self):
        """获取图标字体的字体族名称
        
        返回:
            str: 图标字体的字体族名称
        """
        return self.fluent_icons_font

    def apply_icon_to_icon(self, icon, icon_name, size=24, color="#FFFFFF"):
        """将图标字体应用到QIcon对象
        
        参数:
            icon (QIcon): 要应用图标的QIcon对象
            icon_name (str): 图标名称
            size (int): 图标大小
            color (str): 图标颜色
        """
        from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
        from PySide6.QtCore import Qt, QSize, QRect
        
        # 获取图标字体和字符
        icon_font = self.get_icon_font()
        icon_text = self.get_icon_text(icon_name)
        
        if not icon_font or not icon_text:
            return
        
        # 创建临时QPixmap用于绘制图标
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        # 设置画笔
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        # 设置字体
        font = QFont(icon_font)
        font.setPixelSize(size)
        painter.setFont(font)
        
        # 设置颜色
        painter.setPen(QColor(color))
        
        # 绘制图标
        painter.drawText(QRect(0, 0, size, size), Qt.AlignCenter, icon_text)
        painter.end()
        
        # 应用到图标
        icon.addPixmap(pixmap, QIcon.Normal, QIcon.Off)

