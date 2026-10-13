# Cold Start Dashboard - Troubleshooting Guide

## 🚨 Quick Fixes

### Dashboard Won't Load
**Problem**: Browser shows "This site can't be reached" or loading spinner
**Solutions**:
1. **Wait 15 seconds** - Initial load takes time for ML models
2. **Refresh the page** - Sometimes resources need to reload
3. **Check the terminal** - Look for error messages in the console
4. **Try a different browser** - Chrome works best
5. **Clear browser cache** - Ctrl+F5 (Windows) or Cmd+Shift+R (Mac)

### Predictions Not Working
**Problem**: "Error making prediction" or no results shown
**Solutions**:
1. **Check System Monitoring** - Go to the monitoring section to see service status
2. **Wait and retry** - AWS services may be temporarily unavailable
3. **Try different parameters** - Some combinations may cause timeouts
4. **Check internet connection** - Predictions require AWS API access

### Data Not Updating
**Problem**: Tables and metrics show old data
**Solutions**:
1. **Toggle auto-refresh** - Turn off and on in the sidebar
2. **Click manual refresh** - Force immediate data update
3. **Check AWS credentials** - Data comes from DynamoDB
4. **Wait 30 seconds** - Auto-refresh has a 30-second cycle

## 🔧 Installation Issues

### Python Installation Problems

#### "Python not found" Error
```bash
❌ Python not found in PATH
```
**Solutions**:
1. **Install Python 3.8+** from https://python.org/downloads
2. **Add Python to PATH** during installation
3. **Restart terminal** after installation
4. **Try different commands**: `python3`, `python`, `py`

#### "Permission denied" Error
```bash
❌ Permission denied when installing packages
```
**Solutions**:
1. **Use virtual environment**:
   ```bash
   python -m venv dashboard_env
   # Windows:
   dashboard_env\Scripts\activate
   # Mac/Linux:
   source dashboard_env/bin/activate
   pip install -r requirements.txt
   ```
2. **Use --user flag**:
   ```bash
   pip install --user -r requirements.txt
   ```
3. **Run as administrator** (Windows) or use `sudo` (Mac/Linux)

### Dependency Installation Issues

#### "Package not found" Errors
```bash
❌ Could not find a version that satisfies the requirement
```
**Solutions**:
1. **Update pip**:
   ```bash
   python -m pip install --upgrade pip
   ```
2. **Use specific versions**:
   ```bash
   pip install streamlit==1.28.1
   ```
3. **Check Python version** - Some packages require Python 3.8+

#### "Build failed" Errors
```bash
❌ Failed building wheel for [package]
```
**Solutions**:
1. **Install build tools**:
   - Windows: Install Visual Studio Build Tools
   - Mac: Install Xcode Command Line Tools: `xcode-select --install`
   - Linux: Install build-essential: `sudo apt-get install build-essential`
2. **Use pre-compiled wheels**:
   ```bash
   pip install --only-binary=all -r requirements.txt
   ```

## 🌐 Network and Access Issues

### Public URL Problems

#### ngrok Not Working
```bash
❌ ngrok is not installed or not in PATH
```
**Solutions**:
1. **Install ngrok** from https://ngrok.com/download
2. **Add to PATH** or place in project directory
3. **Get auth token** from ngrok dashboard
4. **Set environment variable**:
   ```bash
   export NGROK_AUTH_TOKEN=your_token_here
   ```

#### "Tunnel not found" Error
```bash
❌ Failed to get ngrok public URL
```
**Solutions**:
1. **Wait 10 seconds** - Tunnel establishment takes time
2. **Check ngrok process** - Look for ngrok in task manager/activity monitor
3. **Restart ngrok**:
   ```bash
   pkill ngrok  # Kill existing processes
   python deploy_external.py  # Restart
   ```
4. **Check firewall** - Ensure port 4040 is not blocked

### Slow Performance

#### Dashboard Loads Slowly
**Symptoms**: Pages take >30 seconds to load
**Solutions**:
1. **Use Chrome browser** - Best performance and compatibility
2. **Close other tabs** - Free up browser memory
3. **Check internet speed** - Minimum 1 Mbps recommended
4. **Disable browser extensions** - Ad blockers may interfere
5. **Try incognito mode** - Eliminates cache/extension issues

#### Predictions Take Too Long
**Symptoms**: Predictions timeout or take >10 seconds
**Solutions**:
1. **Check AWS region** - Use us-east-1 for best performance
2. **Retry prediction** - SageMaker endpoints may be cold starting
3. **Simplify parameters** - Some combinations are computationally intensive
4. **Check system monitoring** - Look for AWS service issues

## 🔐 AWS Configuration Issues

### Credentials Problems

#### "Access Denied" Errors
```bash
❌ An error occurred (AccessDenied) when calling the [operation]
```
**Solutions**:
1. **Check AWS credentials**:
   ```bash
   aws configure list  # If AWS CLI installed
   ```
2. **Set environment variables**:
   ```bash
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=us-east-1
   ```
3. **Use demo mode** - Set `DEMO_MODE=true` for limited functionality
4. **Contact administrator** - Request proper IAM permissions

#### "Region not found" Errors
```bash
❌ The specified region does not exist
```
**Solutions**:
1. **Set correct region**:
   ```bash
   export AWS_DEFAULT_REGION=us-east-1
   ```
2. **Check .env file** - Ensure AWS_DEFAULT_REGION is set
3. **Use standard regions** - us-east-1, us-west-2, eu-west-1

### Service Unavailable Issues

#### DynamoDB Connection Failed
**Symptoms**: "Error fetching data" in data visualization
**Solutions**:
1. **Check table exists** - ETLFeatureData table must be created
2. **Verify permissions** - Need dynamodb:Query and dynamodb:Scan
3. **Check region** - Table and credentials must be in same region
4. **Use demo data** - Dashboard can run with simulated data

#### SageMaker Endpoints Not Found
**Symptoms**: "Endpoint not found" in predictions
**Solutions**:
1. **Check endpoint names** in .env file:
   ```
   XGBOOST_ENDPOINT=cold-start-xgboost-serverless
   RF_ENDPOINT=cold-start-rf-serverless
   ```
2. **Verify endpoints exist** in AWS console
3. **Check endpoint status** - Must be "InService"
4. **Use mock predictions** - Dashboard can simulate predictions

## 🖥️ Operating System Specific Issues

### Windows Issues

#### "Command not found" Errors
**Problem**: `python` or `pip` commands not recognized
**Solutions**:
1. **Use Python Launcher**:
   ```cmd
   py -m pip install -r requirements.txt
   py -m streamlit run app.py
   ```
2. **Add to PATH** - During Python installation, check "Add to PATH"
3. **Use full path**:
   ```cmd
   C:\Python39\python.exe -m streamlit run app.py
   ```

#### Port Already in Use
```cmd
❌ Port 8501 is already in use
```
**Solutions**:
1. **Kill existing process**:
   ```cmd
   netstat -ano | findstr :8501
   taskkill /PID [process_id] /F
   ```
2. **Use different port**:
   ```cmd
   streamlit run app.py --server.port 8502
   ```

### Mac/Linux Issues

#### Permission Errors
```bash
❌ Permission denied: '/usr/local/lib/python3.x/site-packages'
```
**Solutions**:
1. **Use virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Use --user flag**:
   ```bash
   pip install --user -r requirements.txt
   ```

#### "Address already in use" Error
```bash
❌ OSError: [Errno 48] Address already in use
```
**Solutions**:
1. **Find and kill process**:
   ```bash
   lsof -ti:8501 | xargs kill -9
   ```
2. **Use different port**:
   ```bash
   streamlit run app.py --server.port 8502
   ```

## 📱 Browser Compatibility Issues

### Chrome (Recommended)
- **Version**: 90+ required
- **Issues**: Generally none
- **Performance**: Best

### Firefox
- **Version**: 88+ required
- **Common Issue**: Slower chart rendering
- **Solution**: Enable hardware acceleration in settings

### Safari
- **Version**: 14+ required
- **Common Issue**: WebSocket connection problems
- **Solution**: Disable "Prevent cross-site tracking" for the dashboard

### Edge
- **Version**: 90+ required
- **Common Issue**: Compatibility mode interference
- **Solution**: Ensure not running in IE compatibility mode

### Mobile Browsers
- **Supported**: iOS Safari 14+, Chrome Mobile 90+
- **Limitations**: Some charts may not render properly
- **Recommendation**: Use desktop browser for full experience

## 🔍 Debugging Steps

### Enable Debug Mode
1. **Set debug environment**:
   ```bash
   export STREAMLIT_LOGGER_LEVEL=debug
   export DEBUG=true
   ```
2. **Run with verbose output**:
   ```bash
   streamlit run app.py --logger.level debug
   ```

### Check Logs
1. **Streamlit logs**: Look in terminal output
2. **Browser console**: F12 → Console tab
3. **Network tab**: F12 → Network tab to see failed requests
4. **AWS CloudWatch**: If you have access, check Lambda and API Gateway logs

### Test Components Individually
1. **Test AWS connection**:
   ```python
   python -c "from services.aws_clients import AWSClients; print('AWS OK')"
   ```
2. **Test configuration**:
   ```python
   python -c "from config import config_manager; print(config_manager.validate_configuration())"
   ```
3. **Test basic Streamlit**:
   ```python
   python -c "import streamlit; print('Streamlit OK')"
   ```

## 📞 Getting Help

### Self-Help Resources
1. **Check this troubleshooting guide** - Most issues are covered here
2. **Read the External Examiner Guide** - Comprehensive usage instructions
3. **Check the FAQ** - Common questions and answers
4. **Review error messages** - Often contain specific solution hints

### Contact Support
If you're still having issues:

1. **Gather information**:
   - Operating system and version
   - Python version (`python --version`)
   - Browser and version
   - Exact error message
   - Steps to reproduce the problem

2. **Try minimal setup**:
   ```bash
   python quick_deploy.py
   ```

3. **Contact the demonstrator** with:
   - Description of the problem
   - Error messages (copy/paste exact text)
   - What you were trying to do
   - Your system information

### Emergency Fallback
If nothing works, you can:
1. **Use the pre-deployed public URL** (if provided)
2. **Watch a recorded demo** (if available)
3. **Schedule a live demonstration** with screen sharing

## ✅ Verification Checklist

Before contacting support, verify:

- [ ] Python 3.8+ is installed and in PATH
- [ ] All dependencies installed successfully (`pip list | grep streamlit`)
- [ ] .env file exists (copy from .env.example if needed)
- [ ] Port 8501 is not blocked by firewall
- [ ] Internet connection is working
- [ ] Browser is supported version (Chrome 90+, Firefox 88+, etc.)
- [ ] No antivirus/firewall blocking the application
- [ ] Tried refreshing the browser page
- [ ] Waited at least 15 seconds for initial load

## 🎯 Common Error Messages

### "ModuleNotFoundError: No module named 'streamlit'"
**Solution**: Install dependencies with `pip install -r requirements.txt`

### "ConnectionError: Unable to connect to AWS"
**Solution**: Check internet connection and AWS credentials

### "FileNotFoundError: [Errno 2] No such file or directory: 'app.py'"
**Solution**: Run commands from the cold-start-dashboard directory

### "PermissionError: [Errno 13] Permission denied"
**Solution**: Use virtual environment or --user flag with pip

### "Port 8501 is already in use"
**Solution**: Kill existing Streamlit process or use different port

### "ngrok: command not found"
**Solution**: Install ngrok from https://ngrok.com/download

Remember: Most issues are temporary and can be resolved by waiting a moment and trying again. The dashboard is designed to be resilient and will recover from most transient problems automatically.