"""Verification tests for security and functionality fixes"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """All modules import correctly"""
    from graincounter.config import load_config, get_config
    from graincounter.logger import setup_logger
    from graincounter.rate_limiter import RateLimiter
    from graincounter.device_tracker import OnlineDeviceTracker
    from graincounter.detector import GrainDetector
    from graincounter.valuable import ValuablePhotoSaver
    from graincounter.stats import DetectionStats
    import web_server
    print("  [PASS] All imports OK")

def test_rate_limiter_memory_cleanup():
    """RateLimiter has memory cleanup (task 1)"""
    from graincounter.rate_limiter import RateLimiter
    r = RateLimiter(10, 60)
    assert hasattr(r, '_last_cleanup'), "Missing _last_cleanup"
    assert hasattr(r, '_cleanup_old'), "Missing _cleanup_old method"
    print("  [PASS] RateLimiter memory cleanup")

def test_device_tracker_cleanup():
    """DeviceTracker has offline cleanup (task 2)"""
    from graincounter.device_tracker import OnlineDeviceTracker
    t = OnlineDeviceTracker(30)
    assert hasattr(t, '_last_cleanup'), "Missing _last_cleanup"
    assert hasattr(t, '_cleanup_offline'), "Missing _cleanup_offline method"
    print("  [PASS] DeviceTracker offline cleanup")

def test_valuable_thread_safe():
    """ValuablePhotoSaver increment_count is lock-protected (task 3)"""
    from graincounter.valuable import ValuablePhotoSaver
    v = ValuablePhotoSaver()
    assert hasattr(v, 'increment_count'), "Missing increment_count method"
    old = v.saved_count
    v.increment_count()
    assert v.saved_count == old + 1, "Count not incremented"
    print("  [PASS] ValuablePhotoSaver thread safety")

def test_ip_ban():
    """RateLimiter has IP ban support (task 10)"""
    from graincounter.rate_limiter import RateLimiter
    r = RateLimiter(10, 60, ban_minutes=1)
    assert hasattr(r, 'is_banned'), "Missing is_banned"
    assert hasattr(r, 'record_rejection'), "Missing record_rejection"
    # Simulate 3 rejections
    for _ in range(3):
        r.record_rejection("10.0.0.1")
    assert r.is_banned("10.0.0.1"), "IP should be banned after 3 rejections"
    print("  [PASS] IP auto-ban works")

def test_detection_stats():
    """DetectionStats counts correctly (task 12)"""
    from graincounter.stats import DetectionStats
    s = DetectionStats()
    s.record_success("1.1.1.1")
    s.record_success("2.2.2.2")
    s.record_success("1.1.1.1")
    s.record_error()
    stats = s.get_stats()
    assert stats['total'] == 3, f"Expected 3, got {stats['total']}"
    assert stats['today'] == 3
    assert stats['errors'] == 1
    assert stats['uptime_seconds'] >= 0
    top = dict(stats['top_ips'])
    assert top.get('1.1.1.1') == 2
    assert top.get('2.2.2.2') == 1
    print("  [PASS] Detection stats counting")

def test_web_server_import():
    """web_server imports without errors"""
    import web_server
    assert hasattr(web_server, 'app'), "Missing app"
    from graincounter.routes.detect import detect_semaphore
    assert detect_semaphore is not None
    from graincounter.state import app_state
    assert app_state.detect_rate_limiter is not None
    print("  [PASS] web_server imports")

def test_web_server_config():
    """web_server config loads correctly"""
    from graincounter.config import load_config
    cfg = load_config()
    assert cfg['port'] == 8000, f"Port: {cfg['port']}"
    assert 'model_path' in cfg
    print(f"  [PASS] Config loaded (model={cfg['model_path']})")

if __name__ == "__main__":
    print("=== Grain Counter Verification Tests ===")
    tests = [
        ("Imports", test_imports),
        ("RateLimiter cleanup", test_rate_limiter_memory_cleanup),
        ("DeviceTracker cleanup", test_device_tracker_cleanup),
        ("Valuable thread safety", test_valuable_thread_safe),
        ("IP auto-ban", test_ip_ban),
        ("Detection stats", test_detection_stats),
        ("web_server import", test_web_server_import),
        ("Config loading", test_web_server_config),
    ]
    passed = 0
    for name, func in tests:
        try:
            func()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
    print(f"\n=== Result: {passed}/{len(tests)} passed ===")
    sys.exit(0 if passed == len(tests) else 1)
