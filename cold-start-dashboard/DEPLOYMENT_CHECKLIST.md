# Cold Start Dashboard - Deployment Checklist

## 📋 Pre-Deployment Validation

### ✅ System Requirements Check
- [ ] **Python 3.8+** installed and accessible via `python` or `python3`
- [ ] **pip** package manager available
- [ ] **Internet connection** for AWS API access and package installation
- [ ] **Port 8501** available (or alternative port configured)
- [ ] **2GB+ RAM** available for optimal performance

### ✅ Project Files Validation
Run the validation script to check all components:
```bash
python validate_deployment.py
```

Expected output: "🎉 ✅ DEPLOYMENT READY FOR EXTERNAL EXAMINERS!"

### ✅ Dependencies Installation
```bash
pip install -r requirements.txt
```

Verify key packages are installed:
- [ ] `streamlit >= 1.28.1`
- [ ] `boto3 >= 1.34.0`
- [ ] `pandas >= 2.1.4`
- [ ] `plotly >= 5.17.0`
- [ ] `python-dotenv >= 1.0.0`

### ✅ AWS Configuration (Optional but Recommended)
For full functionality, configure AWS access:
- [ ] **AWS credentials** set (access key, secret key, region)
- [ ] **DynamoDB table** "ETLFeatureData" accessible
- [ ] **SageMaker endpoints** deployed and "InService"
- [ ] **Lambda functions** deployed (DataAggregator, IntelligentWarmer, TrafficGenerator)

**Note**: Dashboard works in demo mode without AWS access

## 🚀 Deployment Options

### Option 1: Quick Local Deployment (Recommended for Testing)
```bash
python quick_deploy.py
```

**Use when**:
- Testing the dashboard locally
- No need for external access
- Quick validation of functionality

**Expected result**: Dashboard opens in browser at `http://localhost:8501`

### Option 2: External Access Deployment (Recommended for Examiners)
```bash
python deploy_external.py
```

**Use when**:
- External examiners need remote access
- Demonstrating to multiple people
- Professional presentation setup

**Requirements**:
- [ ] **ngrok installed** (download from https://ngrok.com/download)
- [ ] **ngrok auth token** set in environment or .env file
- [ ] **Stable internet connection**

**Expected result**: 
- Local access: `http://localhost:8501`
- Public access: `https://xxxxx.ngrok.io`

### Option 3: Manual Streamlit Launch
```bash
streamlit run app.py
```

**Use when**:
- Custom configuration needed
- Debugging deployment issues
- Development and testing

## 🌐 External Examiner Setup

### Pre-Examination Preparation

#### 1. Validate Deployment
```bash
python validate_deployment.py
```
Ensure all checks pass before examination.

#### 2. Test Dashboard Functionality
- [ ] **Dashboard loads** within 15 seconds
- [ ] **Live predictions work** (adjust sliders, see results)
- [ ] **System monitoring** shows metrics
- [ ] **Data visualization** displays tables and charts
- [ ] **Traffic generation** can be triggered
- [ ] **All sections accessible** via sidebar navigation

#### 3. Prepare Documentation
Ensure these files are available to examiners:
- [ ] **EXTERNAL_EXAMINER_GUIDE.md** - Primary usage guide
- [ ] **TROUBLESHOOTING.md** - Problem-solving reference
- [ ] **FAQ.md** - Common questions and answers
- [ ] **README.md** - Technical overview

#### 4. Setup Public Access (If Required)
```bash
# Set ngrok token
export NGROK_AUTH_TOKEN=your_token_here

# Start deployment with public URL
python deploy_external.py
```

Share the public URL (format: `https://xxxxx.ngrok.io`) with examiners.

### During Examination

#### 5. Monitor System Health
Keep terminal open to monitor:
- [ ] **Dashboard process** running without errors
- [ ] **ngrok tunnel** stable (if using public access)
- [ ] **AWS services** responding (check System Monitoring section)
- [ ] **Performance** acceptable for all users

#### 6. Provide Support
Be ready to help with:
- [ ] **Browser compatibility** issues (recommend Chrome)
- [ ] **Network connectivity** problems
- [ ] **Feature explanations** and guided tours
- [ ] **Technical questions** about implementation

## 🔧 Troubleshooting During Deployment

### Common Issues and Quick Fixes

#### Dashboard Won't Start
```bash
# Check Python version
python --version

# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Try alternative Python command
python3 -m streamlit run app.py
```

#### Port Already in Use
```bash
# Kill existing Streamlit processes
pkill -f streamlit

# Or use different port
streamlit run app.py --server.port 8502
```

#### ngrok Issues
```bash
# Kill existing ngrok processes
pkill ngrok

# Restart with fresh tunnel
python deploy_external.py
```

#### AWS Connection Problems
```bash
# Test AWS connectivity
python -c "import boto3; print(boto3.Session().region_name)"

# Enable demo mode
export DEMO_MODE=true
python quick_deploy.py
```

### Performance Optimization

#### For Multiple Concurrent Users
- [ ] **Close unnecessary applications** to free memory
- [ ] **Use wired internet connection** if possible
- [ ] **Monitor system resources** (CPU, memory usage)
- [ ] **Consider dedicated machine** for important demonstrations

#### For Slow Networks
- [ ] **Pre-load dashboard** before examination starts
- [ ] **Test all features** to cache resources
- [ ] **Have backup plan** (recorded demo, local screenshots)

## 📊 Examination Day Checklist

### 30 Minutes Before
- [ ] **Run validation script**: `python validate_deployment.py`
- [ ] **Start dashboard**: `python deploy_external.py` (or `quick_deploy.py`)
- [ ] **Test all features** to ensure everything works
- [ ] **Note public URL** if using external access
- [ ] **Prepare documentation** links for examiners

### 15 Minutes Before
- [ ] **Verify dashboard accessibility** from examiner perspective
- [ ] **Check system monitoring** shows healthy status
- [ ] **Test predictions** work with various parameters
- [ ] **Confirm traffic generation** functions properly
- [ ] **Validate data visualization** displays current data

### 5 Minutes Before
- [ ] **Final functionality check** - run through all sections
- [ ] **Monitor system resources** - ensure adequate performance
- [ ] **Have troubleshooting guides** ready for reference
- [ ] **Prepare demonstration scenarios** (high-risk predictions, traffic generation)

### During Examination
- [ ] **Keep terminal visible** to monitor for errors
- [ ] **Watch system performance** and resource usage
- [ ] **Be ready to explain** technical details and design decisions
- [ ] **Guide examiners** through key features and scenarios
- [ ] **Monitor for issues** and provide immediate support

### After Examination
- [ ] **Stop dashboard gracefully** (Ctrl+C in terminal)
- [ ] **Close ngrok tunnel** if used
- [ ] **Save any logs** or error messages for review
- [ ] **Document any issues** encountered for future improvement

## 🎯 Success Criteria

### Technical Functionality
- [ ] **All dashboard sections** load and function correctly
- [ ] **Live predictions** respond within 2-3 seconds
- [ ] **Real-time updates** work automatically (30-second refresh)
- [ ] **Interactive controls** respond immediately to user input
- [ ] **Error handling** displays helpful messages when issues occur

### User Experience
- [ ] **Professional appearance** with consistent styling
- [ ] **Intuitive navigation** via sidebar menu
- [ ] **Clear instructions** and helpful tooltips
- [ ] **Responsive design** works on different screen sizes
- [ ] **Performance** acceptable for demonstration purposes

### External Access (If Used)
- [ ] **Public URL** accessible from external networks
- [ ] **Multiple users** can access simultaneously
- [ ] **Full functionality** maintained over internet connection
- [ ] **Stable connection** throughout examination period
- [ ] **Reasonable performance** despite network latency

## 📞 Emergency Procedures

### If Dashboard Crashes
1. **Check terminal** for error messages
2. **Restart quickly**: `python quick_deploy.py`
3. **Use backup plan**: Screenshots, recorded demo, or local-only access
4. **Explain situation** to examiners and continue with available functionality

### If Network Issues Occur
1. **Switch to local access**: `http://localhost:8501`
2. **Use mobile hotspot** as backup internet
3. **Continue with demo mode** if AWS services unavailable
4. **Focus on architecture** and code review if dashboard unavailable

### If Performance Degrades
1. **Close other applications** to free resources
2. **Restart dashboard** with fresh session
3. **Reduce concurrent users** if necessary
4. **Switch to simpler demonstration** scenarios

## ✅ Final Validation

Before declaring deployment ready:
- [ ] **All checklist items** completed successfully
- [ ] **Validation script** passes without errors
- [ ] **Dashboard tested** by someone other than developer
- [ ] **Documentation reviewed** and accessible
- [ ] **Backup plans** prepared for common failure scenarios
- [ ] **Contact information** available for technical support

---

**🎉 Ready for External Examiner Demonstration!**

This checklist ensures the Cold Start Dashboard is properly deployed and ready to showcase the intelligent cold start prevention system to external examiners. Follow each step carefully to provide a smooth and professional demonstration experience.