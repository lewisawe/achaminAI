import boto3
import json
import base64
import io
import os
import logging
from typing import Dict, Optional, Tuple
import tempfile
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioMixer:
    """Audio mixing utility for combining narration and background music"""
    
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.generated_content_bucket = os.environ.get('GENERATED_CONTENT_BUCKET')
        self.music_bucket = os.environ.get('MUSIC_BUCKET')
        
    def mix_audio(self, narration_url: str, music_style: str, request_id: str) -> str:
        """
        Mix narration audio with background music
        
        Args:
            narration_url: S3 URL of the narration audio
            music_style: Style of background music to use
            request_id: Unique request identifier
            
        Returns:
            S3 URL of the mixed audio file
        """
        try:
            # Download narration audio
            narration_audio = self._download_audio(narration_url)
            
            # Get background music
            background_music = self._get_background_music(music_style)
            
            # Mix audio files
            mixed_audio = self._mix_audio_files(narration_audio, background_music)
            
            # Upload mixed audio
            mixed_audio_url = self._upload_mixed_audio(mixed_audio, request_id)
            
            return mixed_audio_url
            
        except Exception as e:
            logger.error(f"Error mixing audio: {e}")
            # Return original narration if mixing fails
            return narration_url
    
    def _download_audio(self, audio_url: str) -> bytes:
        """Download audio file from S3"""
        try:
            # Extract bucket and key from URL
            if 's3.amazonaws.com' in audio_url:
                # Handle S3 URLs
                parts = audio_url.split('/')
                bucket = parts[2].split('.')[0]
                key = '/'.join(parts[3:])
            else:
                # Handle pre-signed URLs
                parts = audio_url.split('/')
                bucket = parts[2]
                key = '/'.join(parts[3:])
            
            response = self.s3.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
            
        except Exception as e:
            logger.error(f"Error downloading audio: {e}")
            raise
    
    def _get_background_music(self, music_style: str) -> bytes:
        """Get background music based on style"""
        try:
            # Music style mappings
            music_files = {
                'ambient_world': ['world_ambient_1.mp3', 'world_ambient_2.mp3', 'world_ambient_3.mp3'],
                'ethereal_ambient': ['ethereal_1.mp3', 'ethereal_2.mp3', 'ethereal_3.mp3'],
                'traditional_folk': ['folk_traditional_1.mp3', 'folk_traditional_2.mp3', 'folk_traditional_3.mp3'],
                'epic_orchestral': ['epic_orchestral_1.mp3', 'epic_orchestral_2.mp3', 'epic_orchestral_3.mp3'],
                'warm_acoustic': ['warm_acoustic_1.mp3', 'warm_acoustic_2.mp3', 'warm_acoustic_3.mp3']
            }
            
            available_files = music_files.get(music_style, music_files['ambient_world'])
            music_file = available_files[0]  # Use first available file
            
            response = self.s3.get_object(
                Bucket=self.music_bucket,
                Key=f'background_music/{music_file}'
            )
            return response['Body'].read()
            
        except Exception as e:
            logger.error(f"Error getting background music: {e}")
            # Return empty bytes if music not available
            return b''
    
    def _mix_audio_files(self, narration_audio: bytes, background_music: bytes) -> bytes:
        """Mix narration and background music using ffmpeg"""
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as narration_file:
                narration_file.write(narration_audio)
                narration_path = narration_file.name
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as music_file:
                music_file.write(background_music)
                music_path = music_file.name
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as output_file:
                output_path = output_file.name
            
            # Use ffmpeg to mix audio (if available)
            if self._is_ffmpeg_available():
                return self._mix_with_ffmpeg(narration_path, music_path, output_path)
            else:
                # Fallback: return narration only
                logger.warning("ffmpeg not available, returning narration only")
                return narration_audio
                
        except Exception as e:
            logger.error(f"Error mixing audio files: {e}")
            return narration_audio
        finally:
            # Clean up temporary files
            for path in [narration_path, music_path, output_path]:
                if os.path.exists(path):
                    os.unlink(path)
    
    def _is_ffmpeg_available(self) -> bool:
        """Check if ffmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _mix_with_ffmpeg(self, narration_path: str, music_path: str, output_path: str) -> bytes:
        """Mix audio using ffmpeg"""
        try:
            # Mix narration (volume 1.0) with background music (volume 0.3)
            cmd = [
                'ffmpeg',
                '-i', narration_path,
                '-i', music_path,
                '-filter_complex', '[0:a]volume=1.0[narration];[1:a]volume=0.3[music];[narration][music]amix=inputs=2:duration=longest',
                '-c:a', 'mp3',
                '-b:a', '192k',
                output_path,
                '-y'  # Overwrite output file
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Read the mixed audio
            with open(output_path, 'rb') as f:
                return f.read()
                
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg error: {e}")
            # Return narration only if mixing fails
            with open(narration_path, 'rb') as f:
                return f.read()
    
    def _upload_mixed_audio(self, mixed_audio: bytes, request_id: str) -> str:
        """Upload mixed audio to S3 and return URL"""
        try:
            key = f'audio/mixed/{request_id}.mp3'
            
            self.s3.put_object(
                Bucket=self.generated_content_bucket,
                Key=key,
                Body=mixed_audio,
                ContentType='audio/mpeg'
            )
            
            # Generate pre-signed URL
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.generated_content_bucket,
                    'Key': key
                },
                ExpiresIn=3600
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Error uploading mixed audio: {e}")
            raise

def lambda_handler(event, context):
    """Lambda handler for audio mixing"""
    try:
        # Parse input
        narration_url = event.get('narration_url')
        music_style = event.get('music_style', 'ambient_world')
        request_id = event.get('request_id')
        
        if not narration_url or not request_id:
            raise ValueError("Missing required parameters: narration_url and request_id")
        
        # Mix audio
        mixer = AudioMixer()
        mixed_audio_url = mixer.mix_audio(narration_url, music_style, request_id)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'mixed_audio_url': mixed_audio_url,
                'request_id': request_id,
                'music_style': music_style
            })
        }
        
    except Exception as e:
        logger.error(f"Error in audio mixer lambda: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        } 