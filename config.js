// Configuration file for Achamin - Cultural Understanding Through AI
// Production-ready configuration with environment variable support

const config = {
  // API URL for the Cultural Harmony application
  // Can be overridden by environment variable
  API_URL: process.env.ACHAMIN_API_URL || process.env.API_URL || 'https://your-api-gateway-id.execute-api.us-west-2.amazonaws.com/prod/analyze',
  
  // AWS Configuration
  AWS_REGION: process.env.AWS_REGION || 'us-west-2',
  AWS_PROFILE: process.env.AWS_PROFILE || 'default',
  
  // AWS Resource Names (configurable via environment variables)
  LAMBDA_FUNCTION_NAME: process.env.LAMBDA_FUNCTION_NAME || 'your-cultural-harmony-function',
  API_GATEWAY_NAME: process.env.API_GATEWAY_NAME || 'your-achamin-api',
  UPLOAD_BUCKET: process.env.UPLOAD_BUCKET || 'your-achamin-uploads-bucket',
  GENERATED_CONTENT_BUCKET: process.env.GENERATED_CONTENT_BUCKET || 'your-achamin-generated-content-bucket',
  
  // Application settings
  APP_NAME: 'Achamin',
  APP_VERSION: '1.0.0',
  
  // Feature flags
  FEATURES: {
    UNIQUE_NARRATION: process.env.ENABLE_UNIQUE_NARRATION !== 'false',
    NEURAL_ENGINE: process.env.ENABLE_NEURAL_ENGINE !== 'false',
    MULTI_VOICE: process.env.ENABLE_MULTI_VOICE !== 'false',
    CULTURAL_CONTEXT: process.env.ENABLE_CULTURAL_CONTEXT !== 'false'
  },
  
  // Audio settings
  AUDIO: {
    FORMAT: process.env.AUDIO_FORMAT || 'mp3',
    ENGINE: process.env.AUDIO_ENGINE || 'neural',
    EXPIRY_HOURS: parseInt(process.env.AUDIO_EXPIRY_HOURS) || 1
  },
  
  // Error handling
  ERROR_HANDLING: {
    RETRY_ATTEMPTS: parseInt(process.env.RETRY_ATTEMPTS) || 3,
    TIMEOUT_MS: parseInt(process.env.API_TIMEOUT_MS) || 30000,
    SHOW_DETAILED_ERRORS: process.env.SHOW_DETAILED_ERRORS === 'true' || process.env.NODE_ENV === 'development'
  }
};

// Validate configuration
function validateConfig() {
  const required = ['API_URL'];
  const missing = required.filter(key => !config[key]);
  
  if (missing.length > 0) {
    console.error('Missing required configuration:', missing);
    return false;
  }
  
  // Warn about default values in production
  if (process.env.NODE_ENV === 'production') {
    const defaults = [];
    if (config.API_URL.includes('your-api-gateway-id')) {
      defaults.push('API_URL (using default placeholder)');
    }
    if (config.AWS_PROFILE === 'default') {
      defaults.push('AWS_PROFILE (using default)');
    }
    
    if (defaults.length > 0) {
      console.warn('⚠️  Using default values in production:', defaults.join(', '));
    }
  }
  
  return true;
}

// Export configuration
if (typeof module !== 'undefined' && module.exports) {
  module.exports = config;
} else {
  // Browser environment
  window.config = config;
}

// Validate on load
if (typeof window !== 'undefined') {
  validateConfig();
}
