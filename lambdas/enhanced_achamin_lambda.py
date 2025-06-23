import json
import boto3
import uuid
import base64
import os
import random
import io
import time
from typing import Dict, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS clients
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
bedrock = boto3.client('bedrock-runtime')
polly = boto3.client('polly')
dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')

# Get configuration from environment variables
UPLOAD_BUCKET = os.environ.get('UPLOAD_BUCKET', 'your-achamin-uploads-bucket')
GENERATED_CONTENT_BUCKET = os.environ.get('GENERATED_CONTENT_BUCKET', 'your-achamin-generated-content-bucket')
MUSIC_BUCKET = os.environ.get('MUSIC_BUCKET', 'your-achamin-music-bucket')
METADATA_TABLE = os.environ.get('METADATA_TABLE', 'achamin-image-metadata')
ACHAMIN_REGION = os.environ.get('ACHAMIN_REGION', 'us-west-2')

# Initialize DynamoDB table
metadata_table = dynamodb.Table(METADATA_TABLE)

class ImageMetadata:
    """Class to handle predefined image metadata and mapping"""
    
    # Predefined image themes and metadata
    PREDEFINED_IMAGES = {
        'cultural_artifacts': {
            'themes': ['heritage', 'tradition', 'artistry', 'craftsmanship'],
            'mood': 'reverent',
            'genre': 'cultural_documentary',
            'music_style': 'ambient_world',
            'story_length': 'medium',
            'voice_characteristics': ['warm', 'knowledgeable']
        },
        'ceremonial_objects': {
            'themes': ['ritual', 'spirituality', 'community', 'celebration'],
            'mood': 'mystical',
            'genre': 'spiritual_narrative',
            'music_style': 'ethereal_ambient',
            'story_length': 'long',
            'voice_characteristics': ['reverent', 'storytelling']
        },
        'traditional_clothing': {
            'themes': ['identity', 'beauty', 'social_status', 'cultural_pride'],
            'mood': 'proud',
            'genre': 'cultural_exploration',
            'music_style': 'traditional_folk',
            'story_length': 'medium',
            'voice_characteristics': ['enthusiastic', 'descriptive']
        },
        'architectural_heritage': {
            'themes': ['history', 'engineering', 'community', 'endurance'],
            'mood': 'awe_inspiring',
            'genre': 'historical_narrative',
            'music_style': 'epic_orchestral',
            'story_length': 'long',
            'voice_characteristics': ['authoritative', 'narrative']
        },
        'culinary_traditions': {
            'themes': ['nourishment', 'family', 'celebration', 'sensory_experience'],
            'mood': 'warm',
            'genre': 'sensory_story',
            'music_style': 'warm_acoustic',
            'story_length': 'short',
            'voice_characteristics': ['friendly', 'descriptive']
        }
    }
    
    @classmethod
    def get_image_metadata(cls, labels: List[str]) -> Dict:
        """Map detected labels to predefined image metadata"""
        # Analyze labels to determine image category
        label_text = ' '.join(labels).lower()
        
        # Simple keyword matching - in production, use more sophisticated NLP
        if any(word in label_text for word in ['art', 'sculpture', 'pottery', 'weaving']):
            return cls.PREDEFINED_IMAGES['cultural_artifacts']
        elif any(word in label_text for word in ['ceremony', 'ritual', 'religious', 'temple']):
            return cls.PREDEFINED_IMAGES['ceremonial_objects']
        elif any(word in label_text for word in ['clothing', 'dress', 'costume', 'textile']):
            return cls.PREDEFINED_IMAGES['traditional_clothing']
        elif any(word in label_text for word in ['building', 'architecture', 'monument', 'castle']):
            return cls.PREDEFINED_IMAGES['architectural_heritage']
        elif any(word in label_text for word in ['food', 'dish', 'cooking', 'meal']):
            return cls.PREDEFINED_IMAGES['culinary_traditions']
        else:
            # Default to cultural artifacts
            return cls.PREDEFINED_IMAGES['cultural_artifacts']

class StoryGenerator:
    """Enhanced story generation using Amazon Bedrock with Claude"""
    
    @staticmethod
    def create_enhanced_story_prompt(labels: List[str], metadata: Dict, style: str) -> str:
        """Create a sophisticated story generation prompt"""
        
        themes = metadata.get('themes', [])
        mood = metadata.get('mood', 'neutral')
        genre = metadata.get('genre', 'cultural_narrative')
        
        base_prompts = {
            "storytelling": f"""
            Create a captivating cultural story about an image containing: {', '.join(labels)}.
            
            Context:
            - Themes: {', '.join(themes)}
            - Mood: {mood}
            - Genre: {genre}
            
            Story Requirements:
            1. Begin with a compelling hook that draws the listener in
            2. Weave together the cultural significance of the detected elements
            3. Include sensory details that make the story vivid and immersive
            4. Incorporate cultural wisdom or traditional knowledge
            5. End with a meaningful reflection or lesson
            6. Use language that evokes the {mood} mood
            7. Structure as a complete narrative arc (beginning, middle, end)
            
            Make the story feel like an intimate cultural journey that connects past and present.
            """,
            
            "educational": f"""
            Create an educational cultural narrative about: {', '.join(labels)}.
            
            Context:
            - Themes: {', '.join(themes)}
            - Mood: {mood}
            - Genre: {genre}
            
            Educational Structure:
            1. Introduction: What we're looking at and why it matters
            2. Historical Context: Origins and evolution of these cultural elements
            3. Cultural Significance: What these elements mean to their community
            4. Contemporary Relevance: How these traditions continue today
            5. Global Connections: How this connects to universal human experiences
            6. Reflection: Why preserving and understanding these traditions matters
            
            Use clear, engaging language that makes complex cultural concepts accessible.
            """,
            
            "poetic": f"""
            Craft a poetic cultural reflection on: {', '.join(labels)}.
            
            Context:
            - Themes: {', '.join(themes)}
            - Mood: {mood}
            - Genre: {genre}
            
            Poetic Elements:
            1. Use vivid imagery and metaphor to capture cultural essence
            2. Employ rhythmic language that flows like poetry
            3. Connect the physical elements to spiritual and emotional dimensions
            4. Express the beauty and wisdom embedded in cultural traditions
            5. Create emotional resonance with universal human experiences
            6. Use language that honors the {mood} mood
            
            Make it feel like a cultural meditation that touches the soul.
            """,
            
            "inspirational": f"""
            Find inspiration in the cultural elements: {', '.join(labels)}.
            
            Context:
            - Themes: {', '.join(themes)}
            - Mood: {mood}
            - Genre: {genre}
            
            Inspirational Focus:
            1. Discover the creativity and ingenuity behind these traditions
            2. Highlight the resilience and adaptability of cultural practices
            3. Show how cultural diversity enriches human experience
            4. Demonstrate the power of tradition to connect generations
            5. Inspire appreciation for cultural heritage and preservation
            6. Connect to universal values of beauty, wisdom, and community
            
            Make it uplifting and motivating while honoring cultural authenticity.
            """
        }
        
        return base_prompts.get(style, base_prompts["storytelling"])

class AudioProducer:
    """Enhanced audio production with background music and mixing"""
    
    # Music style mappings
    MUSIC_STYLES = {
        'ambient_world': ['ambient_world_1.mp3', 'ambient_world_2.mp3', 'ambient_world_3.mp3'],
        'ethereal_ambient': ['ethereal_ambient_1.mp3', 'ethereal_ambient_2.mp3', 'ethereal_ambient_3.mp3'],
        'traditional_folk': ['traditional_folk_1.mp3', 'traditional_folk_2.mp3', 'traditional_folk_3.mp3'],
        'epic_orchestral': ['epic_orchestral_1.mp3', 'epic_orchestral_2.mp3', 'epic_orchestral_3.mp3'],
        'warm_acoustic': ['warm_acoustic_1.mp3', 'warm_acoustic_2.mp3', 'warm_acoustic_3.mp3']
    }
    
    # Voice mappings based on characteristics
    VOICE_MAPPINGS = {
        'warm': ['Joanna', 'Salli', 'Aditi'],
        'knowledgeable': ['Matthew', 'Justin'],
        'reverent': ['Matthew', 'Joanna'],
        'storytelling': ['Joanna', 'Matthew', 'Salli'],
        'enthusiastic': ['Salli', 'Kendra'],
        'descriptive': ['Joanna', 'Matthew'],
        'authoritative': ['Matthew', 'Justin'],
        'narrative': ['Joanna', 'Matthew'],
        'friendly': ['Salli', 'Kendra', 'Aditi']
    }
    
    @staticmethod
    def select_background_music(music_style: str) -> str:
        """Select appropriate background music based on style"""
        available_music = AudioProducer.MUSIC_STYLES.get(music_style, AudioProducer.MUSIC_STYLES['ambient_world'])
        return random.choice(available_music)
    
    @staticmethod
    def select_voice(characteristics: List[str]) -> str:
        """Select voice based on desired characteristics"""
        available_voices = []
        for characteristic in characteristics:
            if characteristic in AudioProducer.VOICE_MAPPINGS:
                available_voices.extend(AudioProducer.VOICE_MAPPINGS[characteristic])
        
        if not available_voices:
            available_voices = ['Joanna', 'Matthew']  # Default voices
        
        return random.choice(list(set(available_voices)))  # Remove duplicates
    
    @staticmethod
    def generate_narration_audio(text: str, voice_id: str) -> bytes:
        """Generate narration audio using Amazon Polly"""
        try:
            # Try with neural engine first, fall back to standard if not supported
            try:
                polly_response = polly.synthesize_speech(
                    Text=text,
                    OutputFormat='mp3',
                    VoiceId=voice_id,
                    Engine='neural',
                    TextType='text'
                )
            except Exception as neural_error:
                if "ValidationException" in str(neural_error):
                    # Fall back to standard engine
                    polly_response = polly.synthesize_speech(
                        Text=text,
                        OutputFormat='mp3',
                        VoiceId=voice_id,
                        Engine='standard',
                        TextType='text'
                    )
                else:
                    raise neural_error
                    
            return polly_response['AudioStream'].read()
        except Exception as e:
            logger.error(f"Error generating narration: {e}")
            # Return empty bytes instead of raising an exception
            return b''
    
    @staticmethod
    def get_background_music(music_file: str) -> bytes:
        """Retrieve background music from S3"""
        try:
            response = s3.get_object(
                Bucket=MUSIC_BUCKET,
                Key=f'background_music/{music_file}'
            )
            return response['Body'].read()
        except Exception as e:
            logger.error(f"Error retrieving background music: {e}")
            # Return empty bytes if music not available
            return b''

class EnhancedAchaminProcessor:
    """Main processor for enhanced cultural analysis and storytelling"""
    
    def __init__(self):
        self.image_metadata = ImageMetadata()
        self.story_generator = StoryGenerator()
        self.audio_producer = AudioProducer()
    
    def process_image(self, image_data: bytes, request_id: str) -> Dict:
        """Main processing pipeline for enhanced cultural analysis"""
        
        # Step 1: Enhanced image analysis with Rekognition
        labels = self._analyze_image(image_data)
        
        # Step 2: Get image metadata and mapping
        metadata = self.image_metadata.get_image_metadata(labels)
        
        # Step 3: Generate enhanced story using Bedrock
        story = self._generate_enhanced_story(labels, metadata)
        
        # Step 4: Create audio-visual experience
        audio_data = self._create_audio_visual_experience(story, metadata, request_id)
        
        # Step 5: Store metadata in DynamoDB
        self._store_metadata(request_id, labels, metadata, story)
        
        return {
            'culturalContext': story,
            'audioUrl': audio_data['narrationUrl'],
            'musicUrl': audio_data['musicUrl'],
            'musicFile': audio_data['musicFile'],
            'musicStyle': audio_data['musicStyle'],
            'voiceId': audio_data['voiceId'],
            'detectedElements': labels,
            'imageMetadata': metadata,
            'requestId': request_id,
            'storyLength': metadata.get('story_length', 'medium')
        }
    
    def _analyze_image(self, image_data: bytes) -> List[str]:
        """Enhanced image analysis using Rekognition"""
        try:
            # Use multiple Rekognition APIs for comprehensive analysis
            label_response = rekognition.detect_labels(
                Image={'Bytes': image_data},
                MaxLabels=15,
                MinConfidence=70
            )
            
            # Extract labels with confidence scores
            labels = []
            for label in label_response['Labels']:
                if label['Confidence'] > 80:  # High confidence labels
                    labels.append(label['Name'])
                    # Also include instances for better context
                    for instance in label.get('Instances', []):
                        if instance['Confidence'] > 80:
                            labels.append(f"{label['Name']} object")
            
            # Add cultural context labels
            cultural_labels = self._add_cultural_context(labels)
            labels.extend(cultural_labels)
            
            return list(set(labels))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error in image analysis: {e}")
            return ['cultural artifact', 'traditional object']
    
    def _add_cultural_context(self, labels: List[str]) -> List[str]:
        """Add cultural context to detected labels"""
        cultural_context = []
        label_text = ' '.join(labels).lower()
        
        # Add cultural significance based on detected objects
        if any(word in label_text for word in ['art', 'sculpture', 'painting']):
            cultural_context.extend(['cultural heritage', 'artistic tradition'])
        if any(word in label_text for word in ['clothing', 'dress', 'costume']):
            cultural_context.extend(['cultural identity', 'traditional attire'])
        if any(word in label_text for word in ['building', 'architecture']):
            cultural_context.extend(['architectural heritage', 'cultural monument'])
        if any(word in label_text for word in ['food', 'dish', 'cooking']):
            cultural_context.extend(['culinary tradition', 'cultural cuisine'])
        
        return cultural_context
    
    def _generate_enhanced_story(self, labels: List[str], metadata: Dict) -> str:
        """Generate enhanced story using Amazon Bedrock with Claude"""
        try:
            # Select story style based on metadata
            style = self._select_story_style(metadata)
            
            # Create enhanced prompt
            prompt = self.story_generator.create_enhanced_story_prompt(labels, metadata, style)
            
            # Generate story using Bedrock
            bedrock_response = bedrock.invoke_model(
                modelId='anthropic.claude-instant-v1',
                body=json.dumps({
                    "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                    "max_tokens_to_sample": 1500,
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "top_k": 250
                })
            )
            
            story = json.loads(bedrock_response['body'].read())['completion']
            
            # Post-process story for better audio narration
            story = self._optimize_for_narration(story)
            
            return story
            
        except Exception as e:
            logger.error(f"Error generating story: {e}")
            return f"A fascinating cultural story about {', '.join(labels)} that connects us to traditions and heritage."
    
    def _select_story_style(self, metadata: Dict) -> str:
        """Select appropriate story style based on metadata"""
        mood = metadata.get('mood', 'neutral')
        genre = metadata.get('genre', 'cultural_narrative')
        
        style_mapping = {
            'reverent': 'storytelling',
            'mystical': 'poetic',
            'proud': 'inspirational',
            'awe_inspiring': 'storytelling',
            'warm': 'educational'
        }
        
        return style_mapping.get(mood, 'storytelling')
    
    def _optimize_for_narration(self, story: str) -> str:
        """Optimize story text for audio narration"""
        # Add pauses for better pacing
        story = story.replace('. ', '. ... ')
        story = story.replace('! ', '! ... ')
        story = story.replace('? ', '? ... ')
        
        # Ensure proper sentence structure
        if not story.endswith(('.', '!', '?')):
            story += '.'
        
        return story
    
    def _create_audio_visual_experience(self, story: str, metadata: Dict, request_id: str) -> Dict:
        """Create complete audio-visual experience with background music"""
        try:
            # Select voice and music
            voice_characteristics = metadata.get('voice_characteristics', ['warm', 'knowledgeable'])
            voice_id = self.audio_producer.select_voice(voice_characteristics)
            
            music_style = metadata.get('music_style', 'ambient_world')
            music_file = self.audio_producer.select_background_music(music_style)
            
            # Generate narration audio
            narration_audio = self.audio_producer.generate_narration_audio(story, voice_id)
            
            # Get background music
            background_music = self.audio_producer.get_background_music(music_file)
            
            # For now, we'll store both separately and let the frontend handle mixing
            # In a production system, you'd use AWS MediaConvert or similar for audio mixing
            
            # Upload narration
            narration_path = f'audio/narration/{request_id}.mp3'
            s3.put_object(
                Bucket=GENERATED_CONTENT_BUCKET,
                Key=narration_path,
                Body=narration_audio
            )
            
            # Upload background music reference
            music_path = f'audio/background/{request_id}.json'
            music_metadata = {
                'music_file': music_file,
                'music_style': music_style,
                'voice_id': voice_id
            }
            s3.put_object(
                Bucket=GENERATED_CONTENT_BUCKET,
                Key=music_path,
                Body=json.dumps(music_metadata)
            )
            
            # Generate pre-signed URL for narration
            narration_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': GENERATED_CONTENT_BUCKET,
                    'Key': narration_path,
                    'ResponseContentType': 'audio/mpeg',
                    'ResponseContentDisposition': f'inline; filename="{request_id}.mp3"'
                },
                ExpiresIn=3600
            )
            
            # Generate pre-signed URL for background music
            music_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': MUSIC_BUCKET,
                    'Key': f'background_music/{music_file}',
                    'ResponseContentType': 'audio/mpeg',
                    'ResponseContentDisposition': f'inline; filename="{music_file}"'
                },
                ExpiresIn=3600
            )
            
            return {
                'narrationUrl': narration_url,
                'musicUrl': music_url,
                'musicFile': music_file,
                'musicStyle': music_style,
                'voiceId': voice_id
            }
            
        except Exception as e:
            logger.error(f"Error creating audio experience: {e}")
            # Return default values instead of raising an exception
            return {
                'narrationUrl': '',
                'musicUrl': '',
                'musicFile': 'ambient_world_1.mp3',
                'musicStyle': 'ambient_world',
                'voiceId': 'Joanna'
            }
    
    def _store_metadata(self, request_id: str, labels: List[str], metadata: Dict, story: str):
        """Store processing metadata in DynamoDB"""
        try:
            # Convert themes list to a string for the GSI
            themes = metadata.get('themes', [])
            themes_str = ','.join(themes) if themes else 'none'
            
            item = {
                'request_id': request_id,
                'timestamp': int(time.time()),
                'labels': labels,
                'metadata': metadata,
                'story_preview': story[:200] + '...' if len(story) > 200 else story,
                'story_length': len(story),
                'themes': themes_str,  # Store as string for GSI
                'mood': metadata.get('mood', 'neutral')
            }
            
            metadata_table.put_item(Item=item)
            
        except Exception as e:
            logger.error(f"Error storing metadata: {e}")
            # Don't fail the entire process if metadata storage fails

def lambda_handler(event, context):
    """Enhanced Lambda handler for cultural analysis and storytelling"""
    
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
        
        # Process the image with enhanced pipeline
        processor = EnhancedAchaminProcessor()
        result = processor.process_image(image_data, request_id)
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {e}")
        # Always include CORS headers, even in error responses
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': str(e)})
        } 