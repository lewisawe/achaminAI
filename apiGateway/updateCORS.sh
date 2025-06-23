#!/usr/bin/env bash

# Script to update existing API Gateway with CORS settings
# Usage: ./updateCORS.sh <API_ID>

if [ $# -eq 0 ]; then
    echo "Usage: $0 <API_ID>"
    echo "You can find your API ID in the AWS Console or by running:"
    echo "aws --profile your-aws-profile apigateway get-rest-apis --query 'items[?name==\`CulturalHarmonyAPI\`].id' --output text"
    exit 1
fi

API_ID=$1

echo "Updating API Gateway $API_ID with CORS settings..."

# Get the resource ID for the /analyze endpoint
RESOURCE_ID=$(aws --profile your-aws-profile apigateway get-resources --rest-api-id $API_ID --query "items[?pathPart=='analyze'].id" --output text)

if [ -z "$RESOURCE_ID" ]; then
    echo "Error: Could not find /analyze resource. Please check your API Gateway configuration."
    exit 1
fi

echo "Found resource ID: $RESOURCE_ID"

# Create OPTIONS method for CORS
echo "Creating OPTIONS method..."
aws --profile your-aws-profile apigateway put-method --rest-api-id $API_ID --resource-id $RESOURCE_ID --http-method OPTIONS --authorization-type NONE

# Set up MOCK integration for OPTIONS method
echo "Setting up MOCK integration for OPTIONS..."
aws --profile your-aws-profile apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method OPTIONS \
  --type MOCK \
  --request-templates '{"application/json":"{\"statusCode\": 200}"}'

# Set up method response for OPTIONS
echo "Setting up method response for OPTIONS..."
aws --profile your-aws-profile apigateway put-method-response \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{
    "method.response.header.Access-Control-Allow-Headers": true,
    "method.response.header.Access-Control-Allow-Methods": true,
    "method.response.header.Access-Control-Allow-Origin": true
  }'

# Set up integration response for OPTIONS
echo "Setting up integration response for OPTIONS..."
aws --profile your-aws-profile apigateway put-integration-response \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method OPTIONS \
  --status-code 200 \
  --response-parameters '{
    "method.response.header.Access-Control-Allow-Headers": "'\''Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'\''",
    "method.response.header.Access-Control-Allow-Methods": "'\''GET,POST,PUT,DELETE,OPTIONS'\''",
    "method.response.header.Access-Control-Allow-Origin": "'\''*'\''"
  }'

# Deploy the API
echo "Deploying API..."
aws --profile your-aws-profile apigateway create-deployment --rest-api-id $API_ID --stage-name prod

echo "CORS configuration completed successfully!"
echo "Your API should now handle CORS requests properly." 