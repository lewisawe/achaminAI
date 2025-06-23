import json
import boto3
import base64
import os
import logging
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS clients
lambda_client = boto3.client('lambda', region_name='us-west-2')

# Get configuration from environment variables
TARGET_LAMBDA = os.environ.get('TARGET_LAMBDA', 'achamin-enhanced-simi-ops')

def lambda_handler(event, context):
    """
    CORS Proxy Lambda handler
    This function forwards requests to the target Lambda and ensures CORS headers are added to all responses
    """
    
    # Define CORS headers
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Content-Type': 'application/json'
    }
    
    # Handle preflight OPTIONS request
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': ''
        }
    
    try:
        # Log the incoming event for debugging
        logger.info(f"Received event: {json.dumps(event)}")
        
        # Forward the request to the target Lambda
        response = lambda_client.invoke(
            FunctionName=TARGET_LAMBDA,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        
        # Check if the invocation was successful
        if response.get('StatusCode') != 200:
            logger.error(f"Lambda invocation failed with status: {response.get('StatusCode')}")
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Lambda invocation failed'})
            }
        
        # Parse the response from the target Lambda
        response_payload_bytes = response['Payload'].read()
        response_payload_str = response_payload_bytes.decode('utf-8')
        
        logger.info(f"Target Lambda response: {response_payload_str}")
        
        try:
            response_payload = json.loads(response_payload_str)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse Lambda response as JSON: {response_payload_str}")
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Invalid response from Lambda'})
            }
        
        # Handle case where Lambda returns an error
        if 'FunctionError' in response:
            logger.error(f"Lambda function error: {response.get('FunctionError')}")
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Lambda function error', 'details': response_payload})
            }
        
        # Get the status code and body from the response
        status_code = response_payload.get('statusCode', 200)
        body = response_payload.get('body', '')
        
        # Get any headers from the response
        headers = response_payload.get('headers', {})
        
        # Add CORS headers to the response
        headers.update(cors_headers)
        
        # Return the response with CORS headers
        return {
            'statusCode': status_code,
            'headers': headers,
            'body': body
        }
        
    except Exception as e:
        # Log the full exception with traceback
        logger.error(f"Error in CORS proxy: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return an error response with CORS headers
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': str(e)})
        }
