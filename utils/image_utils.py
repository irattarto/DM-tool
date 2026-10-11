"""
Image processing utilities for RPG Database Manager.
"""

import os
import base64
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont
import io

from utils.logger import get_logger

logger = get_logger('image_utils')


class ImageUtils:
    """
    Utility class for image processing and manipulation.

    Provides common image processing functions used throughout
    the RPG Database Manager application.
    """

    @staticmethod
    def validate_image_file(file_path: str) -> bool:
        """Check if file is a valid image."""
        if not os.path.exists(file_path):
            return False

        try:
            with Image.open(file_path) as img:
                img.verify()
            return True
        except Exception as e:
            logger.warning(f"Invalid image file '{file_path}': {e}")
            return False

    @staticmethod
    def get_image_size(file_path: str) -> Optional[Tuple[int, int]]:
        """Get image dimensions."""
        try:
            with Image.open(file_path) as img:
                return img.size
        except Exception as e:
            logger.warning(f"Could not get image size for '{file_path}': {e}")
            return None

    @staticmethod
    def resize_image(file_path: str, max_width: int, max_height: int, output_path: str) -> bool:
        """Resize image while maintaining aspect ratio."""
        try:
            with Image.open(file_path) as img:
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                img.save(output_path)
                return True
        except Exception as e:
            logger.error(f"Failed to resize image '{file_path}' -> '{output_path}': {e}", exc_info=True)
            return False

    @staticmethod
    def create_thumbnail(file_path: str, size: Tuple[int, int], output_path: str) -> bool:
        """Create a thumbnail of specified size."""
        try:
            with Image.open(file_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)

                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                img.save(output_path)
                return True
        except Exception as e:
            logger.error(f"Failed to create thumbnail for '{file_path}': {e}", exc_info=True)
            return False

    @staticmethod
    def image_to_base64(file_path: str, format: str = 'PNG') -> Optional[str]:
        """Convert image to base64 string."""
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Save to bytes buffer
                buffer = io.BytesIO()
                img.save(buffer, format=format)
                buffer.seek(0)

                # Convert to base64
                img_bytes = buffer.getvalue()
                base64_string = base64.b64encode(img_bytes).decode('utf-8')
                return f"data:image/{format.lower()};base64,{base64_string}"
        except Exception as e:
            logger.warning(f"Failed to convert image to base64 '{file_path}': {e}")
            return None

    @staticmethod
    def base64_to_image(base64_string: str, output_path: str) -> bool:
        """Convert base64 string to image file."""
        try:
            # Extract base64 data if data URL format
            if ',' in base64_string:
                base64_string = base64_string.split(',')[1]

            # Decode base64
            img_data = base64.b64decode(base64_string)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Save image
            with open(output_path, 'wb') as f:
                f.write(img_data)

            return True
        except Exception as e:
            logger.error(f"Failed to write image from base64 to '{output_path}': {e}", exc_info=True)
            return False

    @staticmethod
    def get_image_info(file_path: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive image information."""
        try:
            with Image.open(file_path) as img:
                info = {
                    'format': img.format,
                    'size': img.size,
                    'mode': img.mode,
                    'has_transparency': img.mode in ('RGBA', 'LA', 'P'),
                }

                # Add EXIF data if available
                if hasattr(img, '_getexif') and img._getexif() is not None:
                    info['exif'] = img._getexif()

                return info
        except Exception as e:
            logger.warning(f"Failed to get image info for '{file_path}': {e}")
            return None

    @staticmethod
    def create_placeholder_image(width: int, height: int, output_path: str, text: str = "No Image",
                               background_color: str = "#CCCCCC", text_color: str = "#666666") -> bool:
        """Create a placeholder image with text."""
        try:
            # Create image
            img = Image.new('RGB', (width, height), background_color)
            draw = ImageDraw.Draw(img)

            # Try to use a default font, fallback to basic
            try:
                # Try different font sizes
                for font_size in [48, 36, 24, 18, 14]:
                    try:
                        font = ImageFont.load_default()
                        # For default font, we can't easily change size, so we'll use it as is
                        break
                    except Exception:
                        continue
            except Exception:
                font = None

            # Calculate text position for centering
            if font:
                # For default font, approximate the size
                text_width = len(text) * 20  # Rough approximation
                text_height = 24
            else:
                text_width = len(text) * 10
                text_height = 12

            x = (width - text_width) // 2
            y = (height - text_height) // 2

            # Draw text
            draw.text((x, y), text, fill=text_color)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Save image
            img.save(output_path)
            return True
        except Exception as e:
            logger.error(f"Failed to create placeholder image at '{output_path}': {e}", exc_info=True)
            return False

    @staticmethod
    def compress_image(file_path: str, quality: int = 85, output_path: str = None) -> bool:
        """Compress image to reduce file size."""
        if output_path is None:
            output_path = file_path

        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary for JPEG compression
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create a white background
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode in ('P', 'LA'):
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Save with compression
                img.save(output_path, 'JPEG', quality=quality, optimize=True)
                return True
        except Exception as e:
            logger.error(f"Failed to compress image '{file_path}' -> '{output_path}': {e}", exc_info=True)
            return False

    @staticmethod
    def get_supported_formats() -> list:
        """Get list of supported image formats."""
        return ['PNG', 'JPEG', 'JPG', 'BMP', 'TIFF', 'GIF', 'WEBP']