# test_setup.py

"""
SignalScan PRO - Installation Test Script
Verifies all dependencies and configuration
"""

import sys
import os

def test_python_version():
    """Check Python version"""
    version = sys.version_info
    if version.major == 3 and version.minor >= 8:
        print(f"[✓] Python version: {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"[✗] Python version: {version.major}.{version.minor}.{version.micro}")
        print("    Required: Python 3.8+")
        return False

def test_virtual_env():
    """Check if running in virtual environment"""
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    if in_venv:
        print("[✓] Virtual environment: Active")
        return True
    else:
        print("[⚠] Virtual environment: Not detected")
        print("    Recommended: Create and activate a venv")
        return True  # Warning, not error

def test_dependencies():
    """Check if all required packages are installed"""
    # Core packages to check
    required = {
        'kivy': '2.3.1',
        'dotenv': '1.1.1',
        'yfinance': '0.2.66',
        'pandas': '2.3.2',
        'numpy': '2.3.3',
        'requests': '2.32.5',
        'websocket': '1.8.0',
        'pygments': '2.19.2',
        'pytz': '2025.2',
        'alpaca': '0.42.2',  # alpaca-py
    }
    
    all_installed = True
    
    for package, expected_version in required.items():
        try:
            if package == 'dotenv':
                import dotenv
                version = dotenv.__version__
            elif package == 'websocket':
                import websocket
                version = websocket.__version__
            elif package == 'alpaca':
                import alpaca
                version = alpaca.__version__
            else:
                module = __import__(package)
                version = getattr(module, '__version__', 'unknown')
            
            print(f"[✓] {package}: {version}")
        except ImportError:
            print(f"[✗] {package}: NOT INSTALLED")
            all_installed = False
        except Exception as e:
            print(f"[⚠] {package}: Error checking version - {e}")
    
    return all_installed

def test_env_file():
    """Check if .env file exists"""
    if os.path.exists('.env'):
        print("[✓] .env file: Found")
        
        # Check if it has content (not just template)
        with open('.env', 'r') as f:
            content = f.read()
            if 'your_alpaca_key_here' in content or 'your_tradier_token_here' in content:
                print("    [⚠] Warning: .env file contains template values")
                print("    Action: Replace with your actual API keys")
        
        return True
    else:
        print("[✗] .env file: NOT FOUND")
        print("    Action: Copy .env.example to .env and add your API keys")
        return False

def test_directories():
    """Check if required directories exist"""
    dirs = ['core', 'config', 'data', 'logs', 'sounds']
    all_exist = True
    
    for directory in dirs:
        if os.path.exists(directory):
            print(f"[✓] Directory: {directory}/")
        else:
            print(f"[✗] Directory: {directory}/ NOT FOUND")
            all_exist = False
    
    return all_exist

def main():
    """Run all tests"""
    print("=" * 60)
    print("SignalScan PRO - Installation Test")
    print("=" * 60)
    print()
    
    tests = [
        ("Python Version", test_python_version),
        ("Virtual Environment", test_virtual_env),
        ("Dependencies", test_dependencies),
        ("Environment File", test_env_file),
        ("Directory Structure", test_directories),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        result = test_func()
        results.append(result)
    
    print()
    print("=" * 60)
    
    if all(results):
        print("✓ ALL TESTS PASSED - Ready to run!")
        print()
        print("Next steps:")
        print("1. Add your API keys to .env file")
        print("2. Run: python main.py")
    else:
        print("✗ SOME TESTS FAILED")
        print()
        print("Fix the issues above, then run this test again")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
