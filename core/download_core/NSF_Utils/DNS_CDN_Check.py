#!/usr/bin/env python
# -*- coding: utf-8 -*-
# DNS_CDN_Check.py - DNS和CDN优化模块
# 作为Hanabi NSF内核组件
# 开发者: ZZBuAoYe

"""
DNS和CDN优化模块
提供智能DNS解析和CDN优化，通过测试和选择最佳节点提高连接速度
"""

import logging
import socket
import threading
import time
import random
import re
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
import concurrent.futures

# 尝试导入可选依赖
try:
    import dns.resolver
    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False
    logging.warning("未找到dnspython库，将使用标准DNS解析")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logging.warning("未找到requests库，将使用有限的连接测试功能")

# CDN提供商特征
CDN_PATTERNS = {
    'cloudflare': [r'cloudflare', r'cdn-cgi', r'cloudflare-nginx'],
    'akamai': [r'akamai', r'akamaitech', r'akamaiedge', r'akadns'],
    'fastly': [r'fastly', r'fastlylb'],
    'amazon': [r'amazonaws', r'cloudfront', r'aws'],
    'google': [r'googleusercontent', r'googlevideo', r'youtube', r'gstatic'],
    'microsoft': [r'msecnd', r'azureedge', r'azure'],
    'alibaba': [r'aliyun', r'alicdn', r'alikunlun'],
    'tencent': [r'qcloud', r'myqcloud', r'tencent-cloud'],
    'baidu': [r'bdydns', r'baiduyun', r'bdstatic'],
    'limelight': [r'limelight', r'llnwd'],
    'cdnetworks': [r'cdnetworks', r'cdnnetworks'],
    'cachefly': [r'cachefly'],
    'stackpath': [r'stackpathdns', r'stackpathcdn', r'highwinds'],
    'keycdn': [r'keycdn'],
    'jsdelivr': [r'jsdelivr'],
    'unpkg': [r'unpkg'],
    'steamcontent': [r'steamcontent', r'steamstatic'],
    'edgecast': [r'edgecastcdn', r'edgecast'],
    'verizon': [r'verizondigitalmedia', r'vdms']
}

# 公共DNS服务器
PUBLIC_DNS_SERVERS = [
    ('1.1.1.1', 'Cloudflare'),
    ('8.8.8.8', 'Google'),
    ('9.9.9.9', 'Quad9'),
    ('208.67.222.222', 'OpenDNS'),
    ('114.114.114.114', 'China 114 DNS'),
    ('223.5.5.5', 'AliDNS'),
    ('119.29.29.29', 'DNSPod')
]

class DNSResolver:
    """DNS解析器，支持多服务器查询和缓存"""
    
    def __init__(self, cache_ttl: int = 300):
        """初始化DNS解析器
        
        Args:
            cache_ttl: 缓存有效期（秒）
        """
        self.cache = {}  # 域名 -> (IP列表, 过期时间)
        self.cache_ttl = cache_ttl
        self.lock = threading.RLock()
        self.dns_servers = PUBLIC_DNS_SERVERS
    
    def _log_debug(self, message: str) -> None:
        """记录调试信息"""
        logging.debug(f"[DNSResolver] {message}")
    
    def resolve(self, domain: str, force_refresh: bool = False) -> List[str]:
        """解析域名为IP地址列表
        
        Args:
            domain: 要解析的域名
            force_refresh: 是否强制刷新缓存
            
        Returns:
            IP地址列表
        """
        with self.lock:
            now = time.time()
            
            # 检查缓存
            if not force_refresh and domain in self.cache:
                ips, expire_time = self.cache[domain]
                if now < expire_time:
                    return ips
            
            # 缓存未命中或已过期，执行解析
            ips = self._resolve_domain(domain)
            
            # 更新缓存
            if ips:
                self.cache[domain] = (ips, now + self.cache_ttl)
            
            return ips
    
    def _resolve_domain(self, domain: str) -> List[str]:
        """执行实际的域名解析
        
        Args:
            domain: 要解析的域名
            
        Returns:
            IP地址列表
        """
        ips = []
        
        # 首先尝试使用dnspython库（如果可用）
        if HAS_DNSPYTHON:
            try:
                self._log_debug(f"使用dnspython解析 {domain}")
                # 创建解析器
                resolver = dns.resolver.Resolver()
                
                # 随机选择两个DNS服务器
                selected_servers = random.sample(self.dns_servers, min(2, len(self.dns_servers)))
                resolver.nameservers = [server[0] for server in selected_servers]
                
                # 设置超时
                resolver.timeout = 2.0
                resolver.lifetime = 4.0
                
                # 执行查询
                answers = resolver.resolve(domain, 'A')
                for rdata in answers:
                    ips.append(str(rdata))
                
                self._log_debug(f"dnspython解析结果: {ips}")
                return ips
            except Exception as e:
                self._log_debug(f"dnspython解析失败: {e}")
        
        # 回退到标准socket解析
        try:
            self._log_debug(f"使用标准socket解析 {domain}")
            socket_ips = socket.gethostbyname_ex(domain)[2]
            ips.extend(socket_ips)
            self._log_debug(f"标准socket解析结果: {ips}")
        except Exception as e:
            self._log_debug(f"标准socket解析失败: {e}")
        
        return ips

class CDNDetector:
    """CDN检测器，识别CDN提供商并优化连接"""
    
    def __init__(self):
        """初始化CDN检测器"""
        self.cdn_cache = {}  # 域名 -> (CDN提供商, 过期时间)
        self.cache_ttl = 3600  # 1小时
        self.lock = threading.RLock()
    
    def _log_debug(self, message: str) -> None:
        """记录调试信息"""
        logging.debug(f"[CDNDetector] {message}")
    
    def detect_cdn(self, domain: str, headers: Dict[str, str] = None) -> Optional[str]:
        """检测域名使用的CDN提供商
        
        Args:
            domain: 域名
            headers: 响应头（如果已知）
            
        Returns:
            CDN提供商名称，如果未检测到则返回None
        """
        with self.lock:
            now = time.time()
            
            # 检查缓存
            if domain in self.cdn_cache:
                cdn, expire_time = self.cdn_cache[domain]
                if now < expire_time:
                    return cdn
            
            # 从响应头检测
            cdn_provider = None
            if headers:
                cdn_provider = self._detect_from_headers(headers)
                if cdn_provider:
                    self._log_debug(f"从响应头检测到CDN: {cdn_provider}")
            
            # 从域名检测
            if not cdn_provider:
                cdn_provider = self._detect_from_domain(domain)
                if cdn_provider:
                    self._log_debug(f"从域名检测到CDN: {cdn_provider}")
            
            # 更新缓存
            self.cdn_cache[domain] = (cdn_provider, now + self.cache_ttl)
            
            return cdn_provider
    
    def _detect_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """从HTTP响应头检测CDN提供商
        
        Args:
            headers: HTTP响应头
            
        Returns:
            CDN提供商名称，如果未检测到则返回None
        """
        # 转换头部键为小写以便不区分大小写匹配
        headers_lower = {k.lower(): v for k, v in headers.items()}
        
        # 检查常见的CDN头部
        if 'cf-ray' in headers_lower:
            return 'cloudflare'
        elif 'x-amz-cf-id' in headers_lower or 'x-amz-cf-pop' in headers_lower:
            return 'amazon'
        elif 'x-fastly-request-id' in headers_lower:
            return 'fastly'
        elif 'x-akamai-transformed' in headers_lower or 'x-akamai-request-id' in headers_lower:
            return 'akamai'
        elif 'x-azure-ref' in headers_lower or 'x-msedge-ref' in headers_lower:
            return 'microsoft'
        elif 'x-cache-hits' in headers_lower and 'keycdn' in headers_lower.get('server', '').lower():
            return 'keycdn'
        elif 'x-cdn' in headers_lower:
            cdn_header = headers_lower['x-cdn'].lower()
            for cdn, patterns in CDN_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, cdn_header):
                        return cdn
        
        # 检查Server头
        if 'server' in headers_lower:
            server = headers_lower['server'].lower()
            for cdn, patterns in CDN_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, server):
                        return cdn
        
        return None
    
    def _detect_from_domain(self, domain: str) -> Optional[str]:
        """从域名检测CDN提供商
        
        Args:
            domain: 域名
            
        Returns:
            CDN提供商名称，如果未检测到则返回None
        """
        domain_lower = domain.lower()
        
        for cdn, patterns in CDN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, domain_lower):
                    return cdn
        
        return None
    
    def get_cdn_optimization(self, cdn_provider: str) -> Dict[str, Any]:
        """获取CDN优化建议
        
        Args:
            cdn_provider: CDN提供商名称
            
        Returns:
            优化建议字典
        """
        optimizations = {
            'headers': {},
            'connection_settings': {}
        }
        
        if not cdn_provider:
            return optimizations
        
        # 通用优化
        optimizations['headers']['Accept-Encoding'] = 'gzip, deflate, br'
        
        # 针对特定CDN的优化
        if cdn_provider == 'cloudflare':
            # Cloudflare优化
            optimizations['headers']['Accept'] = '*/*'
            optimizations['connection_settings']['keepalive'] = True
            optimizations['connection_settings']['http2'] = True
        elif cdn_provider == 'akamai':
            # Akamai优化
            optimizations['headers']['Accept'] = '*/*'
            optimizations['connection_settings']['keepalive'] = True
        elif cdn_provider == 'fastly':
            # Fastly优化
            optimizations['headers']['Accept'] = '*/*'
            optimizations['connection_settings']['keepalive'] = True
            optimizations['connection_settings']['http2'] = True
        elif cdn_provider == 'amazon':
            # Amazon CloudFront优化
            optimizations['headers']['Accept'] = '*/*'
            optimizations['connection_settings']['keepalive'] = True
        
        return optimizations

class ConnectionTester:
    """连接测试器，测试IP地址的连接质量"""
    
    def __init__(self, timeout: float = 2.0, max_workers: int = 4):
        """初始化连接测试器
        
        Args:
            timeout: 连接超时时间（秒）
            max_workers: 最大并发测试数
        """
        self.timeout = timeout
        self.max_workers = max_workers
    
    def _log_debug(self, message: str) -> None:
        """记录调试信息"""
        logging.debug(f"[ConnectionTester] {message}")
    
    def test_connection(self, ip: str, port: int = 80) -> Dict[str, Any]:
        """测试与IP地址的连接质量
        
        Args:
            ip: IP地址
            port: 端口号
            
        Returns:
            连接测试结果字典
        """
        result = {
            'ip': ip,
            'port': port,
            'success': False,
            'latency': float('inf'),
            'error': None
        }
        
        start_time = time.time()
        sock = None
        
        try:
            # 创建socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            # 连接
            sock.connect((ip, port))
            
            # 计算延迟
            latency = time.time() - start_time
            
            result['success'] = True
            result['latency'] = latency
            
            self._log_debug(f"连接到 {ip}:{port} 成功，延迟: {latency:.3f}秒")
            
        except Exception as e:
            result['error'] = str(e)
            self._log_debug(f"连接到 {ip}:{port} 失败: {e}")
            
        finally:
            if sock:
                try:
                    sock.close()
                except:
                    pass
        
        return result
    
    def test_http_connection(self, url: str, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """测试HTTP连接质量
        
        Args:
            url: URL
            headers: 请求头
            
        Returns:
            HTTP连接测试结果字典
        """
        result = {
            'url': url,
            'success': False,
            'latency': float('inf'),
            'status_code': None,
            'headers': None,
            'error': None
        }
        
        if not HAS_REQUESTS:
            result['error'] = "未安装requests库"
            return result
        
        try:
            # 发送HEAD请求
            start_time = time.time()
            response = requests.head(
                url, 
                headers=headers or {}, 
                timeout=self.timeout,
                allow_redirects=False
            )
            latency = time.time() - start_time
            
            result['success'] = True
            result['latency'] = latency
            result['status_code'] = response.status_code
            result['headers'] = dict(response.headers)
            
            self._log_debug(f"HTTP连接到 {url} 成功，状态码: {response.status_code}，延迟: {latency:.3f}秒")
            
        except Exception as e:
            result['error'] = str(e)
            self._log_debug(f"HTTP连接到 {url} 失败: {e}")
        
        return result
    
    def test_multiple_ips(self, ips: List[str], port: int = 80) -> List[Dict[str, Any]]:
        """并发测试多个IP地址的连接质量
        
        Args:
            ips: IP地址列表
            port: 端口号
            
        Returns:
            连接测试结果列表
        """
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_ip = {
                executor.submit(self.test_connection, ip, port): ip 
                for ip in ips
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    self._log_debug(f"测试IP {ip} 时发生错误: {e}")
                    results.append({
                        'ip': ip,
                        'port': port,
                        'success': False,
                        'latency': float('inf'),
                        'error': str(e)
                    })
        
        # 按延迟排序
        results.sort(key=lambda x: x['latency'])
        return results

class CDNOptimizer:
    """CDN优化器，集成DNS解析和CDN优化功能"""
    
    def __init__(self):
        """初始化CDN优化器"""
        self.dns_resolver = DNSResolver()
        self.cdn_detector = CDNDetector()
        self.connection_tester = ConnectionTester()
        self.ip_cache = {}  # 域名 -> (最佳IP, 过期时间)
        self.cache_ttl = 1800  # 30分钟
        self.lock = threading.RLock()
    
    def _log_debug(self, message: str) -> None:
        """记录调试信息"""
        logging.debug(f"[CDNOptimizer] {message}")
    
    def optimize_url(self, url: str, headers: Dict[str, str] = None) -> Dict[str, Any]:
        """优化URL连接
        
        Args:
            url: URL
            headers: 请求头
            
        Returns:
            优化结果字典
        """
        result = {
            'url': url,
            'original_headers': headers or {},
            'headers': headers.copy() if headers else {},
            'best_ip': None,
            'cdn_provider': None,
            'optimizations': {}
        }
        
        try:
            # 解析URL
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            # 如果域名包含端口，去除端口
            if ':' in domain:
                domain = domain.split(':')[0]
            
            # 检查IP缓存
            with self.lock:
                now = time.time()
                if domain in self.ip_cache:
                    best_ip, expire_time = self.ip_cache[domain]
                    if now < expire_time:
                        result['best_ip'] = best_ip
                        self._log_debug(f"使用缓存的最佳IP: {best_ip}")
            
            # 如果没有缓存的最佳IP，执行优化
            if not result['best_ip']:
                # 解析域名
                ips = self.dns_resolver.resolve(domain)
                
                if ips:
                    self._log_debug(f"域名 {domain} 解析结果: {ips}")
                    
                    # 测试连接
                    port = 443 if parsed_url.scheme == 'https' else 80
                    test_results = self.connection_tester.test_multiple_ips(ips, port)
                    
                    # 找到最佳IP
                    successful_results = [r for r in test_results if r['success']]
                    if successful_results:
                        best_result = successful_results[0]  # 延迟最低的结果
                        result['best_ip'] = best_result['ip']
                        
                        # 缓存最佳IP
                        with self.lock:
                            self.ip_cache[domain] = (best_result['ip'], now + self.cache_ttl)
                        
                        self._log_debug(f"找到最佳IP: {best_result['ip']}，延迟: {best_result['latency']:.3f}秒")
            
            # 测试HTTP连接以获取响应头
            if HAS_REQUESTS and (not headers or 'User-Agent' not in headers):
                # 添加默认User-Agent
                if not headers:
                    result['headers'] = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                else:
                    result['headers']['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            
            # 如果有最佳IP，尝试测试HTTP连接
            if result['best_ip'] and HAS_REQUESTS:
                try:
                    # 构建测试URL
                    test_url = f"{parsed_url.scheme}://{result['best_ip']}"
                    if parsed_url.port:
                        test_url += f":{parsed_url.port}"
                    
                    # 添加Host头
                    headers_with_host = result['headers'].copy()
                    headers_with_host['Host'] = domain
                    
                    # 测试连接
                    http_result = self.connection_tester.test_http_connection(test_url, headers_with_host)
                    
                    # 如果成功，检测CDN
                    if http_result['success'] and http_result['headers']:
                        result['cdn_provider'] = self.cdn_detector.detect_cdn(domain, http_result['headers'])
                        
                        # 获取CDN优化建议
                        if result['cdn_provider']:
                            optimizations = self.cdn_detector.get_cdn_optimization(result['cdn_provider'])
                            result['optimizations'] = optimizations
                            
                            # 应用优化头部
                            for k, v in optimizations['headers'].items():
                                if k not in result['headers']:
                                    result['headers'][k] = v
                except Exception as e:
                    self._log_debug(f"测试HTTP连接失败: {e}")
            
            # 如果没有检测到CDN，尝试从域名检测
            if not result['cdn_provider']:
                result['cdn_provider'] = self.cdn_detector.detect_cdn(domain)
                
                # 获取CDN优化建议
                if result['cdn_provider']:
                    optimizations = self.cdn_detector.get_cdn_optimization(result['cdn_provider'])
                    result['optimizations'] = optimizations
                    
                    # 应用优化头部
                    for k, v in optimizations['headers'].items():
                        if k not in result['headers']:
                            result['headers'][k] = v
        
        except Exception as e:
            logging.error(f"优化URL连接失败: {e}")
        
        return result

def optimize_url_connection(url: str, headers: Dict[str, str] = None) -> Dict[str, Any]:
    """优化URL连接
    
    Args:
        url: URL
        headers: 请求头
        
    Returns:
        优化结果字典
    """
    optimizer = CDNOptimizer()
    return optimizer.optimize_url(url, headers)

# 测试代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # 测试URL
    test_urls = [
        "https://www.google.com",
        "https://www.microsoft.com",
        "https://www.github.com",
        "https://www.cloudflare.com"
    ]
    
    optimizer = CDNOptimizer()
    
    for url in test_urls:
        print(f"\n测试URL: {url}")
        result = optimizer.optimize_url(url)
        print(f"最佳IP: {result['best_ip']}")
        print(f"CDN提供商: {result['cdn_provider']}")
        print(f"优化头部: {result['headers']}")
