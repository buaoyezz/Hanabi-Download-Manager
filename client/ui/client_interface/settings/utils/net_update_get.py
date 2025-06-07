import requests
import json
import logging

def get_version_info(proxy_settings=None, headers=None, timeout=30, alt_url=None):
    """获取版本信息
    
    Args:
        proxy_settings (dict, optional): 代理设置，例如{"http": "http://proxy:port", "https": "https://proxy:port"}
        headers (dict, optional): 自定义请求头，例如User-Agent
        timeout (int, optional): 请求超时时间（秒）。默认为30秒。
        alt_url (str, optional): 备用更新源URL。如果提供，将直接使用此URL获取更新信息。
        
    Returns:
        dict: 版本信息字典，请求失败时返回None
    """
    # 根据是否提供了备用URL决定使用哪个URL
    url = alt_url if alt_url else "https://apiv2.xiaoy.asia/custody-project/hdm/api/version.php"
    
    try:
        # 禁用SSL警告
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 准备请求参数
        request_kwargs = {
            "verify": False,
            "timeout": timeout
        }
        
        # 添加代理设置（如果提供）
        if proxy_settings:
            request_kwargs["proxies"] = proxy_settings
            logging.info("使用代理设置获取版本信息")
        
        # 添加自定义请求头（如果提供）
        if headers:
            request_kwargs["headers"] = headers
        
        # 发送GET请求
        source_type = "备用" if alt_url else "主"
        logging.info(f"正在从{source_type}更新源获取版本信息: {url}")
        response = requests.get(url, **request_kwargs)
        
        # 检查响应状态
        if response.status_code == 200:
            try:
                # 尝试解析JSON响应
                data = response.json()
                logging.info(f"成功从{source_type}更新源获取版本信息")
                return data
            except json.JSONDecodeError as e:
                logging.error(f"JSON解析错误: {e}")
                logging.debug(f"响应内容: {response.text[:200]}...")
                return None
        else:
            logging.error(f"{source_type}更新源请求失败，状态码: {response.status_code}")
            
            # 只有在使用主源且未指定备用URL时尝试备用路径
            if not alt_url:
                # 尝试主源的备用路径
                alt_url_main = "https://apiv2.xiaoy.asia/version.json"
                logging.info(f"尝试主源备用路径: {alt_url_main}")
                
                alt_response = requests.get(alt_url_main, **request_kwargs)
                
                if alt_response.status_code == 200:
                    try:
                        data = alt_response.json()
                        logging.info("主源备用路径连接成功")
                        return data
                    except json.JSONDecodeError:
                        logging.error("主源备用路径响应不是有效的JSON")
                else:
                    logging.error(f"主源备用路径请求失败，状态码: {alt_response.status_code}")
            
            return None
            
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"连接错误: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"连接超时: {timeout_err}")
        return None
    except Exception as e:
        logging.error(f"请求异常: {e}")
        return None

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 获取版本信息
    version_info = get_version_info()
    
    # 打印结果
    if version_info:
        print(json.dumps(version_info, indent=2, ensure_ascii=False))
    else:
        print("获取版本信息失败")
