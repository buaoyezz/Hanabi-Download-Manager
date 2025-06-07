import http.server
import socketserver
import threading
import json
import logging
import time
import os

# 获取日志记录器
logger = logging.getLogger('HDM.StatusServer')

# 定义默认端口
DEFAULT_PORT = 20972  # 使用不同于WebSocket的端口

class StatusHandler(http.server.SimpleHTTPRequestHandler):
    """处理状态请求的HTTP处理器"""
    
    def __init__(self, *args, **kwargs):
        # SimpleHTTPRequestHandler不接受自定义参数，直接传递标准参数
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """重写日志记录方法，使用HDM的日志系统"""
        logger.debug("%s - %s" % (self.address_string(), format % args))
    
    def do_GET(self):
        """处理GET请求"""
        try:
            if self.path == '/status':
                # 返回状态信息
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')  # 允许跨域
                self.end_headers()
                
                # 检查扩展连接状态
                extension_connected = self.check_extension_connection()
                
                # 创建状态响应
                status = {
                    'status': 'online',
                    'type': 'alive',
                    'timestamp': int(time.time() * 1000),
                    'message': 'HDM服务器运行中',
                    'extension_connected': extension_connected
                }
                
                # 安全发送状态信息
                try:
                    self.wfile.write(json.dumps(status).encode('utf-8'))
                    logger.info("发送状态信息到浏览器扩展")
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
                    logger.warning(f"发送状态信息时连接被中断: {e}")
                except Exception as e:
                    logger.error(f"发送状态信息时出错: {e}")
            else:
                # 对于其他路径，返回404
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error = {
                    'error': 'Not Found',
                    'message': '请求的路径不存在'
                }
                try:
                    self.wfile.write(json.dumps(error).encode('utf-8'))
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
                    logger.warning(f"发送404响应时连接被中断: {e}")
                except Exception as e:
                    logger.error(f"发送404响应时出错: {e}")
        except Exception as e:
            logger.error(f"处理HTTP请求时出错: {e}")
            try:
                # 尝试发送500错误
                self.send_error(500, f"内部服务器错误: {str(e)}")
            except:
                # 如果连发送错误都失败，只记录日志
                logger.error("无法发送500错误响应")
    
    def check_extension_connection(self):
        """检查浏览器扩展是否连接"""
        try:
            import socket
            # 尝试连接扩展监听端口
            test_socket = None
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(0.5)  # 设置更短的超时时间
                test_socket.connect(("localhost", 20971))
                return True
            except (socket.timeout, ConnectionRefusedError, ConnectionResetError) as e:
                logger.debug(f"扩展连接测试失败: {e}")
                return False
            finally:
                if test_socket:
                    try:
                        # 正确关闭socket，先shutdown后close
                        test_socket.shutdown(socket.SHUT_RDWR)
                    except (OSError, socket.error, ConnectionResetError) as e:
                        # 忽略关闭时的错误
                        logger.debug(f"Socket shutdown失败: {e}")
                    finally:
                        try:
                            test_socket.close()
                        except (OSError, socket.error) as e:
                            logger.debug(f"Socket close失败: {e}")
        except Exception as e:
            logger.error(f"检查扩展连接状态时出错: {e}")
            return False
    
    def do_OPTIONS(self):
        """处理OPTIONS请求，支持CORS"""
        try:
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'X-Extension-Check')
            self.end_headers()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError) as e:
            logger.warning(f"发送OPTIONS响应时连接被中断: {e}")
        except Exception as e:
            logger.error(f"处理OPTIONS请求时出错: {e}")


class StatusServer:
    """提供状态检查的HTTP服务器"""
    
    def __init__(self, port=DEFAULT_PORT):
        self.port = port
        self.server = None
        self.server_thread = None
        self.is_running = False
        self.logger = logging.getLogger('HDM.StatusServer')
    
    def start(self):
        """启动HTTP状态服务器"""
        if self.is_running:
            self.logger.warning("HTTP状态服务器已经在运行")
            return
        
        try:
            # 创建一个允许地址重用的HTTP服务器
            handler = StatusHandler
            socketserver.TCPServer.allow_reuse_address = True
            self.server = socketserver.TCPServer(("localhost", self.port), handler)
            
            # 在新线程中启动服务器
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            self.is_running = True
            self.logger.info(f"HTTP状态服务器已启动，监听端口 {self.port}")
        except Exception as e:
            self.logger.error(f"启动HTTP状态服务器失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    
    def _run_server(self):
        """在线程中运行服务器"""
        try:
            self.logger.info("HTTP状态服务器线程开始运行")
            self.server.serve_forever()
        except Exception as e:
            self.logger.error(f"HTTP状态服务器运行出错: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            self.is_running = False
    
    def stop(self):
        """停止HTTP状态服务器"""
        if not self.is_running:
            return
        
        try:
            if self.server:
                self.server.shutdown()
                self.server.server_close()
            
            self.is_running = False
            self.logger.info("HTTP状态服务器已停止")
        except Exception as e:
            self.logger.error(f"停止HTTP状态服务器出错: {e}")
            import traceback
            self.logger.error(traceback.format_exc())


# 单例模式
_status_server_instance = None

def get_status_server(port=DEFAULT_PORT):
    """获取HTTP状态服务器实例"""
    global _status_server_instance
    if _status_server_instance is None:
        _status_server_instance = StatusServer(port)
    return _status_server_instance 