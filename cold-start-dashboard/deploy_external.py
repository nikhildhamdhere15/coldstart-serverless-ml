#!/usr/bin/env python3
"""
External Deployment Script for Cold Start Dashboard
Configures and launches the dashboard for external examiner access
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path
from config import config_manager

class ExternalDeploymentManager:
    """Manages external deployment of the dashboard"""
    
    def __init__(self):
        self.config = config_manager.dashboard_config
        self.dashboard_process = None
        self.ngrok_process = None
        
    def validate_environment(self) -> bool:
        """Validate that the environment is ready for external deployment"""
        print("🔍 Validating deployment environment...")
        
        # Check if Streamlit is installed
        try:
            import streamlit
            print(f"✅ Streamlit {streamlit.__version__} is installed")
        except ImportError:
            print("❌ Streamlit is not installed. Run: pip install -r requirements.txt")
            return False
        
        # Check if app_simple.py exists
        app_path = Path("app_simple.py")
        if not app_path.exists():
            print("❌ app_simple.py not found in current directory")
            return False
        print("✅ Simple dashboard application found")
        
        # Validate AWS configuration
        aws_status = config_manager.validate_configuration()
        if not all(aws_status.values()):
            print("⚠️  AWS configuration issues detected:")
            for item, status in aws_status.items():
                icon = "✅" if status else "❌"
                print(f"   {icon} {item.replace('_', ' ').title()}")
            print("   Dashboard will run with limited functionality")
        else:
            print("✅ AWS configuration is valid")
        
        return True
    
    def setup_streamlit_config(self):
        """Ensure Streamlit configuration is set up for external access"""
        print("⚙️  Configuring Streamlit for external access...")
        
        # Create .streamlit directory if it doesn't exist
        streamlit_dir = Path(".streamlit")
        streamlit_dir.mkdir(exist_ok=True)
        
        # The config.toml file should already exist from the previous step
        config_path = streamlit_dir / "config.toml"
        if config_path.exists():
            print("✅ Streamlit configuration found")
        else:
            print("❌ Streamlit configuration missing")
            return False
        
        return True
    
    def start_dashboard(self) -> bool:
        """Start the Streamlit dashboard"""
        print(f"🚀 Starting dashboard on port {self.config.public_port}...")
        
        try:
            # Build Streamlit command with simple clean app
            cmd = [
                sys.executable, "-m", "streamlit", "run", "app_simple.py",
                "--server.port", str(self.config.public_port),
                "--server.address", self.config.server_address,
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false",
                "--server.enableCORS", str(self.config.enable_cors).lower(),
                "--server.enableXsrfProtection", str(self.config.enable_xsrf_protection).lower()
            ]
            
            # Start the dashboard process
            self.dashboard_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait a moment for startup
            time.sleep(3)
            
            # Check if process is still running
            if self.dashboard_process.poll() is None:
                print(f"✅ Dashboard started successfully (PID: {self.dashboard_process.pid})")
                print(f"🌐 Local access: http://localhost:{self.config.public_port}")
                return True
            else:
                stdout, stderr = self.dashboard_process.communicate()
                print(f"❌ Dashboard failed to start:")
                print(f"   stdout: {stdout}")
                print(f"   stderr: {stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start dashboard: {str(e)}")
            return False
    
    def setup_ngrok(self) -> bool:
        """Set up ngrok tunnel for public access"""
        if not self.config.ngrok_auth_token:
            print("⚠️  No ngrok auth token configured. Skipping public URL setup.")
            print("   Set NGROK_AUTH_TOKEN environment variable to enable public access.")
            return False
        
        print("🌐 Setting up ngrok tunnel for public access...")
        
        try:
            # Check if ngrok is installed
            result = subprocess.run(["ngrok", "version"], capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ ngrok is not installed or not in PATH")
                print("   Install from: https://ngrok.com/download")
                return False
            
            print(f"✅ ngrok found: {result.stdout.strip()}")
            
            # Authenticate ngrok
            auth_result = subprocess.run(
                ["ngrok", "authtoken", self.config.ngrok_auth_token],
                capture_output=True,
                text=True
            )
            
            if auth_result.returncode != 0:
                print(f"❌ ngrok authentication failed: {auth_result.stderr}")
                return False
            
            print("✅ ngrok authenticated successfully")
            
            # Start ngrok tunnel
            self.ngrok_process = subprocess.Popen(
                ["ngrok", "http", str(self.config.public_port), "--log=stdout"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for ngrok to establish tunnel
            print("⏳ Establishing ngrok tunnel...")
            time.sleep(5)
            
            # Get public URL
            public_url = self.get_ngrok_public_url()
            if public_url:
                print(f"🌍 Public URL: {public_url}")
                print("📋 Share this URL with external examiners")
                return True
            else:
                print("❌ Failed to get ngrok public URL")
                return False
                
        except Exception as e:
            print(f"❌ Failed to setup ngrok: {str(e)}")
            return False
    
    def get_ngrok_public_url(self) -> str:
        """Get the public URL from ngrok API"""
        try:
            import requests
            import json
            
            # Query ngrok local API
            response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
            if response.status_code == 200:
                tunnels = response.json()
                for tunnel in tunnels.get("tunnels", []):
                    if tunnel.get("proto") == "https":
                        return tunnel.get("public_url")
            
            return None
            
        except Exception:
            return None
    
    def display_access_info(self):
        """Display access information for users"""
        print("\n" + "="*60)
        print("🎉 COLD START DASHBOARD - EXTERNAL ACCESS READY")
        print("="*60)
        print(f"📊 Dashboard Title: {self.config.title}")
        print(f"🌐 Local Access: http://localhost:{self.config.public_port}")
        
        public_url = self.get_ngrok_public_url()
        if public_url:
            print(f"🌍 Public Access: {public_url}")
            print("\n📋 INSTRUCTIONS FOR EXTERNAL EXAMINERS:")
            print(f"   1. Open your web browser")
            print(f"   2. Navigate to: {public_url}")
            print(f"   3. The dashboard will load automatically")
            print(f"   4. Use the sidebar to navigate between sections")
        else:
            print("🔒 Public Access: Not configured (local access only)")
        
        print(f"\n⚙️  Configuration:")
        print(f"   • Session Timeout: {self.config.session_timeout // 60} minutes")
        print(f"   • Max Concurrent Users: {self.config.max_concurrent_users}")
        print(f"   • Auto Refresh: {self.config.auto_refresh_interval} seconds")
        
        print(f"\n🛑 To stop the dashboard:")
        print(f"   Press Ctrl+C in this terminal")
        print("="*60)
    
    def cleanup(self):
        """Clean up processes on shutdown"""
        print("\n🛑 Shutting down dashboard...")
        
        if self.dashboard_process:
            try:
                self.dashboard_process.terminate()
                self.dashboard_process.wait(timeout=5)
                print("✅ Dashboard process terminated")
            except subprocess.TimeoutExpired:
                self.dashboard_process.kill()
                print("⚠️  Dashboard process killed (forced)")
            except Exception as e:
                print(f"❌ Error terminating dashboard: {str(e)}")
        
        if self.ngrok_process:
            try:
                self.ngrok_process.terminate()
                self.ngrok_process.wait(timeout=5)
                print("✅ ngrok tunnel closed")
            except subprocess.TimeoutExpired:
                self.ngrok_process.kill()
                print("⚠️  ngrok process killed (forced)")
            except Exception as e:
                print(f"❌ Error terminating ngrok: {str(e)}")
    
    def run(self):
        """Main deployment workflow"""
        try:
            # Validate environment
            if not self.validate_environment():
                print("❌ Environment validation failed. Please fix issues and try again.")
                return False
            
            # Setup Streamlit configuration
            if not self.setup_streamlit_config():
                print("❌ Streamlit configuration failed.")
                return False
            
            # Start dashboard
            if not self.start_dashboard():
                print("❌ Dashboard startup failed.")
                return False
            
            # Setup ngrok (optional)
            ngrok_success = self.setup_ngrok()
            
            # Display access information
            self.display_access_info()
            
            # Keep running until interrupted
            print("\n⏳ Dashboard is running. Press Ctrl+C to stop...")
            
            try:
                while True:
                    time.sleep(1)
                    
                    # Check if dashboard process is still running
                    if self.dashboard_process.poll() is not None:
                        print("❌ Dashboard process has stopped unexpectedly")
                        break
                        
            except KeyboardInterrupt:
                print("\n🛑 Shutdown requested by user")
            
            return True
            
        except Exception as e:
            print(f"❌ Deployment failed: {str(e)}")
            return False
        
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    print("🚀 Cold Start Dashboard - External Deployment")
    print("=" * 50)
    
    # Change to dashboard directory if needed
    dashboard_dir = Path(__file__).parent
    if dashboard_dir != Path.cwd():
        os.chdir(dashboard_dir)
        print(f"📁 Changed to dashboard directory: {dashboard_dir}")
    
    # Create deployment manager
    deployment_manager = ExternalDeploymentManager()
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}")
        deployment_manager.cleanup()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run deployment
    success = deployment_manager.run()
    
    if success:
        print("✅ Deployment completed successfully")
        return 0
    else:
        print("❌ Deployment failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())