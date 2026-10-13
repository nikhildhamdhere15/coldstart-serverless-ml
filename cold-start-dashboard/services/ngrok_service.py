"""
Ngrok Service for Cold Start Dashboard
Manages ngrok tunnels for external access and public URL generation
"""

import time
import requests
import subprocess
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class NgrokTunnel:
    """Represents an active ngrok tunnel"""
    public_url: str
    local_port: int
    protocol: str
    tunnel_name: str
    created_at: datetime
    is_active: bool = True

@dataclass
class NgrokStatus:
    """Status information for ngrok service"""
    is_installed: bool
    is_authenticated: bool
    is_running: bool
    active_tunnels: list
    api_available: bool
    version: Optional[str] = None

class NgrokService:
    """Service for managing ngrok tunnels and public URL access"""
    
    def __init__(self, auth_token: Optional[str] = None):
        self.auth_token = auth_token
        self.process = None
        self.api_url = "http://localhost:4040/api"
        self.tunnel_info = None
        
    def check_installation(self) -> bool:
        """Check if ngrok is installed and accessible"""
        try:
            result = subprocess.run(
                ["ngrok", "version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def get_version(self) -> Optional[str]:
        """Get ngrok version information"""
        try:
            result = subprocess.run(
                ["ngrok", "version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode == 0:
                # Extract version from output
                version_line = result.stdout.strip().split('\n')[0]
                return version_line.replace('ngrok version ', '')
            return None
        except Exception:
            return None
    
    def authenticate(self) -> bool:
        """Authenticate ngrok with the provided auth token"""
        if not self.auth_token:
            logger.warning("No ngrok auth token provided")
            return False
        
        try:
            result = subprocess.run(
                ["ngrok", "authtoken", self.auth_token],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("Ngrok authentication successful")
                return True
            else:
                logger.error(f"Ngrok authentication failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to authenticate ngrok: {str(e)}")
            return False
    
    def start_tunnel(self, port: int, protocol: str = "http") -> bool:
        """Start an ngrok tunnel for the specified port"""
        if not self.check_installation():
            logger.error("Ngrok is not installed or not accessible")
            return False
        
        if self.auth_token and not self.authenticate():
            logger.error("Ngrok authentication failed")
            return False
        
        try:
            # Start ngrok tunnel
            cmd = ["ngrok", protocol, str(port), "--log=stdout"]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for tunnel to establish
            logger.info(f"Starting ngrok tunnel for port {port}...")
            time.sleep(5)
            
            # Verify tunnel is active
            if self.is_tunnel_active():
                tunnel_info = self.get_tunnel_info()
                if tunnel_info:
                    self.tunnel_info = tunnel_info
                    logger.info(f"Ngrok tunnel established: {tunnel_info.public_url}")
                    return True
            
            logger.error("Failed to establish ngrok tunnel")
            return False
            
        except Exception as e:
            logger.error(f"Failed to start ngrok tunnel: {str(e)}")
            return False
    
    def stop_tunnel(self):
        """Stop the active ngrok tunnel"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
                logger.info("Ngrok tunnel stopped")
            except subprocess.TimeoutExpired:
                self.process.kill()
                logger.warning("Ngrok process killed (forced)")
            except Exception as e:
                logger.error(f"Error stopping ngrok tunnel: {str(e)}")
            finally:
                self.process = None
                self.tunnel_info = None
    
    def is_tunnel_active(self) -> bool:
        """Check if ngrok tunnel is currently active"""
        try:
            response = requests.get(f"{self.api_url}/tunnels", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_tunnel_info(self) -> Optional[NgrokTunnel]:
        """Get information about the active tunnel"""
        try:
            response = requests.get(f"{self.api_url}/tunnels", timeout=5)
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                
                for tunnel in tunnels:
                    if tunnel.get("proto") in ["https", "http"]:
                        return NgrokTunnel(
                            public_url=tunnel.get("public_url", ""),
                            local_port=int(tunnel.get("config", {}).get("addr", "").split(":")[-1]),
                            protocol=tunnel.get("proto", ""),
                            tunnel_name=tunnel.get("name", ""),
                            created_at=datetime.now(),
                            is_active=True
                        )
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get tunnel info: {str(e)}")
            return None
    
    def get_public_url(self) -> Optional[str]:
        """Get the public URL of the active tunnel"""
        if self.tunnel_info:
            return self.tunnel_info.public_url
        
        tunnel_info = self.get_tunnel_info()
        if tunnel_info:
            self.tunnel_info = tunnel_info
            return tunnel_info.public_url
        
        return None
    
    def get_status(self) -> NgrokStatus:
        """Get comprehensive status of ngrok service"""
        is_installed = self.check_installation()
        version = self.get_version() if is_installed else None
        is_running = self.process is not None and self.process.poll() is None
        api_available = self.is_tunnel_active()
        
        active_tunnels = []
        if api_available:
            try:
                response = requests.get(f"{self.api_url}/tunnels", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    active_tunnels = data.get("tunnels", [])
            except Exception:
                pass
        
        return NgrokStatus(
            is_installed=is_installed,
            is_authenticated=bool(self.auth_token),
            is_running=is_running,
            active_tunnels=active_tunnels,
            api_available=api_available,
            version=version
        )
    
    def monitor_tunnel(self) -> Dict[str, Any]:
        """Monitor tunnel health and return status information"""
        status = {
            "tunnel_active": False,
            "public_url": None,
            "process_running": False,
            "api_accessible": False,
            "last_check": datetime.now().isoformat()
        }
        
        # Check if process is running
        if self.process:
            status["process_running"] = self.process.poll() is None
        
        # Check if API is accessible
        status["api_accessible"] = self.is_tunnel_active()
        
        # Get tunnel information
        if status["api_accessible"]:
            tunnel_info = self.get_tunnel_info()
            if tunnel_info:
                status["tunnel_active"] = True
                status["public_url"] = tunnel_info.public_url
        
        return status
    
    def restart_tunnel(self, port: int, protocol: str = "http") -> bool:
        """Restart the ngrok tunnel"""
        logger.info("Restarting ngrok tunnel...")
        
        # Stop existing tunnel
        self.stop_tunnel()
        
        # Wait a moment
        time.sleep(2)
        
        # Start new tunnel
        return self.start_tunnel(port, protocol)
    
    def get_tunnel_metrics(self) -> Dict[str, Any]:
        """Get tunnel usage metrics from ngrok API"""
        try:
            if not self.is_tunnel_active():
                return {}
            
            # Get tunnel details
            response = requests.get(f"{self.api_url}/tunnels", timeout=5)
            if response.status_code != 200:
                return {}
            
            data = response.json()
            tunnels = data.get("tunnels", [])
            
            metrics = {
                "tunnel_count": len(tunnels),
                "tunnels": []
            }
            
            for tunnel in tunnels:
                tunnel_metrics = {
                    "name": tunnel.get("name", ""),
                    "public_url": tunnel.get("public_url", ""),
                    "protocol": tunnel.get("proto", ""),
                    "local_addr": tunnel.get("config", {}).get("addr", ""),
                    "created_at": tunnel.get("created_at", "")
                }
                metrics["tunnels"].append(tunnel_metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get tunnel metrics: {str(e)}")
            return {}

class NgrokManager:
    """High-level manager for ngrok operations"""
    
    def __init__(self, auth_token: Optional[str] = None):
        self.service = NgrokService(auth_token)
        self.auto_restart = True
        self.monitoring_enabled = False
    
    def setup_public_access(self, port: int) -> Dict[str, Any]:
        """Set up public access and return status information"""
        result = {
            "success": False,
            "public_url": None,
            "error": None,
            "status": {}
        }
        
        try:
            # Check ngrok installation
            if not self.service.check_installation():
                result["error"] = "Ngrok is not installed. Please install from https://ngrok.com/download"
                return result
            
            # Start tunnel
            if self.service.start_tunnel(port):
                public_url = self.service.get_public_url()
                if public_url:
                    result["success"] = True
                    result["public_url"] = public_url
                    result["status"] = self.service.get_status().__dict__
                else:
                    result["error"] = "Failed to get public URL from ngrok"
            else:
                result["error"] = "Failed to start ngrok tunnel"
        
        except Exception as e:
            result["error"] = f"Setup failed: {str(e)}"
        
        return result
    
    def get_access_info(self) -> Dict[str, Any]:
        """Get current access information"""
        return {
            "ngrok_status": self.service.get_status().__dict__,
            "tunnel_info": self.service.tunnel_info.__dict__ if self.service.tunnel_info else None,
            "public_url": self.service.get_public_url(),
            "metrics": self.service.get_tunnel_metrics()
        }
    
    def cleanup(self):
        """Clean up ngrok resources"""
        self.service.stop_tunnel()

# Global ngrok manager instance
ngrok_manager = None

def get_ngrok_manager(auth_token: Optional[str] = None) -> NgrokManager:
    """Get or create global ngrok manager instance"""
    global ngrok_manager
    if ngrok_manager is None:
        ngrok_manager = NgrokManager(auth_token)
    return ngrok_manager