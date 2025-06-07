from PySide6.QtCore import QObject, Signal, QTranslator, QCoreApplication
import os
import json
import re
from core.config.config_manager import config
from core.log.log_manager import log

# 导入版本管理器
try:
    from client.version.version_manager import VersionManager
    version_manager = VersionManager.get_instance()
except ImportError:
    version_manager = None
    log.warning("无法导入版本管理器，将使用默认版本号")

class I18N(QObject):
    """
    国际化管理类
    支持动态切换语言，自动翻译界面文本
    """
    # 语言变更信号
    language_changed = Signal()
    
    def __init__(self):
        super().__init__()
        self.current_language = "zh_CN"  # 默认语言
        self.translations = {}  # 翻译字典 {语言代码: {key: 翻译}}
        self.supported_languages = ["zh_CN", "en"]  # 支持的语言列表
        self.translator = QTranslator()
        self.non_translatable = ["HanabiDownloadManager"]
        
        # 加载语言配置
        self._load_config()
        
        # 加载所有语言文件
        self._load_translations()
        
        # 应用当前语言
        self.set_language(self.current_language)
        
        # 初始化版本号
        self._init_version()
        
    def _init_version(self):
        """初始化版本信息"""
        try:
            # 优先使用版本管理器获取版本信息
            if version_manager:
                self.client_version = version_manager.get_client_version()
                self.extension_version = version_manager.get_extension_version()
                log.info(f"从版本管理器获取版本信息: 客户端={self.client_version}, 扩展={self.extension_version}")
            else:
                # 回退到旧方法
                self.client_version = self._load_version()
                self.extension_version = "1.0.2"  # 默认扩展版本
                log.info(f"使用旧方法获取版本信息: 客户端={self.client_version}, 扩展={self.extension_version}")
        except Exception as e:
            log.error(f"初始化版本信息失败: {str(e)}")
            self.client_version = "1.0.0"
            self.extension_version = "1.0.2"
    
    def reload_version(self):
        """重新加载版本信息"""
        try:
            if version_manager:
                # 使用版本管理器重新加载
                if version_manager.reload_version():
                    self.client_version = version_manager.get_client_version()
                    self.extension_version = version_manager.get_extension_version()
                    log.info(f"重新加载版本信息: 客户端={self.client_version}, 扩展={self.extension_version}")
                    return True
            return False
        except Exception as e:
            log.error(f"重新加载版本信息失败: {str(e)}")
            return False
        
    def _load_version(self):
        try:
            # 获取基础目录路径
            base_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 尝试多个可能的版本文件路径
            possible_paths = [
                os.path.join(base_dir, "../../client/version/VERSION"),  # 开发环境路径
                os.path.join(base_dir, "../version/VERSION"),            # 相对路径
                os.path.join(base_dir, "/version/VERSION"),              # 打包后可能的路径
                os.path.join(os.path.dirname(base_dir), "version/VERSION") # 上级目录
            ]
            
            # 遍历所有可能的路径
            for version_file in possible_paths:
                if os.path.exists(version_file):
                    with open(version_file, 'r', encoding='utf-8') as f:
                        version_content = f.read().strip()
                        # 提取版本号
                        match = re.search(r'VERSION\s*=\s*(\d+\.\d+\.\d+)', version_content)
                        if match:
                            return match.group(1)
            
            # 如果所有路径都不存在，返回默认版本号
            log.warning("未找到版本文件，使用默认版本号")
            return "1.0.0"  # 默认版本号
        except Exception as e:
            log.error(f"加载版本号失败: {str(e)}")
            return "1.0.0"
    
    def _load_config(self):
        """从配置中加载语言设置"""
        try:
            language = config.get("ui", "language")
            if language and language in self.supported_languages:
                self.current_language = language
            else:
                # 配置不存在或无效，使用默认值并更新配置
                config.set("ui", "language", self.current_language)
                config.save_config()
        except Exception as e:
            log.error(f"加载语言配置失败: {str(e)}")
    
    def _load_translations(self):
        """加载所有语言的翻译文件"""
        try:
            # 获取语言文件目录
            lang_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")
            os.makedirs(lang_dir, exist_ok=True)
            
            # 获取.hdmtr文件目录
            hdmtr_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../languages")
            
            # 遍历所有支持的语言
            for lang in self.supported_languages:
                # 初始化该语言的翻译字典
                if lang not in self.translations:
                    self.translations[lang] = {}
                
                # 检查是否有对应的.hdmtr文件
                hdmtr_file = None
                if lang == "zh_CN":
                    hdmtr_file = os.path.join(hdmtr_dir, "chinese.hdmtr")
                elif lang == "en":
                    hdmtr_file = os.path.join(hdmtr_dir, "en.hdmtr")
                
                # 尝试加载.hdmtr文件
                hdmtr_loaded = False
                if hdmtr_file and os.path.exists(hdmtr_file):
                    hdmtr_loaded = self._load_hdmtr_file(hdmtr_file, lang)
                    log.info(f"从HDMTR文件加载了翻译: {hdmtr_file}")
                
                # 如果没有加载到任何翻译，记录警告
                if not self.translations[lang]:
                    log.warning(f"语言 {lang} 没有加载到任何翻译，请确保对应的hdmtr文件存在")
                        
            log.info(f"已加载 {len(self.translations)} 种语言翻译")
        except Exception as e:
            log.error(f"加载翻译文件失败: {str(e)}")
    
    def _load_hdmtr_file(self, file_path, language):
        """加载.hdmtr格式的翻译文件"""
        try:
            if not os.path.exists(file_path):
                log.warning(f"HDMTR文件不存在: {file_path}")
                return False
            
            # 初始化语言的翻译字典
            if language not in self.translations:
                self.translations[language] = {}
            
            # 读取hdmtr文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # 如果文件为空，直接返回
            if not content:
                return False
                
            # 解析hdmtr格式
            lines = content.split('\n')
            translation_count = 0
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):  # 跳过空行和注释
                    continue
                
                # 尝试解析键值对
                parts = line.split('=', 1)  # 只在第一个等号处分割
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()
                    
                    # 如果值被引号包围，去掉引号
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    # 存储翻译
                    self.translations[language][key] = value
                    translation_count += 1
            
            log.info(f"从HDMTR文件加载了 {translation_count} 条翻译: {file_path}")
            return translation_count > 0  # 如果加载了翻译则返回True
        except Exception as e:
            log.error(f"加载HDMTR文件失败: {file_path}, {str(e)}")
            return False
    
    def save_translations_to_hdmtr(self, language):
        """将翻译保存为.hdmtr格式"""
        try:
            if language not in self.translations:
                log.warning(f"没有找到语言的翻译: {language}")
                return False
            
            # 确定保存路径
            hdmtr_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../languages")
            os.makedirs(hdmtr_dir, exist_ok=True)
            
            # 确定文件名
            if language == "zh_CN":
                file_name = "chinese.hdmtr"
            elif language == "en":
                file_name = "en.hdmtr"
            else:
                file_name = f"{language}.hdmtr"
            
            file_path = os.path.join(hdmtr_dir, file_name)
            
            # 写入hdmtr文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# Hanabi Download Manager Translation Resource\n")
                f.write(f"# Language: {language}\n")
                f.write("# Format: key=value\n\n")
                
                for key, value in sorted(self.translations[language].items()):
                    # 如果值包含特殊字符，用引号包围
                    if any(c in value for c in "=\n#"):
                        value = f'"{value}"'
                    f.write(f"{key}={value}\n")
            
            log.info(f"翻译已保存到HDMTR文件: {file_path}")
            return True
        except Exception as e:
            log.error(f"保存HDMTR文件失败: {language}, {str(e)}")
            return False
    
    def get_text(self, key, *args, **kwargs):
        """
        获取翻译文本
        支持参数格式化: i18n.get_text("hello", "world") -> "Hello, world!"
        支持版本号替换: i18n.get_text("version_string") -> "版本 1.0.7"
        
        Args:
            key: 翻译键
            *args: 格式化参数
            **kwargs: 格式化参数 (关键字参数)
            
        Returns:
            str: 翻译后的文本，如果找不到则返回键名
        """
        try:
            # 检查是否为不可翻译的术语
            for term in self.non_translatable:
                if key == term or (isinstance(key, str) and term in key):
                    return key
                    
            # 获取当前语言的翻译
            translation = self.translations.get(self.current_language, {}).get(key, key)
            
            # 特殊键的处理
            if key == "version":
                return self.client_version
            elif key == "client_version":
                return self.client_version
            elif key == "extension_version":
                # 如果翻译项需要格式化版本号
                if "{version}" in translation:
                    return translation.format(version=self.extension_version)
                return self.extension_version
            
            # 检查翻译是否需要版本号替换
            if "{version}" in translation:
                # 确定要使用的版本号
                version_to_use = kwargs.get("version", self.client_version)
                if "extension" in key.lower():
                    version_to_use = self.extension_version
                # 使用版本号替换占位符
                translation = translation.format(version=version_to_use)
            
            # 如果有参数，进行格式化
            if args and "{" in translation and "}" in translation:
                try:
                    return translation.format(*args)
                except Exception as e:
                    log.warning(f"格式化翻译失败: {key}, {str(e)}")
                    # 格式化失败，返回原文
                    return translation
            
            # 如果有关键字参数，进行格式化
            if kwargs and "{" in translation and "}" in translation:
                try:
                    return translation.format(**kwargs)
                except Exception as e:
                    log.warning(f"关键字格式化翻译失败: {key}, {str(e)}")
                    # 格式化失败，返回原文
                    return translation
            
            return translation
        except Exception as e:
            log.warning(f"获取翻译失败: {key}, {str(e)}")
            return key
    
    def translate_widget(self, widget):
        """
        翻译Qt Widget中的文本
        自动识别并翻译标签、按钮等控件的文本
        
        Args:
            widget: 需要翻译的Qt控件
        """
        # 递归翻译所有子控件
        for child in widget.findChildren(QObject):
            # 翻译标签文本
            if hasattr(child, "text") and callable(getattr(child, "text")) and hasattr(child, "setText") and callable(getattr(child, "setText")):
                original_text = child.text()
                
                # 检查是否包含不可翻译的词
                skip_translation = False
                for term in self.non_translatable:
                    if term in original_text:
                        skip_translation = True
                        break
                        
                if not skip_translation:
                    # 查找可能的翻译键
                    translation_key = self._find_translation_key(original_text)
                    if translation_key:
                        # 使用找到的键获取翻译
                        child.setText(self.get_text(translation_key))
            
            # 翻译工具提示
            if hasattr(child, "toolTip") and callable(getattr(child, "toolTip")) and hasattr(child, "setToolTip") and callable(getattr(child, "setToolTip")):
                original_tooltip = child.toolTip()
                if original_tooltip:
                    skip_translation = False
                    for term in self.non_translatable:
                        if term in original_tooltip:
                            skip_translation = True
                            break
                            
                    if not skip_translation:
                        translation_key = self._find_translation_key(original_tooltip)
                        if translation_key:
                            child.setToolTip(self.get_text(translation_key))
            
            # 翻译窗口标题
            if hasattr(child, "windowTitle") and callable(getattr(child, "windowTitle")) and hasattr(child, "setWindowTitle") and callable(getattr(child, "setWindowTitle")):
                original_title = child.windowTitle()
                if original_title:
                    skip_translation = False
                    for term in self.non_translatable:
                        if term in original_title:
                            skip_translation = True
                            break
                            
                    if not skip_translation:
                        translation_key = self._find_translation_key(original_title)
                        if translation_key:
                            child.setWindowTitle(self.get_text(translation_key))
                        
            # 翻译placeholder文本(对于LineEdit等)
            if hasattr(child, "placeholderText") and callable(getattr(child, "placeholderText")) and hasattr(child, "setPlaceholderText") and callable(getattr(child, "setPlaceholderText")):
                original_placeholder = child.placeholderText()
                if original_placeholder:
                    skip_translation = False
                    for term in self.non_translatable:
                        if term in original_placeholder:
                            skip_translation = True
                            break
                            
                    if not skip_translation:
                        translation_key = self._find_translation_key(original_placeholder)
                        if translation_key:
                            child.setPlaceholderText(self.get_text(translation_key))
    
    def _find_translation_key(self, text):
        """
        根据文本查找对应的翻译键
        
        Args:
            text: 原始文本
            
        Returns:
            str: 找到的翻译键，找不到则返回None
        """
        if not text or len(text.strip()) == 0:
            return None
            
        # 检查是否包含不可翻译的词
        for term in self.non_translatable:
            if term in text:
                return None
                
        # 1. 直接查找文本是否是键
        if text in self.translations.get(self.current_language, {}):
            return text
            
        # 2. 检查是否在值中找到对应的键
        # 先在中文中找，因为中文通常是基础语言
        for lang in ["zh_CN", "en"]:
            for k, v in self.translations.get(lang, {}).items():
                if v == text:
                    return k
        
        # 3. 将文本转换为可能的键格式(小写，下划线分隔)
        possible_key = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '_', text.lower())
        possible_key = re.sub(r'_+', '_', possible_key).strip('_')
        
        # 检查生成的可能键是否存在
        if possible_key in self.translations.get(self.current_language, {}):
            return possible_key
            
        # 找不到对应的键
        return None
    
    def set_language(self, language):
        """
        设置当前语言
        
        Args:
            language: 语言代码，如"zh_CN", "en"
        
        Returns:
            bool: 是否成功切换语言
        """
        if language not in self.supported_languages:
            log.warning(f"不支持的语言: {language}")
            return False
            
        if language == self.current_language:
            return True
            
        # 更新当前语言
        self.current_language = language
        
        # 更新配置
        config.set("ui", "language", language)
        config.save_config()
        
        # 安装翻译器
        if QCoreApplication.instance():
            QCoreApplication.instance().removeTranslator(self.translator)
            # 目前我们使用自己的翻译系统，不使用Qt的翻译器
            
        # 发送语言变更信号
        self.language_changed.emit()
        log.info(f"语言已切换为: {language}")
        return True
    
    def add_translation(self, key, text, language=None):
        """
        添加或更新翻译
        
        Args:
            key: 翻译键
            text: 翻译文本
            language: 语言代码，如果为None则使用当前语言
            
        Returns:
            bool: 是否成功添加翻译
        """
        language = language or self.current_language
        
        if language not in self.supported_languages:
            log.warning(f"不支持的语言: {language}")
            return False
            
        # 更新翻译字典
        if language not in self.translations:
            self.translations[language] = {}
            
        self.translations[language][key] = text
        
        # 保存到文件
        try:
            # 保存到JSON文件
            lang_file = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 
                "lang", 
                f"{language}.json"
            )
            os.makedirs(os.path.dirname(lang_file), exist_ok=True)
            
            with open(lang_file, 'w', encoding='utf-8') as f:
                json.dump(self.translations[language], f, ensure_ascii=False, indent=4)
            
            # 保存到HDMTR文件
            self.save_translations_to_hdmtr(language)
                
            return True
        except Exception as e:
            log.error(f"保存翻译失败: {key}, {language}, {str(e)}")
            return False
    
    def get_supported_languages(self):
        """获取支持的语言列表"""
        return self.supported_languages
        
    def get_current_language(self):
        """获取当前语言"""
        return self.current_language


# 创建单例实例
i18n = I18N()
