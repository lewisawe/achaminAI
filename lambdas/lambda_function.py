import json
import boto3
import uuid
import base64
import os

# Initialize AWS clients
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
polly = boto3.client('polly')

def lambda_handler(event, context):
    try:
        # Get the image data from the request
        content_type = event['headers'].get('content-type', '')
        if 'image' in content_type:
            # Handle direct image upload
            image_data = base64.b64decode(event['body'])
        else:
            # Handle JSON with base64 encoded image
            body = json.loads(event['body'])
            image_data = base64.b64decode(body['image'])
        
        # Generate unique identifier for this request
        request_id = str(uuid.uuid4())
        
        # Upload the image to S3
        image_path = f'uploads/{request_id}.jpg'
        s3.put_object(
            Bucket='your-achamin-uploads-bucket',
            Key=image_path,
            Body=image_data
        )
        
        # Step 1: Use Rekognition to analyze the image
        rekognition_response = rekognition.detect_labels(
            Image={
                'Bytes': image_data
            },
            MaxLabels=10
        )
        
        # Extract relevant labels
        labels = [label['Name'] for label in rekognition_response['Labels']]
        
        # Skip Bedrock for now and use a static cultural explanation
        cultural_explanation = f"""
        This image contains the following elements: {', '.join(labels)}.
        
        These elements have deep cultural significance in many societies. The visual representation 
        captures aspects of cultural heritage that have been passed down through generations.
        
        Historically, these elements have played important roles in ceremonies, daily life, and 
        artistic expression. They symbolize community values, spiritual beliefs, and collective identity.
        
        When appreciating these cultural elements, it's important to approach them with respect and 
        understanding of their original context and meaning.
        """
        
        # Step 3: Generate narration using Amazon Polly
        polly_response = polly.synthesize_speech(
            Text=cultural_explanation,
            OutputFormat='mp3',
            VoiceId='Joanna'
        )
        
        # Upload the generated audio to S3
        audio_path = f'audio/{request_id}.mp3'
        s3.put_object(
            Bucket='your-achamin-generated-content-bucket',
            Key=audio_path,
            Body=polly_response['AudioStream'].read()
        )
        
        # Generate a pre-signed URL for accessing the audio
        audio_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': 'your-achamin-generated-content-bucket',
                'Key': audio_path
            },
            ExpiresIn=3600
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'culturalContext': cultural_explanation,
                'audioUrl': audio_url,
                'detectedElements': labels
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
