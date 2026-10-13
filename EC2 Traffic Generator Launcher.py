import boto3
import os
import json
from botocore.exceptions import ClientError

# --- CONFIGURATION ---
AWS_REGION = 'ap-south-1'
EC2_KEY_PAIR_NAME = 'cold'  # Confirmed KeyPair
TRAFFIC_GENERATOR_SCRIPT_PATH = 'traffic_generator.py'

# --- FINAL DEPLOYMENT VALUES ---
LIVE_API_URL = "https://mi90qzwvz5.execute-api.ap-south-1.amazonaws.com/prod"
LIVE_BUCKET_NAME = "clod-start-demo-yourname-unique"
LIVE_EC2_ROLE_ARN = "arn:aws:iam::559284420137:role/EC2-CLOD-START-Role"
LIVE_SECURITY_GROUP_ID = "sg-0d3d451c75c98a7b4"  # Confirmed SG ID

ec2_client = boto3.client('ec2', region_name=AWS_REGION)
ec2_resource = boto3.resource('ec2', region_name=AWS_REGION)
iam_client = boto3.client('iam', region_name=AWS_REGION)


def get_latest_ami_id():
    """Finds the latest Ubuntu Server 20.04 LTS AMI in the region."""
    try:
        response = ec2_client.describe_images(
            Owners=['099720109477'],  # Canonical owner ID for Ubuntu
            Filters=[
                {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*']},
                {'Name': 'state', 'Values': ['available']},
                {'Name': 'architecture', 'Values': ['x86_64']},
            ]
        )
        images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
        return images[0]['ImageId'] if images else None
    except Exception as e:
        print(f"❌ Error finding AMI: {e}")
        return None

def launch_and_start_traffic_generator(api_url, bucket_name, role_arn, security_group_id):
    """
    Launches an EC2 instance, configures it with User Data, and starts traffic generation.
    """
    ami_id = get_latest_ami_id()
    if not ami_id:
        print("❌ Could not find a suitable AMI for EC2 launch.")
        return None

    # 1. Prepare the User Data script (Shell Script executed on EC2 launch)
    try:
        # Read the traffic generator content
        with open(TRAFFIC_GENERATOR_SCRIPT_PATH, 'r', encoding='utf-8') as f:
            python_script_content = f.read() 
    except FileNotFoundError:
        print(f"❌ Error: {TRAFFIC_GENERATOR_SCRIPT_PATH} not found. Ensure it is in the same directory.")
        return None

    # Replace the placeholder values in the Python script dynamically
    python_script_content = python_script_content.replace(
        'API_URL = "https://cuc9ef69c5.execute-api.ap-south-1.amazonaws.com/prod"',
        f'API_URL = "{api_url}"'
    ).replace(
        'BUCKET_NAME_INIT = "clod-start-demo-yourname-unique"',
        f'BUCKET_NAME_INIT = "{bucket_name}"'
    )

    user_data_script = f"""#!/bin/bash
echo "Starting automated EC2 setup..." > /tmp/setup.log

# 1. Install necessary software
sudo apt update -y >> /tmp/setup.log 2>&1
sudo apt install python3 python3-pip -y >> /tmp/setup.log 2>&1
pip install requests boto3 >> /tmp/setup.log 2>&1

# 2. Create the traffic_generator.py file in /home/ubuntu
cat << EOF > /home/ubuntu/traffic_generator.py
{python_script_content}
EOF
chown ubuntu:ubuntu /home/ubuntu/traffic_generator.py

# 3. Execute the script in the background using nohup for continuous running
echo "Starting traffic generator in background..." >> /tmp/setup.log
sudo -u ubuntu nohup python3 /home/ubuntu/traffic_generator.py 240 > /home/ubuntu/traffic_generator.log 2>&1 &
echo "Traffic generator script started. Check /home/ubuntu/traffic_generator.log for status." >> /tmp/setup.log
"""

    # 2. Launch the EC2 Instance
    print(f"Attempting to launch t2.micro instance with AMI: {ami_id}")

    # Use a default subnet in the region 
    subnets_response = ec2_client.describe_subnets(Filters=[{'Name': 'default-for-az', 'Values': ['true']}])
    subnet_id = subnets_response['Subnets'][0]['SubnetId'] if subnets_response['Subnets'] else None

    if not subnet_id:
        print("❌ Could not find a default subnet. EC2 launch failed.")
        return None

    try:
        # Convert the Role ARN to the Instance Profile ARN format
        instance_profile_arn = role_arn.replace(':role/', ':instance-profile/')

        instance_response = ec2_resource.create_instances(
            ImageId=ami_id,
            MinCount=1,
            MaxCount=1,
            InstanceType='t2.micro',
            KeyName=EC2_KEY_PAIR_NAME,
            UserData=user_data_script,
            SecurityGroupIds=[security_group_id],
            SubnetId=subnet_id,
            IamInstanceProfile={
                'Arn': instance_profile_arn
            },
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Name', 'Value': 'CLOD-START-Traffic-Generator-Manual'},
                        {'Key': 'Project', 'Value': 'CLOD-START'}
                    ]
                }
            ]
        )
        instance_id = instance_response[0].id
        print(f"✅ EC2 Traffic Generator launched: {instance_id}")
        return instance_id

    except ClientError as e:
        print(f"❌ EC2 launch failed: {e}")
        return None


if __name__ == '__main__':
    print("--- 🚀 Standalone EC2 Traffic Launcher ---")

    # --- VERIFY CONFIGURATION BEFORE RUNNING ---
    if any(placeholder in LIVE_EC2_ROLE_ARN for placeholder in ['example', 'changeme']) or \
       LIVE_SECURITY_GROUP_ID in ['sg-xxxxxxxxxxxxxxxx', 'sg-changeme']:
        print("\n🚨 CRITICAL ERROR: Please update the LIVE_* variables in the script first.")
        exit()

    # --- Execute the isolated launch ---
    instance_id = launch_and_start_traffic_generator(
        api_url=LIVE_API_URL,
        bucket_name=LIVE_BUCKET_NAME,
        role_arn=LIVE_EC2_ROLE_ARN,
        security_group_id=LIVE_SECURITY_GROUP_ID
    )

    if instance_id:
        print(f"\nDeployment initiated for instance ID: {instance_id}")
        print("The EC2 script will now run automatically to collect data. Check the S3 bucket!")
    else:
        print("\nEC2 launch failed. Check KeyPair name and IAM permissions.")
