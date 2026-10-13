#!/usr/bin/env python3
"""
Setup validation script for Cold Start Dashboard
Tests configuration management and basic functionality
"""

import sys
import os
import importlib.util

def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        # Test config module
        from config import config_manager, AWSConfig, DashboardConfig
        print("✅ Configuration module imported successfully")
        
        # Test configuration validation
        config_status = config_manager.validate_configuration()
        print(f"✅ Configuration validation completed: {config_status}")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_dependencies():
    """Test that required dependencies are available"""
    print("\nTesting dependencies...")
    
    required_packages = [
        'streamlit',
        'boto3',
        'pandas',
        'plotly',
        'requests',
        'python-dotenv'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - Not installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def test_directory_structure():
    """Test that all required directories exist"""
    print("\nTesting directory structure...")
    
    required_dirs = [
        'services',
        'components', 
        'tests'
    ]
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name) and os.path.isdir(dir_name):
            print(f"✅ {dir_name}/ directory exists")
        else:
            print(f"❌ {dir_name}/ directory missing")
            return False
    
    return True

def test_files():
    """Test that all required files exist"""
    print("\nTesting required files...")
    
    required_files = [
        'app.py',
        'config.py',
        'requirements.txt',
        'README.md',
        '.env.example',
        '.gitignore'
    ]
    
    for file_name in required_files:
        if os.path.exists(file_name) and os.path.isfile(file_name):
            print(f"✅ {file_name}")
        else:
            print(f"❌ {file_name} missing")
            return False
    
    return True

def main():
    """Run all setup tests"""
    print("Cold Start Dashboard - Setup Validation")
    print("=" * 50)
    
    tests = [
        test_directory_structure,
        test_files,
        test_dependencies,
        test_imports
    ]
    
    all_passed = True
    
    for test in tests:
        if not test():
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All setup tests passed! Dashboard is ready for development.")
        print("\nNext steps:")
        print("1. Copy .env.example to .env and configure your AWS credentials")
        print("2. Run: streamlit run app.py")
        print("3. Open your browser to the displayed URL")
    else:
        print("❌ Some setup tests failed. Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()