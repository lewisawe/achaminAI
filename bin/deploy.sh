#!/bin/bash

echo "===== Deploying Achamin - Cultural Understanding Through AI ====="
echo ""

# Check for AWS CLI
if ! command -v aws &> /dev/null; then
    echo "AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check for AWS credentials with your-aws-profile profile
aws --profile your-aws-profile sts get-caller-identity &> /dev/null
if [ $? -ne 0 ]; then
    echo "AWS credentials not configured for your-aws-profile profile. Please run 'aws configure --profile your-aws-profile' first."
    exit 1
fi

echo "Creating S3 buckets..."
aws --profile your-aws-profile s3 mb s3://your-achamin-uploads-bucket --region us-east-1
aws --profile your-aws-profile s3 mb s3://your-achamin-generated-content-bucket --region us-east-1

echo "Setting bucket CORS policies..."
aws --profile your-aws-profile s3api put-bucket-cors --bucket your-achamin-uploads-bucket --cors-configuration file://../policies/cors-policy.json
aws --profile your-aws-profile s3api put-bucket-cors --bucket your-achamin-generated-content-bucket --cors-configuration file://../policies/cors-policy.json

echo "Deploying Lambda function..."
cd ../lambdas
./deployLambdaFunction

echo "Deploying API Gateway..."
cd ../apiGateway
./deployAPIGateway

echo "Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Update the API endpoint URL in index.html"
echo "2. Open index.html in your browser to start using Achamin"
echo ""
