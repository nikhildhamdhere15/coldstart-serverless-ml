#!/usr/bin/env python3
"""
Quick Deployment Script for External Examiners
Simplified one-command setup for the Cold Start Dashboard
"""

import os
import sys
import subprocess
import time
import platform
from pathlib import Path

class QuickDeployment:
    """Simplified deployment for external examiners"""
    
    def __init__(self):
        self.python_cmd = self.get_python_command()
        self.pip_cmd = self.get_pip_command()
        
    def get_python_command(self):
        """Get the correct Python command for this system"""
        # Try different Python commands
        for cmd in ['python3', 'python']:
            try:
                result = subprocess.run([cmd, '--version'], capture_output=True, text=True)
                if result.returncode == 0 and 'Python 3' in result.stdout:
                    return cmd
            except FileNotFoundError:
                continue
        return 'python'  # Fallback
    
    def get_pip_command(self):
        """Get the correct pip command for this system"""
        # Try different pip commands
        for cmd in ['pip3', 'pip']:
            try:
                result = subprocess.run([cmd, '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    return cmd
            except FileNotFoundError:
                continue
        return 'pip'  # Fallback
    
    def print_header(self):
        """Print welcome header"""
        print("=" * 60)
        print("🚀 COLD START DASHBOARD - QUICK DEPLOYMENT")
        print("=" * 60)
        print("📋 This script will automatically set up the dashboard for you")
        print("⏱️  Estimated time: 2-3 minutes")
        print("🌐 You'll get a local URL to access the dashboard")
        print()
    
    def check_python(self):
        """Check Python installation"""
        print("🔍 Checking Python installation...")
        
        try:
            result = subprocess.run([self.python_cmd, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✅ Found {version}")
                
                # Check if it's Python 3.8+
                version_parts = version.split()[1].split('.')
                major, minor = int(version_parts[0]), int(version_parts[1])
                
                if major >= 3 and minor >= 8:
                    return True
                else:
                    print(f"⚠️  Python 3.8+ recommended, found {major}.{minor}")
                    return True  # Still try to continue
            else:
                print("❌ Python not found")
                return False
                
        except FileNotFoundError:
            print("❌ Python not found in PATH")
            return False
    
    def install_dependencies(self):
        """Install required dependencies"""
        print("\n📦 Installing dependencies...")
        
        # Check if requirements.txt exists
        if not Path("requirements.txt").exists():
            print("❌ requirements.txt not found")
            return False
        
        try:
            # Install dependencies
            print("   Installing packages (this may take 1-2 minutes)...")
            result = subprocess.run(
                [self.pip_cmd, 'install', '-r', 'requirements.txt'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✅ Dependencies installed successfully")
                return True
            else:
                print(f"❌ Failed to install dependencies:")
                print(f"   {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error installing dependencies: {str(e)}")
            return False
    
    def setup_environment(self):
        """Set up environment configuration"""
        print("\n⚙️  Setting up environment...")
        
        # Check if .env exists, if not create from example
        env_file = Path(".env")
        env_example = Path(".env.example")
        
        if not env_file.exists() and env_example.exists():
            try:
                # Copy .env.example to .env
                with open(env_example, 'r') as src, open(env_file, 'w') as dst:
                    dst.write(src.read())
                print("✅ Environment file created from template")
            except Exception as e:
                print(f"⚠️  Could not create .env file: {str(e)}")
        
        # Set minimal environment for demo mode
        os.environ['DEMO_MODE'] = 'true'
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
        
        print("✅ Environment configured for demo mode")
        return True
    
    def start_dashboard(self):
        """Start the dashboard"""
        print("\n🚀 Starting the dashboard...")
        
        try:
            # Check if app.py exists
            if not Path("app.py").exists():
                print("❌ app.py not found")
                return False
            
            print("   Launching Streamlit (this may take 10-15 seconds)...")
            print("   📱 Your browser should open automatically")
            print("   🌐 If not, look for the 'Local URL' below")
            print()
            
            # Start Streamlit
            cmd = [
                self.python_cmd, '-m', 'streamlit', 'run', 'app.py',
                '--server.headless', 'false',  # Allow browser opening
                '--browser.gatherUsageStats', 'false'
            ]
            
            # Execute the command
            subprocess.run(cmd)
            
        except KeyboardInterrupt:
            print("\n🛑 Dashboard stopped by user")
            return True
        except Exception as e:
            print(f"❌ Failed to start dashboard: {str(e)}")
            return False
    
    def print_instructions(self):
        """Print usage instructions"""
        print("\n" + "=" * 60)
        print("🎉 DASHBOARD SETUP COMPLETE!")
        print("=" * 60)
        print("📋 NEXT STEPS:")
        print("   1. Your browser should open automatically")
        print("   2. If not, look for 'Local URL' in the output above")
        print("   3. The dashboard will load in 10-15 seconds")
        print("   4. Use the sidebar to navigate between sections")
        print()
        print("🎯 QUICK DEMO GUIDE:")
        print("   • Try the 'Live Predictions' section first")
        print("   • Adjust the sliders to see risk predictions")
        print("   • Check 'System Monitoring' for live metrics")
        print("   • Generate test traffic in the 'Traffic Generation' section")
        print()
        print("🆘 TROUBLESHOOTING:")
        print("   • If dashboard won't load: wait 15 seconds, then refresh")
        print("   • If predictions don't work: check 'System Monitoring'")
        print("   • For help: see EXTERNAL_EXAMINER_GUIDE.md")
        print()
        print("🛑 TO STOP: Press Ctrl+C in this terminal")
        print("=" * 60)
    
    def run(self):
        """Main deployment process"""
        self.print_header()
        
        # Step 1: Check Python
        if not self.check_python():
            print("\n❌ SETUP FAILED: Python 3.8+ is required")
            print("   Please install Python from: https://python.org/downloads")
            return False
        
        # Step 2: Install dependencies
        if not self.install_dependencies():
            print("\n❌ SETUP FAILED: Could not install dependencies")
            print("   Try running manually: pip install -r requirements.txt")
            return False
        
        # Step 3: Setup environment
        if not self.setup_environment():
            print("\n❌ SETUP FAILED: Could not configure environment")
            return False
        
        # Step 4: Print instructions
        self.print_instructions()
        
        # Step 5: Start dashboard
        print("⏳ Starting dashboard in 3 seconds...")
        time.sleep(3)
        
        return self.start_dashboard()

def main():
    """Main entry point"""
    # Change to script directory
    script_dir = Path(__file__).parent
    if script_dir != Path.cwd():
        os.chdir(script_dir)
    
    # Check if we're in the right directory
    if not Path("app.py").exists():
        print("❌ ERROR: app.py not found")
        print("   Please run this script from the cold-start-dashboard directory")
        return 1
    
    # Run deployment
    deployment = QuickDeployment()
    success = deployment.run()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())