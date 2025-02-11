"""
Simple test script to verify OpenAI API functionality
"""
import os
import logging
from openai import OpenAI

from llm_quest_benchmark.constants import MODEL_CHOICES, DEFAULT_MODEL

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_openai():
    """Test basic OpenAI API functionality"""
    try:
        # Get API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable not set")
            return False

        # Initialize client
        client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized")

        # Test simple completion
        prompt = "What is 2+2? Answer with just the number."
        logger.info(f"Testing prompt: {prompt}")

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using gpt-4o-mini as specified
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            temperature=0
        )

        answer = response.choices[0].message.content.strip()
        logger.info(f"Response: {answer}")

        return answer == "4"
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False

def main():
    """Main test function"""
    logger.info("Starting OpenAI API test...")
    logger.info(f"Using model: gpt-4o-mini (default model in constants: {DEFAULT_MODEL})")

    # Print API key status (without the actual key)
    api_key = os.getenv('OPENAI_API_KEY')
    logger.info(f"OpenAI API key is {'set' if api_key else 'not set'}")

    success = test_openai()

    if success:
        logger.info("Test completed successfully!")
    else:
        logger.error("Test failed!")
        exit(1)

if __name__ == "__main__":
    main()