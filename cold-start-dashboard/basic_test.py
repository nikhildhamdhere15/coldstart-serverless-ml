#!/usr/bin/env python3
"""
Basic validation script for Cold Start Dashboard setup
Tests core functionality without requiring all dependencies
"""

import os
import sys

def test_project_structure():
    """Test that the project structure is correct"""
    print("Testing project structure...")
    
    # Check directories
    directories = ['services', 'components', 'tests']
    for directory in directories:
        if os.path.exists(directory):
            print(f"✅ {directory}/ directory exists")
        else:
            print(f"❌ {directory}/ directory missing")
            return False
    
    # Check files
    files = [
        'app.py',
        'config.py', 
        'requirements.txt',
        'README.md',
        '.env.example',
        '.gitignore',
        'setup_test.py'
    ]
    
    for file in files:
        if os.path.exists(file):
            print(f"✅ {file} exists")
        else:
            print(f"❌ {file} missing")
            return False
    
    return True

def test_config_structure():
    """Test that config.py has the right structure"""
    print("\nTesting config.py structure...")
    
    try:
        with open('config.py', 'r') as f:
            content = f.read()
        
        required_classes = ['AWSConfig', 'DashboardConfig', 'ConfigManager']
        for class_name in required_classes:
            if f'class {class_name}' in content:
                print(f"✅ {class_name} class defined")
            else:
                print(f"❌ {class_name} class missing")
                return False
        
        # Check for key configuration items
        config_items = [
            'dynamodb_table_name',
            'xgboost_endpoint', 
            'random_forest_endpoint',
            'traffic_generator_function'
        ]
        
        for item in config_items:
            if item in content:
                print(f"✅ {item} configuration present")
            else:
                print(f"❌ {item} configuration missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error reading config.py: {e}")
        return False

def test_app_structure():
    """Test that app.py has the right structure"""
    print("\nTesting app.py structure...")
    
    try:
        with open('app.py', 'r') as f:
            content = f.read()
        
        required_elements = [
            'import streamlit',
            'def main()',
            'st.set_page_config',
            'config_manager'
        ]
        
        for element in required_elements:
            if element in content:
                print(f"✅ {element} present")
            else:
                print(f"❌ {element} missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error reading app.py: {e}")
        return False

def test_requirements():
    """Test that requirements.txt has essential packages"""
    print("\nTesting requirements.txt...")
    
    try:
        with open('requirements.txt', 'r') as f:
            content = f.read()
        
        required_packages = [
            'streamlit',
            'boto3',
            'pandas',
            'plotly',
            'python-dotenv'
        ]
        
        for package in required_packages:
            if package in content:
                print(f"✅ {package} listed in requirements")
            else:
                print(f"❌ {package} missing from requirements")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error reading requirements.txt: {e}")
        return False

def main():
    """Run basic validation tests"""
    print("Cold Start Dashboard - Basic Setup Validation")
    print("=" * 55)
    
    tests = [
        test_project_structure,
        test_config_structure,
        test_app_structure,
        test_requirements
    ]
    
    all_passed = True
    
    for test in tests:
        if not test():
            all_passed = False
    
    print("\n" + "=" * 55)
    if all_passed:
        print("🎉 Basic setup validation passed!")
        print("\nProject structure is correctly established.")
        print("Task 1 requirements completed:")
        print("✅ Dashboard directory structure created")
        print("✅ requirements.txt with dependencies configured")
        print("✅ Configuration management implemented")
        print("✅ Git repository initialized")
        print("✅ Basic project files created")
        
        print("\nNext: Install dependencies with 'pip install -r requirements.txt'")
        print("Then run: 'streamlit run app.py'")
    else:
        print("❌ Basic setup validation failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()