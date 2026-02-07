"""Generate YouTube thumbnail suggestions using Gemini image generation."""
from __future__ import annotations

import base64
import logging
from typing import Any

from google import genai
from google.genai import types

from ..config import settings

logger = logging.getLogger(__name__)

THUMBNAIL_MODEL = 'gemini-2.5-flash-image'

THUMBNAIL_PROMPT_TEMPLATE = """\
Generate a compelling YouTube video thumbnail image for a video titled: "{title}"

Video description/context: {description}

Requirements for the thumbnail:
- Eye-catching, bold visual design suitable for YouTube
- 16:9 aspect ratio (standard YouTube thumbnail)
- Bold, large readable text overlay showing a short hook phrase (3-5 words max) derived from the title
- Vibrant, high-contrast colors that pop on both light and dark backgrounds
- Professional quality, modern YouTube style
- Include a dramatic or intriguing visual element related to the topic
- Style similar to popular science/education YouTube channels like Veritasium, Vsauce, or Kurzgesagt
- Do NOT include any YouTube UI elements (play button, progress bar, etc.)
"""


def generate_thumbnail(title: str, description: str = '') -> dict[str, Any]:
    """Generate a thumbnail image using Gemini's image generation model.

    Returns dict with 'image_base64' and 'mime_type'.
    """
    if not settings.gemini_api_key:
        raise RuntimeError('GEMINI_API_KEY is required for thumbnail generation')

    client = genai.Client(api_key=settings.gemini_api_key)

    prompt = THUMBNAIL_PROMPT_TEMPLATE.format(
        title=title,
        description=description or title,
    )

    logger.info('Generating thumbnail for: %s', title)

    response = client.models.generate_content(
        model=THUMBNAIL_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=['Image'],
            image_config=types.ImageConfig(
                aspect_ratio='16:9',
            ),
        ),
    )

    # Extract image from response parts
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            image_bytes = part.inline_data.data
            mime = part.inline_data.mime_type or 'image/png'
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            logger.info('Thumbnail generated successfully (%d bytes)', len(image_bytes))
            return {
                'image_base64': image_b64,
                'mime_type': mime,
            }

    raise RuntimeError('Gemini did not return an image in the response')
