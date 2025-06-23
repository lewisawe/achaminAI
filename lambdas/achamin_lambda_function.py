import json
import boto3
import uuid
import base64
import os
import random

# Initialize AWS clients
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
bedrock = boto3.client('bedrock-runtime')
polly = boto3.client('polly')

# Get configuration from environment variables
UPLOAD_BUCKET = os.environ.get('UPLOAD_BUCKET', 'your-achamin-uploads-bucket')
GENERATED_CONTENT_BUCKET = os.environ.get('GENERATED_CONTENT_BUCKET', 'your-achamin-generated-content-bucket')
AWS_REGION = os.environ.get('AWS_REGION', 'us-west-2')

def get_narration_style():
    """Generate a random narration style to ensure uniqueness"""
    styles = [
        "storytelling",
        "educational",
        "conversational",
        "poetic",
        "historical",
        "personal",
        "analytical",
        "inspirational"
    ]
    return random.choice(styles)

def get_voice_id():
    """Select an appropriate voice based on cultural context"""
    voices = [
        'Joanna',  # Female, US English
        'Matthew', # Male, US English
        'Aditi',   # Female, Indian English
        'Raveena', # Female, Indian English
        'Salli',   # Female, US English
        'Justin',  # Male, US English
        'Kendra',  # Female, US English
        'Kevin'    # Male, US English
    ]
    return random.choice(voices)

def create_unique_cultural_prompt(labels, style):
    """Create a unique cultural analysis prompt based on style and content"""
    
    base_prompts = {
        "storytelling": f"""
        Tell me a captivating story about this image containing: {', '.join(labels)}.
        Imagine you're sharing this with a friend who's curious about cultural traditions.
        Include:
        - A personal anecdote or historical tale related to these elements
        - The emotional and spiritual significance
        - How these traditions connect people across generations
        - A moment of wonder or discovery
        
        Make it feel like you're sitting around a campfire sharing wisdom.
        """,
        
        "educational": f"""
        Provide an educational analysis of this image containing: {', '.join(labels)}.
        Structure your response as a cultural lesson covering:
        1. Historical origins and evolution
        2. Cultural symbolism and meaning
        3. Social functions and community roles
        4. Contemporary significance and preservation
        5. Cross-cultural connections and influences
        
        Use clear, accessible language suitable for cultural education.
        """,
        
        "conversational": f"""
        Have a friendly conversation about this image showing: {', '.join(labels)}.
        Talk about it as if you're chatting with someone who just discovered this cultural treasure.
        Share:
        - What makes these elements special and unique
        - How they reflect the values and beliefs of their culture
        - Personal reflections on their beauty and meaning
        - Ways to appreciate and respect these traditions
        
        Keep it warm, engaging, and personal.
        """,
        
        "poetic": f"""
        Create a poetic reflection on this image featuring: {', '.join(labels)}.
        Express the cultural essence through lyrical language that captures:
        - The beauty and artistry of these traditions
        - The spiritual and emotional resonance
        - The connection between past and present
        - The universal human experience they represent
        
        Use vivid imagery and emotional language.
        """,
        
        "historical": f"""
        Explore the historical journey of this image containing: {', '.join(labels)}.
        Trace the historical development including:
        - Ancient origins and early forms
        - Evolution through different periods
        - Key historical events that shaped these traditions
        - How they survived and adapted over time
        - Their role in preserving cultural memory
        
        Focus on the historical narrative and timeline.
        """,
        
        "personal": f"""
        Share a personal perspective on this image showing: {', '.join(labels)}.
        Reflect on what these cultural elements mean to you personally:
        - What emotions they evoke
        - How they connect to your own cultural experiences
        - What you find most inspiring or meaningful
        - How they remind you of universal human values
        - Your hopes for cultural preservation and understanding
        
        Make it intimate and reflective.
        """,
        
        "analytical": f"""
        Provide a detailed analysis of this image containing: {', '.join(labels)}.
        Examine the cultural elements through multiple lenses:
        - Anthropological significance and social functions
        - Artistic and aesthetic qualities
        - Economic and practical aspects
        - Religious and spiritual dimensions
        - Environmental and material considerations
        - Cross-cultural comparisons and influences
        
        Be thorough and systematic in your analysis.
        """,
        
        "inspirational": f"""
        Find inspiration in this image featuring: {', '.join(labels)}.
        Discover what makes these cultural elements inspiring:
        - The creativity and ingenuity they represent
        - The resilience and adaptability of cultural traditions
        - The beauty that emerges from cultural diversity
        - The lessons they teach about human connection
        - How they inspire us to preserve and celebrate our heritage
        
        Focus on hope, beauty, and positive cultural values.
        """
    }
    
    return base_prompts.get(style, base_prompts["conversational"])

def lambda_handler(event, context):
    # Define CORS headers
    cors_headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }
    
    # Handle preflight OPTIONS request
    if event['httpMethod'] == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': ''
        }
    
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
            Bucket=UPLOAD_BUCKET,
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
        
        # Step 2: Generate unique narration style and cultural context
        narration_style = get_narration_style()
        voice_id = get_voice_id()
        
        cultural_prompt = create_unique_cultural_prompt(labels, narration_style)
        
        # Call Bedrock to generate unique cultural context
        bedrock_response = bedrock.invoke_model(
            modelId='anthropic.claude-v3.7',
            body=json.dumps({
                "prompt": f"\n\nHuman: {cultural_prompt}\n\nAssistant:",
                "max_tokens_to_sample": 1200,
                "temperature": 0.8  # Slightly higher temperature for more variety
            })
        )
        
        cultural_explanation = json.loads(bedrock_response['body'].read())['completion']
        
        # Step 3: Generate unique narration using Amazon Polly
        polly_response = polly.synthesize_speech(
            Text=cultural_explanation,
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine='neural'  # Use neural engine for better quality
        )
        
        # Upload the generated audio to S3
        audio_path = f'audio/{request_id}.mp3'
        s3.put_object(
            Bucket=GENERATED_CONTENT_BUCKET,
            Key=audio_path,
            Body=polly_response['AudioStream'].read()
        )
        
        # Generate a pre-signed URL for accessing the audio
        audio_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': GENERATED_CONTENT_BUCKET,
                'Key': audio_path
            },
            ExpiresIn=3600
        )
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'culturalContext': cultural_explanation,
                'audioUrl': audio_url,
                'detectedElements': labels,
                'narrationStyle': narration_style,
                'voiceId': voice_id,
                'requestId': request_id
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': str(e)})
        }