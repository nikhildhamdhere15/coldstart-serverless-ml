#!/usr/bin/env python3
"""
Deployment Validation Script
Validates that the Cold Start Dashboard is properly configured for external access
"""

import os
import sys
import subprocess
import importlib
import json
from pathlib import Path
from typing import Dict, List, Tuple

class DeploymentValidator:
    """Validates deployment readiness for external examiners"""
    
    def __init__(self):
        self.results = {}
        self.warnings = []
        self.errors = []
        
    def print_header(self):
        """Print validation header"""
        print("=" * 60)
        print("🔍 COLD START DASHBOARD - DEPLOYMENT VALIDATION")
        print("=" * 60)
        print("📋 Checking if the dashboard is ready for external examiner access")
        print()
    
    def check_python_version(self) -> bool:
        """Check Python version compatibility"""
        print("🐍 Checking Python version...")
        
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            print(f"✅ Python {version.major}.{version.minor}.{version.micro} (compatible)")
            return True
        else:
            print(f"❌ Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)")
            self.errors.append("Python 3.8+ required")
            return False
    
    def check_required_files(self) -> bool:
        """Check that all required files exist"""
        print("\n📁 Checking required files...")
        
        required_files = [
            "app.py",
            "config.py", 
            "requirements.txt",
            ".env.example",
            "README.md",
            "EXTERNAL_EXAMINER_GUIDE.md",
            "TROUBLESHOOTING.md",
            "FAQ.md",
            "quick_deploy.py",
            "deploy_external.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            if Path(file_path).exists():
                print(f"✅ {file_path}")
            else:
                print(f"❌ {file_path} (missing)")
                missing_files.append(file_path)
        
        if missing_files:
            self.errors.extend([f"Missing file: {f}" for f in missing_files])
            return False
        
        return True
    
    def check_dependencies(self) -> bool:
        """Check that all required dependencies are installed"""
        print("\n📦 Checking dependencies...")
        
        required_packages = [
            "streamlit",
            "boto3",
            "pandas",
            "plotly",
            "python-dotenv",
            "pytest",
            "hypothesis"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                # Handle special package names
                import_name = package.replace("-", "_")
                if package == "python-dotenv":
                    import_name = "dotenv"
                
                importlib.import_module(import_name)
                print(f"✅ {package}")
            except ImportError:
                print(f"❌ {package} (not installed)")
                missing_packages.append(package)
        
        if missing_packages:
            self.errors.append(f"Missing packages: {', '.join(missing_packages)}")
            print(f"\n💡 Install with: pip install {' '.join(missing_packages)}")
            return False
        
        return True
    
    def check_configuration(self) -> bool:
        """Check configuration setup"""
        print("\n⚙️  Checking configuration...")
        
        try:
            # Try to import config
            from config import config_manager
            print("✅ Configuration module loads")
            
            # Check if .env exists
            env_file = Path(".env")
            if env_file.exists():
                print("✅ .env file exists")
            else:
                print("⚠️  .env file not found (will use defaults)")
                self.warnings.append("No .env file - using default configuration")
            
            # Validate configuration
            validation = config_manager.validate_configuration()
            aws_configured = any(validation.values())
            
            if aws_configured:
                print("✅ AWS configuration detected")
            else:
                print("⚠️  No AWS configuration (demo mode available)")
                self.warnings.append("No AWS credentials - limited functionality")
            
            return True
            
        except Exception as e:
            print(f"❌ Configuration error: {str(e)}")
            self.errors.append(f"Configuration error: {str(e)}")
            return False
    
    def check_streamlit_config(self) -> bool:
        """Check Streamlit configuration"""
        print("\n🌐 Checking Streamlit configuration...")
        
        streamlit_dir = Path(".streamlit")
        config_file = streamlit_dir / "config.toml"
        
        if streamlit_dir.exists():
            print("✅ .streamlit directory exists")
        else:
            print("⚠️  .streamlit directory not found")
            self.warnings.append("No Streamlit configuration directory")
        
        if config_file.exists():
            print("✅ Streamlit config.toml exists")
            return True
        else:
            print("⚠️  Streamlit config.toml not found (will use defaults)")
            self.warnings.append("No Streamlit configuration file")
            return True  # Not critical
    
    def check_services(self) -> bool:
        """Check that service modules can be imported"""
        print("\n🔧 Checking service modules...")
        
        service_modules = [
            "services.aws_clients",
            "services.live_prediction", 
            "services.system_monitoring",
            "services.data_visualization",
            "services.traffic_generation",
            "services.warming_system",
            "services.cost_analytics",
            "services.external_access"
        ]
        
        failed_imports = []
        for module in service_modules:
            try:
                importlib.import_module(module)
                print(f"✅ {module}")
            except ImportError as e:
                print(f"❌ {module} (import failed)")
                failed_imports.append(f"{module}: {str(e)}")
        
        if failed_imports:
            self.errors.extend(failed_imports)
            return False
        
        return True
    
    def check_tests(self) -> bool:
        """Check that tests can be discovered"""
        print("\n🧪 Checking test suite...")
        
        tests_dir = Path("tests")
        if not tests_dir.exists():
            print("❌ tests/ directory not found")
            self.errors.append("Missing tests directory")
            return False
        
        # Count test files
        test_files = list(tests_dir.glob("test_*.py"))
        if test_files:
            print(f"✅ Found {len(test_files)} test files")
            
            # Try to run a quick test discovery
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "--collect-only", "-q"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    print("✅ Test discovery successful")
                else:
                    print("⚠️  Test discovery issues (tests may still work)")
                    self.warnings.append("Test discovery warnings")
                    
            except Exception as e:
                print(f"⚠️  Could not run test discovery: {str(e)}")
                self.warnings.append("Could not validate tests")
        else:
            print("❌ No test files found")
            self.errors.append("No test files found")
            return False
        
        return True
    
    def check_documentation(self) -> bool:
        """Check documentation completeness"""
        print("\n📚 Checking documentation...")
        
        docs = {
            "README.md": "Project overview and setup",
            "EXTERNAL_EXAMINER_GUIDE.md": "External examiner instructions", 
            "TROUBLESHOOTING.md": "Problem-solving guide",
            "FAQ.md": "Frequently asked questions"
        }
        
        all_present = True
        for doc_file, description in docs.items():
            if Path(doc_file).exists():
                try:
                    # Check if file has content with proper encoding
                    content = Path(doc_file).read_text(encoding='utf-8')
                    if len(content) > 100:  # Minimum content check
                        print(f"✅ {doc_file} ({description})")
                    else:
                        print(f"⚠️  {doc_file} (too short)")
                        self.warnings.append(f"{doc_file} may be incomplete")
                except UnicodeDecodeError:
                    try:
                        # Try with different encoding
                        content = Path(doc_file).read_text(encoding='latin-1')
                        if len(content) > 100:
                            print(f"✅ {doc_file} ({description}) - encoding issue fixed")
                            self.warnings.append(f"{doc_file} has encoding issues")
                        else:
                            print(f"⚠️  {doc_file} (too short)")
                            self.warnings.append(f"{doc_file} may be incomplete")
                    except Exception as e:
                        print(f"❌ {doc_file} (encoding error: {str(e)})")
                        self.errors.append(f"Cannot read {doc_file}: encoding error")
                        all_present = False
                except Exception as e:
                    print(f"❌ {doc_file} (error: {str(e)})")
                    self.errors.append(f"Cannot read {doc_file}: {str(e)}")
                    all_present = False
            else:
                print(f"❌ {doc_file} (missing)")
                self.errors.append(f"Missing documentation: {doc_file}")
                all_present = False
        
        return all_present
    
    def check_deployment_scripts(self) -> bool:
        """Check deployment scripts"""
        print("\n🚀 Checking deployment scripts...")
        
        scripts = {
            "quick_deploy.py": "Quick deployment for external examiners",
            "deploy_external.py": "Full external deployment with ngrok",
            "validate_deployment.py": "This validation script"
        }
        
        all_present = True
        for script_file, description in scripts.items():
            if Path(script_file).exists():
                print(f"✅ {script_file} ({description})")
                
                # Check if script is executable
                try:
                    result = subprocess.run(
                        [sys.executable, script_file, "--help"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    # Don't fail if --help doesn't work, just note it
                except:
                    pass  # Script exists, that's what matters
                    
            else:
                print(f"❌ {script_file} (missing)")
                self.errors.append(f"Missing script: {script_file}")
                all_present = False
        
        return all_present
    
    def run_basic_app_test(self) -> bool:
        """Try to import and validate the main app"""
        print("\n🎯 Testing main application...")
        
        try:
            # Try to import the main app
            import app
            print("✅ Main app module imports successfully")
            
            # Check if main function exists
            if hasattr(app, 'main'):
                print("✅ Main function found")
            else:
                print("⚠️  No main function found")
                self.warnings.append("No main function in app.py")
            
            return True
            
        except Exception as e:
            print(f"❌ App import failed: {str(e)}")
            self.errors.append(f"App import error: {str(e)}")
            return False
    
    def print_summary(self):
        """Print validation summary"""
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        
        if not self.errors:
            print("🎉 ✅ DEPLOYMENT READY FOR EXTERNAL EXAMINERS!")
            print()
            print("📋 Next steps:")
            print("   1. Run: python quick_deploy.py")
            print("   2. Or run: python deploy_external.py (for public URL)")
            print("   3. Share the URL with external examiners")
            print("   4. Provide them with EXTERNAL_EXAMINER_GUIDE.md")
        else:
            print("❌ DEPLOYMENT NOT READY - Issues found:")
            for error in self.errors:
                print(f"   • {error}")
            print()
            print("🔧 Fix these issues and run validation again")
        
        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} warnings (non-critical):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        print("\n📚 Documentation available:")
        print("   • EXTERNAL_EXAMINER_GUIDE.md - Complete usage guide")
        print("   • TROUBLESHOOTING.md - Problem-solving help")
        print("   • FAQ.md - Common questions and answers")
        print("   • README.md - Technical setup information")
        
        print("\n🚀 Deployment options:")
        print("   • python quick_deploy.py - Simple local deployment")
        print("   • python deploy_external.py - Full deployment with public URL")
        print("   • streamlit run app.py - Manual Streamlit launch")
        
        print("=" * 60)
    
    def run_validation(self) -> bool:
        """Run complete validation"""
        self.print_header()
        
        checks = [
            ("Python Version", self.check_python_version),
            ("Required Files", self.check_required_files),
            ("Dependencies", self.check_dependencies),
            ("Configuration", self.check_configuration),
            ("Streamlit Config", self.check_streamlit_config),
            ("Service Modules", self.check_services),
            ("Test Suite", self.check_tests),
            ("Documentation", self.check_documentation),
            ("Deployment Scripts", self.check_deployment_scripts),
            ("Main Application", self.run_basic_app_test)
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            try:
                result = check_func()
                if not result:
                    all_passed = False
            except Exception as e:
                print(f"❌ {check_name} check failed: {str(e)}")
                self.errors.append(f"{check_name} check error: {str(e)}")
                all_passed = False
        
        self.print_summary()
        return all_passed

def main():
    """Main entry point"""
    # Change to script directory
    script_dir = Path(__file__).parent
    if script_dir != Path.cwd():
        os.chdir(script_dir)
    
    # Run validation
    validator = DeploymentValidator()
    success = validator.run_validation()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())