import os
import chardet
import logging
import sys
import traceback
import platform

class VersionManager:
    # 一个平平无奇的版本号管理类
    _instance = None
    _initialized = False
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = VersionManager()
        return cls._instance
    
    def __init__(self):
        # 初始化
        if VersionManager._initialized:
            return
        VersionManager._initialized = True
        
        self.client_version = "1.0.0"  # 初始的版本
        self.extension_version = "1.0.2"  # 初始的扩展版本
        
        # 设置日志
        self._init_logger()
        self.load_version()
    
    def _init_logger(self):
        # 初始化日志
        try:
            self.logger = logging.getLogger('VersionManager')
            if not self.logger.handlers:
                # 只有在没有处理器时才添加
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                self.logger.addHandler(console_handler)
                self.logger.setLevel(logging.INFO)
        except Exception as e:
            # 无法初始化日志时使用print
            print(f"初始化版本管理器日志失败: {str(e)}")
            self.logger = None
    
    def _log_info(self, message):
        # 记录
        if hasattr(self, 'logger') and self.logger:
            self.logger.info(message)
        else:
            print(f"[VERSION_INFO] {message}")
    
    def _log_warning(self, message):
        # 警告
        if hasattr(self, 'logger') and self.logger:
            self.logger.warning(message)
        else:
            print(f"[VERSION_WARNING] {message}")
    
    def _log_error(self, message):
        # 错误
        if hasattr(self, 'logger') and self.logger:
            self.logger.error(message)
        else:
            print(f"[VERSION_ERROR] {message}")
    
    def _get_possible_paths(self):
        # Anti Path Traversal
        paths = []
        
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            standard_path = os.path.join(parent_dir, "version", "VERSION")
            paths.append(standard_path)
            
            # 尝试另一种常见路径结构
            alt_path = os.path.join(parent_dir, "VERSION")
            paths.append(alt_path)
        except Exception as e:
            self._log_error(f"获取标准路径时出错: {str(e)}")
        
        # 可执行文件所在目录
        try:
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包后的路径
                exe_dir = os.path.dirname(sys.executable)
                exe_path = os.path.join(exe_dir, "client", "version", "VERSION")
                paths.append(exe_path)
                
                # 尝试直接在可执行文件目录下
                exe_direct = os.path.join(exe_dir, "VERSION")
                paths.append(exe_direct)
                
                # 再试一个上层目录
                exe_parent_dir = os.path.dirname(exe_dir)
                exe_parent = os.path.join(exe_parent_dir, "VERSION")
                paths.append(exe_parent)
                
                # 尝试资源目录
                if platform.system() == "Windows":
                    resource_path = os.path.join(exe_dir, "resources", "client", "version", "VERSION")
                    paths.append(resource_path)
                    
                    resource_alt = os.path.join(exe_dir, "resources", "VERSION")
                    paths.append(resource_alt)
                    
                elif platform.system() == "Darwin":  # macOS
                    resource_path = os.path.join(exe_dir, "../Resources/client/version/VERSION")
                    paths.append(resource_path)
                    
                    resource_alt = os.path.join(exe_dir, "../Resources/VERSION")
                    paths.append(resource_alt)
        except Exception as e:
            self._log_error(f"获取可执行文件路径时出错: {str(e)}")
        
        # 当前工作目录
        try:
            cwd_path = os.path.join(os.getcwd(), "client", "version", "VERSION")
            paths.append(cwd_path)
            
            # 直接在当前目录
            cwd_direct = os.path.join(os.getcwd(), "VERSION")
            paths.append(cwd_direct)
            
            # 上级目录
            cwd_parent = os.path.dirname(os.getcwd())
            cwd_parent_path = os.path.join(cwd_parent, "VERSION")
            paths.append(cwd_parent_path)
        except Exception as e:
            self._log_error(f"获取当前工作目录路径时出错: {str(e)}")
        
        # 去重
        return list(dict.fromkeys(paths))
    
    def load_version(self):
        # 从VERSION文件加载版本信息
        loaded = False
        errors = []
        
        # 尝试所有可能的路径
        possible_paths = self._get_possible_paths()
        self._log_info(f"尝试从以下路径加载版本信息: {possible_paths}")
        
        for version_file in possible_paths:
            try:
                if os.path.exists(version_file):
                    self._log_info(f"找到VERSION文件: {version_file}")
                    # 使用chardet检测文件编码
                    with open(version_file, 'rb') as f:
                        raw_data = f.read()
                        if not raw_data:
                            self._log_warning(f"文件为空: {version_file}")
                            continue
                        
                        encoding_result = chardet.detect(raw_data)
                        encoding = encoding_result['encoding'] or 'utf-8'
                        confidence = encoding_result.get('confidence', 0)
                        
                        self._log_info(f"检测到编码: {encoding} (置信度: {confidence:.2f})")
                        if confidence < 0.5:
                            self._log_warning(f"编码置信度过低，尝试使用utf-8")
                            encoding = 'utf-8'
                    
                    # 使用检测到的编码读取文件
                    with open(version_file, 'r', encoding=encoding) as f:
                        lines = f.readlines()
                    
                    for line in lines:
                        line = line.strip()
                        if line.startswith("VERSION ="):
                            self.client_version = line.split("=", 1)[1].strip()
                        elif line.startswith("ExtensionVersion ="):
                            self.extension_version = line.split("=", 1)[1].strip()
                    
                    self._log_info(f"成功从 {version_file} 加载版本信息: 客户端={self.client_version}, 扩展={self.extension_version}")
                    loaded = True
                    break
            except UnicodeDecodeError as ude:
                error_message = f"从 {version_file} 读取时编码错误: {str(ude)}"
                self._log_warning(error_message)
                errors.append(error_message)
                # 尝试其他编码
                try:
                    with open(version_file, 'r', encoding='latin-1') as f:
                        lines = f.readlines()
                    
                    for line in lines:
                        line = line.strip()
                        if line.startswith("VERSION ="):
                            self.client_version = line.split("=", 1)[1].strip()
                        elif line.startswith("ExtensionVersion ="):
                            self.extension_version = line.split("=", 1)[1].strip()
                    
                    self._log_info(f"使用latin-1编码成功从 {version_file} 加载版本信息: 客户端={self.client_version}, 扩展={self.extension_version}")
                    loaded = True
                    break
                except Exception as e2:
                    self._log_warning(f"使用备用编码加载失败: {str(e2)}")
            except Exception as e:
                error_message = f"从 {version_file} 加载版本信息失败: {str(e)}"
                self._log_warning(error_message)
                errors.append(error_message)
                continue
        
        if not loaded:
            error_msg = f"无法从任何路径加载版本信息，使用默认版本: 客户端={self.client_version}, 扩展={self.extension_version}"
            if errors:
                error_details = "; ".join(errors[:3])  # 只显示前3个错误
                if len(errors) > 3:
                    error_details += f" 和 {len(errors) - 3} 个其他错误"
                self._log_warning(f"{error_msg}。错误: {error_details}")
            else:
                self._log_warning(error_msg)
    
    def reload_version(self):
        # 重新加载版本信息
        old_client = self.client_version
        old_extension = self.extension_version
        self.load_version()
        changed = (old_client != self.client_version or old_extension != self.extension_version)
        if changed:
            self._log_info(f"版本信息已更新: 客户端 {old_client} -> {self.client_version}, 扩展 {old_extension} -> {self.extension_version}")
        else:
            self._log_info("版本信息未变化")
        return changed
    
    def get_client_version(self):
        # 获取客户端版本
        return self.client_version
    
    def get_extension_version(self):
        # 获取扩展版本
        return self.extension_version
        
    def __str__(self):
        return f"VersionManager(client={self.client_version}, extension={self.extension_version})" 