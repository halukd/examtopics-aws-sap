import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import boto3
from botocore.exceptions import ClientError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
# Enable CORS for the frontend to access this backend
# In a production environment, you would restrict this to your frontend's domain.
CORS(app)

# --- AWS Configuration ---
# Boto3 will automatically look for credentials in the following order:
# 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
# 2. Shared credential file (~/.aws/credentials)
# 3. AWS config file (~/.aws/config)
# 4. IAM role for Amazon EC2 instance (if running on EC2)
# 5. ECS Task Role (if running on ECS)
# For local development, setting environment variables or using ~/.aws/credentials is common.
# Example (for development only, not for production):
# export AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY"
# export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_KEY"
# export AWS_DEFAULT_REGION="us-east-1" # Or any preferred default region

# --- Helper function to get all AWS regions ---
def get_aws_regions():
    """Fetches all available AWS regions."""
    try:
        # Use a default region to list all regions. us-east-1 is generally a good choice.
        ec2_client = boto3.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_regions()
        regions = [region['RegionName'] for region in response['Regions']]
        logging.info(f"Discovered AWS regions: {regions}")
        return regions
    except ClientError as e:
        logging.error(f"Error fetching AWS regions: {e}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching regions: {e}")
        return []

# --- Resource Discovery Functions ---

def discover_ec2_instances(client):
    """Discovers EC2 instances in a given region."""
    instances = []
    try:
        paginator = client.get_paginator('describe_instances')
        for page in paginator.paginate():
            for reservation in page['Reservations']:
                for instance in reservation['Instances']:
                    instance_id = instance.get('InstanceId')
                    instance_type = instance.get('InstanceType')
                    state = instance['State']['Name']
                    # Extract Name tag, default to 'N/A' if not found
                    name_tag = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), 'N/A')
                    instances.append({
                        'id': instance_id,
                        'name': name_tag,
                        'type': instance_type,
                        'state': state
                    })
        logging.info(f"Discovered {len(instances)} EC2 instances in {client.meta.region_name}.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'UnauthorizedOperation':
            logging.warning(f"Permission denied for EC2 in region {client.meta.region_name}. Skipping.")
        else:
            logging.error(f"Error discovering EC2 instances in region {client.meta.region_name}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during EC2 discovery in {client.meta.region_name}: {e}")
    return instances

def discover_s3_buckets(client):
    """
    Discovers S3 buckets. Note: S3 buckets are global, but the API call to list them
    is typically made against a specific region (e.g., us-east-1).
    To get the actual region of a bucket, a separate API call is needed.
    """
    buckets = []
    try:
        response = client.list_buckets()
        for bucket in response['Buckets']:
            bucket_name = bucket['Name']
            bucket_region = 'N/A' # Default
            public_access = 'Unknown' # Default

            # Get bucket location
            try:
                location_response = client.get_bucket_location(Bucket=bucket_name)
                # 'LocationConstraint' can be None for us-east-1, so default to it
                bucket_region = location_response.get('LocationConstraint') or 'us-east-1'
            except ClientError as e:
                logging.warning(f"Could not get location for bucket {bucket_name}: {e}. Defaulting to N/A.")

            # Check public access block configuration
            try:
                block_public_access = client.get_public_access_block(Bucket=bucket_name)
                config = block_public_access['PublicAccessBlockConfiguration']
                if config.get('BlockPublicAcls', False) and config.get('BlockPublicPolicy', False) and \
                   config.get('IgnorePublicAcls', False) and config.get('RestrictPublicBuckets', False):
                    public_access = 'Private (All Public Access Blocked)'
                else:
                    public_access = 'Potentially Public (Public Access Not Fully Blocked)'
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchPublicAccessBlockConfiguration':
                    public_access = 'Potentially Public (No Public Access Block Configured)'
                else:
                    logging.warning(f"Error checking public access for {bucket_name}: {e}")
            except Exception as e:
                logging.error(f"An unexpected error occurred while checking S3 public access for {bucket_name}: {e}")


            buckets.append({
                'name': bucket_name,
                'region': bucket_region,
                'type': public_access,
                'objects': 'N/A' # Counting objects requires list_objects_v2, which can be slow for many objects
            })
        logging.info(f"Discovered {len(buckets)} S3 buckets.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'UnauthorizedOperation':
            logging.warning(f"Permission denied for S3. Skipping S3 discovery.")
        else:
            logging.error(f"Error discovering S3 buckets: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during S3 discovery: {e}")
    return buckets

def discover_lambda_functions(client):
    """Discovers Lambda functions in a given region."""
    functions = []
    try:
        paginator = client.get_paginator('list_functions')
        for page in paginator.paginate():
            for func in page['Functions']:
                functions.append({
                    'name': func.get('FunctionName'),
                    'runtime': func.get('Runtime'),
                    'memory': func.get('MemorySize'),
                    'arn': func.get('FunctionArn')
                })
        logging.info(f"Discovered {len(functions)} Lambda functions in {client.meta.region_name}.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'UnauthorizedOperation':
            logging.warning(f"Permission denied for Lambda in region {client.meta.region_name}. Skipping.")
        else:
            logging.error(f"Error discovering Lambda functions in region {client.meta.region_name}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during Lambda discovery in {client.meta.region_name}: {e}")
    return functions

def discover_rds_instances(client):
    """Discovers RDS instances in a given region."""
    databases = []
    try:
        paginator = client.get_paginator('describe_db_instances')
        for page in paginator.paginate():
            for db_instance in page['DBInstances']:
                databases.append({
                    'id': db_instance.get('DBInstanceIdentifier'),
                    'engine': db_instance.get('Engine'),
                    'instanceClass': db_instance.get('DBInstanceClass'),
                    'status': db_instance.get('DBInstanceStatus'),
                    'endpoint': db_instance.get('Endpoint', {}).get('Address', 'N/A')
                })
        logging.info(f"Discovered {len(databases)} RDS instances in {client.meta.region_name}.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'UnauthorizedOperation':
            logging.warning(f"Permission denied for RDS in region {client.meta.region_name}. Skipping.")
        else:
            logging.error(f"Error discovering RDS instances in region {client.meta.region_name}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during RDS discovery in {client.meta.region_name}: {e}")
    return databases

def discover_vpcs(client):
    """Discovers VPCs in a given region."""
    vpcs = []
    try:
        response = client.describe_vpcs()
        for vpc in response['Vpcs']:
            name_tag = next((tag['Value'] for tag in vpc.get('Tags', []) if tag['Key'] == 'Name'), 'N/A')
            vpcs.append({
                'id': vpc.get('VpcId'),
                'name': name_tag,
                'cidr': vpc.get('CidrBlock'),
                'isDefault': vpc.get('IsDefault')
            })
        logging.info(f"Discovered {len(vpcs)} VPCs in {client.meta.region_name}.")
    except ClientError as e:
        if e.response['Error']['Code'] == 'UnauthorizedOperation':
            logging.warning(f"Permission denied for VPCs in region {client.meta.region_name}. Skipping.")
        else:
            logging.error(f"Error discovering VPCs in region {client.meta.region_name}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during VPC discovery in {client.meta.region_name}: {e}")
    return vpcs

# --- Main API Endpoint ---
@app.route('/discover-aws', methods=['GET'])
def discover_aws_resources():
    """
    API endpoint to discover AWS resources.
    The AWS Account ID from the frontend is for logging/display.
    Boto3 uses the credentials configured in the backend's environment or IAM role.
    """
    aws_account_id = request.args.get('accountId', 'N/A')
    logging.info(f"Received discovery request for AWS Account ID: {aws_account_id}")

    discovered_data = {}
    regions = get_aws_regions()

    if not regions:
        return jsonify({"error": "Could not retrieve AWS regions. Check AWS credentials and network connectivity."}), 500

    for region in regions:
        region_data = {}
        logging.info(f"Starting discovery in region: {region}")
        try:
            # Initialize clients for each service in the current region
            ec2_client = boto3.client('ec2', region_name=region)
            s3_client = boto3.client('s3', region_name=region)
            lambda_client = boto3.client('lambda', region_name=region)
            rds_client = boto3.client('rds', region_name=region)
            # VPC client is also EC2 client
            vpc_client = ec2_client

            # Discover resources for each service
            ec2_resources = discover_ec2_instances(ec2_client)
            if ec2_resources:
                region_data['EC2'] = ec2_resources

            # S3 buckets are listed globally, but the API call is regional.
            # We call it once from a specific region (e.g., us-east-1) to avoid duplicate listings.
            # For this demo, we'll ensure S3 is only called once from us-east-1 to avoid redundancy.
            if region == 'us-east-1': # Or any other single region you prefer for S3 listing
                s3_resources = discover_s3_buckets(s3_client)
                if s3_resources:
                    region_data['S3'] = s3_resources
            else:
                # For other regions, we don't re-list S3 buckets
                pass

            lambda_resources = discover_lambda_functions(lambda_client)
            if lambda_resources:
                region_data['Lambda'] = lambda_resources

            rds_resources = discover_rds_instances(rds_client)
            if rds_resources:
                region_data['RDS'] = rds_resources

            vpc_resources = discover_vpcs(vpc_client)
            if vpc_resources:
                region_data['VPC'] = vpc_resources

            if region_data: # Only add region to final data if it has discovered resources
                discovered_data[region] = region_data

        except Exception as e:
            logging.error(f"An unexpected error occurred during discovery in region {region}: {e}")
            # Continue to next region even if one fails
            # In a production app, you might want more sophisticated error reporting

    logging.info(f"Discovery complete for account {aws_account_id}.")
    return jsonify(discovered_data)

# --- Run the Flask app ---
if __name__ == '__main__':
    # Run the Flask app on localhost port 5000
    # debug=True allows for automatic reloading on code changes and provides a debugger
    # host='127.0.0.1' ensures it's only accessible from your local machine
    app.run(debug=True, host='127.0.0.1', port=5000)
