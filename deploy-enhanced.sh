#!/bin/bash

# Enhanced Achamin Deployment Script
# This script deploys the complete enhanced cultural analysis system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="achamin-enhanced"
AWS_REGION="${AWS_REGION:-us-west-2}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Load environment variables
if [ -f ".env.production" ]; then
    echo -e "${BLUE}Loading environment variables...${NC}"
    source .env.production
else
    echo -e "${RED}Error: .env.production file not found. Please create it from production.env.example${NC}"
    exit 1
fi

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check AWS CLI
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS CLI is not configured. Please run 'aws configure' first."
        exit 1
    fi
}

# Function to create S3 buckets
create_s3_buckets() {
    print_status "Creating S3 buckets..."
    
    # Create upload bucket
    if aws s3api head-bucket --bucket "$UPLOAD_BUCKET" 2>/dev/null; then
        print_warning "Upload bucket $UPLOAD_BUCKET already exists"
    else
        aws s3api create-bucket \
            --bucket "$UPLOAD_BUCKET" \
            --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION"
        print_status "Created upload bucket: $UPLOAD_BUCKET"
    fi
    
    # Create generated content bucket
    if aws s3api head-bucket --bucket "$GENERATED_CONTENT_BUCKET" 2>/dev/null; then
        print_warning "Generated content bucket $GENERATED_CONTENT_BUCKET already exists"
    else
        aws s3api create-bucket \
            --bucket "$GENERATED_CONTENT_BUCKET" \
            --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION"
        print_status "Created generated content bucket: $GENERATED_CONTENT_BUCKET"
    fi
    
    # Create music bucket
    if aws s3api head-bucket --bucket "$MUSIC_BUCKET" 2>/dev/null; then
        print_warning "Music bucket $MUSIC_BUCKET already exists"
    else
        aws s3api create-bucket \
            --bucket "$MUSIC_BUCKET" \
            --region "$AWS_REGION" \
            --create-bucket-configuration LocationConstraint="$AWS_REGION"
        print_status "Created music bucket: $MUSIC_BUCKET"
    fi
}

# Function to configure S3 bucket policies
configure_bucket_policies() {
    print_status "Configuring S3 bucket policies..."
    
    # Upload bucket policy
    cat > /tmp/upload-bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowLambdaUploads",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/achamin-lambda-role"
            },
            "Action": [
                "s3:PutObject",
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::$UPLOAD_BUCKET/*"
        }
    ]
}
EOF
    
    aws s3api put-bucket-policy --bucket "$UPLOAD_BUCKET" --policy file:///tmp/upload-bucket-policy.json
    
    # Generated content bucket policy
    cat > /tmp/generated-content-bucket-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowLambdaAccess",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/achamin-lambda-role"
            },
            "Action": [
                "s3:PutObject",
                "s3:GetObject"
            ],
            "Resource": "arn:aws:s3:::$GENERATED_CONTENT_BUCKET/*"
        }
    ]
}
EOF
    
    aws s3api put-bucket-policy --bucket "$GENERATED_CONTENT_BUCKET" --policy file:///tmp/generated-content-bucket-policy.json
    
    # Configure CORS for the generated content bucket
    print_status "Configuring CORS for the generated content bucket..."
    cat > /tmp/cors-config.json << EOF
{
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["GET", "HEAD"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": ["ETag", "Content-Length", "Content-Type"],
            "MaxAgeSeconds": 3600
        }
    ]
}
EOF
    
    aws s3api put-bucket-cors --bucket "$GENERATED_CONTENT_BUCKET" --cors-configuration file:///tmp/cors-config.json
    
    # Clean up temporary files
    rm -f /tmp/upload-bucket-policy.json /tmp/generated-content-bucket-policy.json /tmp/cors-config.json
}

# Function to create DynamoDB table
create_dynamodb_table() {
    print_status "Creating DynamoDB table..."
    
    if aws dynamodb describe-table --table-name "$METADATA_TABLE" 2>/dev/null; then
        print_warning "DynamoDB table $METADATA_TABLE already exists"
    else
        # Create a temporary JSON file for the table definition
        cat > /tmp/dynamodb-table-definition.json << EOF
{
  "TableName": "$METADATA_TABLE",
  "AttributeDefinitions": [
    {
      "AttributeName": "request_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "timestamp",
      "AttributeType": "N"
    },
    {
      "AttributeName": "mood",
      "AttributeType": "S"
    },
    {
      "AttributeName": "themes",
      "AttributeType": "S"
    }
  ],
  "KeySchema": [
    {
      "AttributeName": "request_id",
      "KeyType": "HASH"
    }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "timestamp-index",
      "KeySchema": [
        {
          "AttributeName": "timestamp",
          "KeyType": "HASH"
        }
      ],
      "Projection": {
        "ProjectionType": "ALL"
      },
      "ProvisionedThroughput": {
        "ReadCapacityUnits": 5,
        "WriteCapacityUnits": 5
      }
    },
    {
      "IndexName": "mood-themes-index",
      "KeySchema": [
        {
          "AttributeName": "mood",
          "KeyType": "HASH"
        },
        {
          "AttributeName": "themes",
          "KeyType": "RANGE"
        }
      ],
      "Projection": {
        "ProjectionType": "ALL"
      },
      "ProvisionedThroughput": {
        "ReadCapacityUnits": 5,
        "WriteCapacityUnits": 5
      }
    }
  ],
  "ProvisionedThroughput": {
    "ReadCapacityUnits": 10,
    "WriteCapacityUnits": 10
  },
  "StreamSpecification": {
    "StreamEnabled": true,
    "StreamViewType": "NEW_AND_OLD_IMAGES"
  }
}
EOF

        # Create the table using the JSON file
        aws dynamodb create-table --cli-input-json file:///tmp/dynamodb-table-definition.json --region "$AWS_REGION"
        
        print_status "Created DynamoDB table: $METADATA_TABLE"
        
        # Wait for table to be active
        print_status "Waiting for DynamoDB table to be active..."
        aws dynamodb wait table-exists --table-name "$METADATA_TABLE"
        
        # Clean up temporary file
        rm -f /tmp/dynamodb-table-definition.json
    fi
}

# Function to create IAM roles
create_iam_roles() {
    print_status "Creating IAM roles..."
    
    # Create Lambda execution role
    if aws iam get-role --role-name achamin-lambda-role 2>/dev/null; then
        print_warning "IAM role achamin-lambda-role already exists"
    else
        # Create trust policy
        cat > /tmp/trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF
        
        aws iam create-role \
            --role-name achamin-lambda-role \
            --assume-role-policy-document file:///tmp/trust-policy.json
        
        # Attach policies
        aws iam attach-role-policy \
            --role-name achamin-lambda-role \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
        
        aws iam attach-role-policy \
            --role-name achamin-lambda-role \
            --policy-arn arn:aws:iam::aws:policy/AmazonRekognitionFullAccess
        
        aws iam attach-role-policy \
            --role-name achamin-lambda-role \
            --policy-arn arn:aws:iam::aws:policy/AmazonPollyFullAccess
        
        aws iam attach-role-policy \
            --role-name achamin-lambda-role \
            --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
        
        aws iam attach-role-policy \
            --role-name achamin-lambda-role \
            --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess
        
        aws iam attach-role-policy \
            --role-name achamin-lambda-role \
            --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
        
        aws iam attach-role-policy \
            --role-name achamin-lambda-role \
            --policy-arn arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess
        
        print_status "Created IAM role: achamin-lambda-role"
        
        # Wait for role to be available
        sleep 10
    fi
    
    # Clean up temporary files
    rm -f /tmp/trust-policy.json
}

# Function to create Lambda function
create_lambda_function() {
    print_status "Creating enhanced Lambda function..."
    
    # Create deployment package
    cd "$SCRIPT_DIR/lambdas"
    
    # Install dependencies
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install boto3 requests
    
    # Create deployment package
    mkdir -p package
    cp enhanced_achamin_lambda.py package/
    pip install -r <(pip freeze) -t package/ --no-deps
    
    cd package
    zip -r ../enhanced-lambda.zip .
    cd ..
    
    # Deploy Lambda function
    if aws lambda get-function --function-name "$LAMBDA_FUNCTION_NAME" 2>/dev/null; then
        print_warning "Lambda function $LAMBDA_FUNCTION_NAME already exists, updating..."
        aws lambda update-function-code \
            --function-name "$LAMBDA_FUNCTION_NAME" \
            --zip-file fileb://enhanced-lambda.zip
    else
        aws lambda create-function \
            --function-name "$LAMBDA_FUNCTION_NAME" \
            --runtime python3.9 \
            --role "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/achamin-lambda-role" \
            --handler enhanced_achamin_lambda.lambda_handler \
            --zip-file fileb://enhanced-lambda.zip \
            --timeout 300 \
            --memory-size 1024 \
            --environment Variables="{
                UPLOAD_BUCKET=$UPLOAD_BUCKET,
                GENERATED_CONTENT_BUCKET=$GENERATED_CONTENT_BUCKET,
                MUSIC_BUCKET=$MUSIC_BUCKET,
                METADATA_TABLE=$METADATA_TABLE,
                ACHAMIN_REGION=$AWS_REGION
            }"
        
        print_status "Created Lambda function: $LAMBDA_FUNCTION_NAME"
    fi
    
    # Clean up
    rm -rf package enhanced-lambda.zip
    deactivate
    cd "$SCRIPT_DIR"
}

# Function to create API Gateway
create_api_gateway() {
    print_status "Creating API Gateway..."
    
    # Check if API Gateway already exists
    if aws apigateway get-rest-api --rest-api-id "$API_GATEWAY_NAME" 2>/dev/null; then
        print_warning "API Gateway $API_GATEWAY_NAME already exists"
        return
    fi
    
    # Create REST API
    API_ID=$(aws apigateway create-rest-api \
        --name "$API_GATEWAY_NAME" \
        --description "Enhanced Achamin Cultural Analysis API" \
        --query 'id' --output text)
    
    # Get root resource ID
    ROOT_ID=$(aws apigateway get-resources \
        --rest-api-id "$API_ID" \
        --query 'items[?path==`/`].id' --output text)
    
    # Create resource
    RESOURCE_ID=$(aws apigateway create-resource \
        --rest-api-id "$API_ID" \
        --parent-id "$ROOT_ID" \
        --path-part "analyze" \
        --query 'id' --output text)
    
    # Create POST method
    aws apigateway put-method \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method POST \
        --authorization-type NONE
    
    # Create integration
    aws apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method POST \
        --type AWS_PROXY \
        --integration-http-method POST \
        --uri "arn:aws:apigateway:$AWS_REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):function:$LAMBDA_FUNCTION_NAME/invocations"
    
    # Add Lambda permission
    print_status "Adding Lambda permission for API Gateway..."
    # Generate a unique statement ID using timestamp
    STATEMENT_ID="apigateway-access-$(date +%s)"
    
    # Add permission (this will fail if permission already exists, but we'll continue)
    aws lambda add-permission \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --statement-id "$STATEMENT_ID" \
        --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):$API_ID/*/*" || \
        print_warning "Lambda permission already exists or could not be added"
    
    # Add OPTIONS method for CORS
    aws apigateway put-method \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method OPTIONS \
        --authorization-type NONE
    
    # Add method response for OPTIONS first
    aws apigateway put-method-response \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method OPTIONS \
        --status-code 200 \
        --response-parameters '{
            "method.response.header.Access-Control-Allow-Headers": true,
            "method.response.header.Access-Control-Allow-Methods": true,
            "method.response.header.Access-Control-Allow-Origin": true
        }'
    
    # Add mock integration for OPTIONS
    aws apigateway put-integration \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method OPTIONS \
        --type MOCK \
        --request-templates '{"application/json": "{\"statusCode\": 200}"}'
    
    # Add integration response for OPTIONS
    aws apigateway put-integration-response \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method OPTIONS \
        --status-code 200 \
        --response-parameters '{
            "method.response.header.Access-Control-Allow-Headers": "'"'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"'",
            "method.response.header.Access-Control-Allow-Methods": "'"'GET,POST,PUT,DELETE,OPTIONS'"'",
            "method.response.header.Access-Control-Allow-Origin": "'"'*'"'"
        }'
    
    # Add method response for POST
    aws apigateway put-method-response \
        --rest-api-id "$API_ID" \
        --resource-id "$RESOURCE_ID" \
        --http-method POST \
        --status-code 200 \
        --response-parameters '{
            "method.response.header.Access-Control-Allow-Origin": true
        }'
    
    # Deploy API
    aws apigateway create-deployment \
        --rest-api-id "$API_ID" \
        --stage-name "prod"
    
    # Get the API URL
    API_URL="https://$API_ID.execute-api.$AWS_REGION.amazonaws.com/prod/analyze"
    
    print_status "Created API Gateway: $API_GATEWAY_NAME"
    print_status "API URL: $API_URL"
    
    # Update the API URL in the enhanced-index.html file
    print_status "Updating API URL in enhanced-index.html..."
    sed -i "s|this.apiUrl = '.*';|this.apiUrl = '$API_URL';|" "$SCRIPT_DIR/enhanced-index.html"
}

# Function to create Step Functions workflow
create_step_functions() {
    print_status "Creating Step Functions workflow..."
    
    # Replace placeholders in workflow definition
    sed "s/\${AWS_REGION}/$AWS_REGION/g; s/\${AWS_ACCOUNT_ID}/$(aws sts get-caller-identity --query Account --output text)/g" \
        "$SCRIPT_DIR/step-functions/enhanced-pipeline-definition.json" > /tmp/workflow-definition.json
    
    # Create state machine
    if aws stepfunctions describe-state-machine --state-machine-arn "arn:aws:states:$AWS_REGION:$(aws sts get-caller-identity --query Account --output text):stateMachine:achamin-enhanced-pipeline" 2>/dev/null; then
        print_warning "Step Functions workflow already exists"
    else
        aws stepfunctions create-state-machine \
            --name "achamin-enhanced-pipeline" \
            --definition file:///tmp/workflow-definition.json \
            --role-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/achamin-lambda-role"
        
        print_status "Created Step Functions workflow: achamin-enhanced-pipeline"
    fi
    
    # Clean up
    rm -f /tmp/workflow-definition.json
}

# Function to upload sample background music
upload_sample_music() {
    print_status "Uploading sample background music..."
    
    # Create sample music files (empty files for demo)
    mkdir -p /tmp/sample_music
    
    # Create sample music files
    for style in ambient_world ethereal_ambient traditional_folk epic_orchestral warm_acoustic; do
        for i in {1..3}; do
            echo "Sample $style music $i" > "/tmp/sample_music/${style}_${i}.mp3"
        done
    done
    
    # Upload to S3
    aws s3 sync /tmp/sample_music/ "s3://$MUSIC_BUCKET/background_music/" --delete
    
    # Clean up
    rm -rf /tmp/sample_music
    
    print_status "Uploaded sample background music to S3"
}

# Function to update environment file
update_environment_file() {
    print_status "Updating environment configuration..."
    
    # Get API Gateway URL
    API_ID=$(aws apigateway get-rest-apis --query "items[?name=='$API_GATEWAY_NAME'].id" --output text)
    API_URL="https://$API_ID.execute-api.$AWS_REGION.amazonaws.com/prod/analyze"
    
    # Update .env.production
    sed -i "s|ACHAMIN_API_URL=.*|ACHAMIN_API_URL=$API_URL|" .env.production
    sed -i "s|MUSIC_BUCKET=.*|MUSIC_BUCKET=$MUSIC_BUCKET|" .env.production
    sed -i "s|METADATA_TABLE=.*|METADATA_TABLE=$METADATA_TABLE|" .env.production
    
    # Update enhanced-production.env
    sed -i "s|ACHAMIN_API_URL=.*|ACHAMIN_API_URL=$API_URL|" enhanced-production.env
    
    print_status "Updated environment configuration"
}

# Function to run health check
run_health_check() {
    print_status "Running health check..."
    
    if [ -f "health-check.js" ]; then
        node health-check.js
    else
        print_warning "Health check script not found"
    fi
}

# Main deployment function
main() {
    print_status "Starting enhanced Achamin deployment..."
    
    # Check prerequisites
    check_aws_cli
    
    # Create infrastructure
    create_s3_buckets
    create_dynamodb_table
    create_iam_roles
    configure_bucket_policies
    create_lambda_function
    create_api_gateway
    create_step_functions
    upload_sample_music
    
    # Update configuration
    update_environment_file
    
    # Health check
    run_health_check
    
    print_status "Enhanced Achamin deployment completed successfully!"
    print_status "Frontend URL: file://$(pwd)/enhanced-index.html"
    print_status "API URL: $ACHAMIN_API_URL"
}

# Run main function
main "$@" 