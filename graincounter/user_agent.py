"""User-Agent 解析 — 识别品牌/操作系统/浏览器"""
import re


def parse_user_agent(ua_string: str) -> dict:
    """解析 User-Agent，返回 {brand, os, browser, raw}"""
    result = {"brand": "", "os": "", "browser": "", "raw": ua_string or ""}
    if not ua_string:
        return result
    ua = ua_string

    # --- 操作系统 ---
    os_patterns = [
        (r"Windows NT 10\.0", "Windows 10"),
        (r"Windows NT 11\.0", "Windows 11"),
        (r"Windows NT 6\.1", "Windows 7"),
        (r"Windows", "Windows"),
        (r"Mac OS X (\d+[._]\d+[._]?\d*)", None),
        (r"Android (\d+)", None),
        (r"iPhone OS (\d+_\d+)", None),
        (r"OS (\d+_\d+).*iPad", None),
        (r"Linux", "Linux"),
        (r"CrOS", "ChromeOS"),
    ]
    for pattern, fallback in os_patterns:
        m = re.search(pattern, ua)
        if m:
            if fallback:
                result["os"] = fallback
            elif "Mac OS X" in pattern:
                result["os"] = f"macOS {m.group(1).replace('_', '.')}"
            elif "Android" in pattern:
                result["os"] = f"Android {m.group(1)}"
            elif "iPhone OS" in pattern:
                result["os"] = f"iOS {m.group(1).replace('_', '.')}"
            elif "iPad" in pattern:
                result["os"] = f"iPadOS {m.group(1).replace('_', '.')}"
            break

    # --- 品牌 ---
    # 检测顺序很重要：先排除非Apple的WebKit设备（华为/荣耀/小米等UA含"AppleWebKit"）
    # "Apple" 关键词只在排除其他品牌后才匹配，避免误判
    brand_rules = [
        (["XiaoMi", "MiuiBrowser", "MIUI", "Redmi", "Xiaomi"], "小米"),
        (["HUAWEI", "Huawei", "HarmonyOS"], "华为"),
        (["Samsung", "SM-"], "三星"),
        (["OPPO", "ColorOS", "A37"], "OPPO"),
        (["vivo", "Vivo", "V2024"], "vivo"),
        (["OnePlus"], "一加"),
        (["Realme"], "Realme"),
        (["Honor", "HONOR"], "荣耀"),
        (["Pixel"], "Google"),
        (["Nokia"], "Nokia"),
        (["LG-", "LG;"], "LG"),
        (["Sony"], "索尼"),
        (["Motorola", "Moto"], "摩托罗拉"),
    ]
    for keywords, brand in brand_rules:
        if any(kw in ua for kw in keywords):
            result["brand"] = brand
            break

    # Apple 检测：排除 UA 中含 "AppleWebKit" 但不是 Apple 设备的情况
    # 只有含 iPhone/iPad/iPod/Macintosh 时才是真正的 Apple 设备
    if not result["brand"]:
        if "iPhone" in ua or "iPad" in ua or "iPod" in ua or "Macintosh" in ua:
            result["brand"] = "Apple"

    # --- 浏览器 ---
    browser_rules = [
        (r"Edg/(\d+)", "Edge"),
        (r"OPR/(\d+)", "Opera"),
        (r"Quark/(\d+)", "夸克"),
        (r"UCBrowser|UCWEB", "UC浏览器"),
        (r"MiuiBrowser/([\d.]+)", "小米浏览器"),
        (r"Chrome/(\d+).*Safari", "Chrome"),
        (r"Safari.*Version/([\d.]+)", "Safari"),
        (r"Firefox/(\d+)", "Firefox"),
    ]
    for pattern, name in browser_rules:
        m = re.search(pattern, ua)
        if m:
            version = m.lastindex and m.group(1) or ""
            result["browser"] = f"{name} {version}" if version else name
            break

    return result


def get_device_display_name(ua_info: dict) -> str:
    """生成设备显示名称：手机优先品牌，电脑用系统"""
    parts = []
    if ua_info["brand"]:
        parts.append(ua_info["brand"])
    elif ua_info["os"]:
        parts.append(ua_info["os"])
    if ua_info["browser"]:
        parts.append(ua_info["browser"])
    return " · ".join(parts) if parts else "未知设备"
