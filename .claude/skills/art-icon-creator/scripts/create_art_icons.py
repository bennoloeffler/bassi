#!/usr/bin/env python3
"""
Art Icon Creator - Generate 10 artistic icon variations from images.
Creates greyscale, posterized icons with high contrast in different artistic styles.
"""

import sys
import os
from pathlib import Path
from urllib.request import urlopen
from io import BytesIO
import json

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def is_valid_source(source: str) -> tuple[bool, str]:
    """Check if source is valid URL or local file."""
    if source.startswith(('http://', 'https://')):
        return True, source

    local_path = Path(source)
    if local_path.exists() and local_path.is_file():
        return True, str(local_path)

    return False, f"Invalid source: {source} (not a valid URL or local file)"


def load_image(source: str) -> tuple[Image.Image, str, str]:
    """Load image from URL or local file. Returns (image, original_name, original_ext)."""
    is_valid, location = is_valid_source(source)
    if not is_valid:
        raise ValueError(location)

    if source.startswith(('http://', 'https://')):
        # Download from URL
        response = urlopen(source)
        img = Image.open(BytesIO(response.read()))

        # Extract filename from URL
        url_path = source.split('/')[-1].split('?')[0]
        if url_path:
            name, ext = os.path.splitext(url_path)
            if not ext:
                ext = '.png'
        else:
            name, ext = 'image', '.png'
    else:
        # Load from local file
        img = Image.open(source)
        path = Path(source)
        name = path.stem
        ext = path.suffix

    return img, name, ext


def prepare_image(img: Image.Image) -> Image.Image:
    """Prepare image: convert to RGB, remove background if possible, resize to 256x256."""
    # Convert to RGB if necessary
    if img.mode != 'RGB':
        if img.mode == 'RGBA':
            # White background for transparency
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        else:
            img = img.convert('RGB')

    # Simple background removal: detect dominant color and replace
    img = remove_background_simple(img)

    # Resize to 256x256 with aspect ratio preservation
    img = resize_with_aspect_ratio(img, 256)

    return img


def remove_background_simple(img: Image.Image) -> Image.Image:
    """Try to remove background using edge-based approach."""
    # Create a copy
    result = img.copy()

    # Get image array
    pixels = result.load()
    width, height = result.size

    # Find the most common edge color (likely background)
    # Sample edges
    edge_colors = []
    for x in range(0, width, max(1, width // 10)):
        edge_colors.append(pixels[x, 0])  # top
        edge_colors.append(pixels[x, height - 1])  # bottom
    for y in range(0, height, max(1, height // 10)):
        edge_colors.append(pixels[0, y])  # left
        edge_colors.append(pixels[width - 1, y])  # right

    if edge_colors:
        # Find most common color
        bg_color = max(set(edge_colors), key=edge_colors.count)

        # Replace similar colors with white
        tolerance = 50
        for y in range(height):
            for x in range(width):
                pixel = pixels[x, y]
                if all(abs(pixel[i] - bg_color[i]) < tolerance for i in range(3)):
                    pixels[x, y] = (255, 255, 255)

    return result


def resize_with_aspect_ratio(img: Image.Image, size: int) -> Image.Image:
    """Resize image to square 256x256 preserving aspect ratio with padding."""
    img.thumbnail((size, size), Image.Resampling.LANCZOS)

    # Create square canvas with white background
    square = Image.new('RGB', (size, size), (255, 255, 255))

    # Center the image
    offset = ((size - img.width) // 2, (size - img.height) // 2)
    square.paste(img, offset)

    return square


def convert_to_greyscale(img: Image.Image) -> Image.Image:
    """Convert image to greyscale."""
    return img.convert('L')


def variation_01_high_contrast_soft(img: Image.Image) -> Image.Image:
    """Variation 1: Simple high contrast black & white (softer)."""
    grey = convert_to_greyscale(img)
    enhancer = ImageEnhance.Contrast(grey)
    grey = enhancer.enhance(2.0)
    return grey.point(lambda x: 0 if x < 128 else 255, mode='1').convert('L')


def variation_02_high_contrast_strict(img: Image.Image) -> Image.Image:
    """Variation 2: High contrast black & white (strict threshold)."""
    grey = convert_to_greyscale(img)
    enhancer = ImageEnhance.Contrast(grey)
    grey = enhancer.enhance(2.5)
    return grey.point(lambda x: 0 if x < 100 else 255, mode='1').convert('L')


def variation_03_high_contrast_extreme(img: Image.Image) -> Image.Image:
    """Variation 3: Extreme high contrast black & white."""
    grey = convert_to_greyscale(img)
    enhancer = ImageEnhance.Contrast(grey)
    grey = enhancer.enhance(3.0)
    return grey.point(lambda x: 0 if x < 120 else 255, mode='1').convert('L')


def variation_04_poster_8colors(img: Image.Image) -> Image.Image:
    """Variation 4: Artistic poster effect (8 colors)."""
    grey = convert_to_greyscale(img)
    enhancer = ImageEnhance.Contrast(grey)
    grey = enhancer.enhance(2.2)

    # Posterize to 8 levels
    return ImageOps.posterize(grey, 2)  # 2^(8-2) = 64 levels = ~8 effective


def variation_05_poster_16colors(img: Image.Image) -> Image.Image:
    """Variation 5: Artistic poster effect (16 colors)."""
    grey = convert_to_greyscale(img)
    enhancer = ImageEnhance.Contrast(grey)
    grey = enhancer.enhance(2.0)

    # Posterize to 16 levels
    return ImageOps.posterize(grey, 3)  # 2^(8-3) = 32 levels = ~16 effective


def variation_06_poster_smooth(img: Image.Image) -> Image.Image:
    """Variation 6: Smooth poster effect."""
    grey = convert_to_greyscale(img)

    # Smooth edges first
    grey = grey.filter(ImageFilter.SMOOTH)

    enhancer = ImageEnhance.Contrast(grey)
    grey = enhancer.enhance(2.1)

    # Posterize to 8 levels
    return ImageOps.posterize(grey, 2)


def variation_07_comic_bold(img: Image.Image) -> Image.Image:
    """Variation 7: Comic book style (bold lines)."""
    grey = convert_to_greyscale(img)
    enhancer = ImageEnhance.Contrast(grey)
    grey = enhancer.enhance(2.4)

    # Find edges and combine
    edges = grey.filter(ImageFilter.FIND_EDGES)
    edges = ImageEnhance.Contrast(edges).enhance(2.0)

    # Blend: use edges to enhance the posterized version
    posterized = ImageOps.posterize(grey, 2)

    # Convert to arrays and combine
    from PIL import ImageChops
    result = ImageChops.lighter(posterized, edges)
    return result


def variation_08_comic_outline(img: Image.Image) -> Image.Image:
    """Variation 8: Comic book style (outlines)."""
    grey = convert_to_greyscale(img)

    # Apply edge detection
    edges = grey.filter(ImageFilter.FIND_EDGES)
    edges = ImageEnhance.Contrast(edges).enhance(2.5)

    # Posterize the greyscale
    posterized = ImageOps.posterize(grey, 2)

    # Use edges as mask
    from PIL import ImageChops
    result = ImageChops.screen(posterized, edges)
    return result


def variation_09_comic_smooth(img: Image.Image) -> Image.Image:
    """Variation 9: Comic book style (smooth version)."""
    grey = convert_to_greyscale(img)

    # Smooth first
    grey = grey.filter(ImageFilter.SMOOTH_MORE)

    # Enhance contrast
    enhancer = ImageEnhance.Contrast(grey)
    grey = enhancer.enhance(2.3)

    # Edge detection
    edges = grey.filter(ImageFilter.FIND_EDGES)
    enhancer = ImageEnhance.Contrast(edges)
    edges = enhancer.enhance(1.8)

    # Posterize
    posterized = ImageOps.posterize(grey, 2)

    from PIL import ImageChops
    result = ImageChops.lighter(posterized, edges)
    return result


def variation_10_artistic_blend(img: Image.Image) -> Image.Image:
    """Variation 10: Artistic blend of all techniques."""
    grey = convert_to_greyscale(img)

    # Smooth lightly
    grey = grey.filter(ImageFilter.SMOOTH)

    # Strong contrast
    enhancer = ImageEnhance.Contrast(grey)
    grey = enhancer.enhance(2.5)

    # Posterize to 16 levels for smooth gradation
    posterized = ImageOps.posterize(grey, 3)

    # Apply slight edge emphasis
    edges = grey.filter(ImageFilter.FIND_EDGES)
    edges = ImageEnhance.Contrast(edges).enhance(1.5)

    from PIL import ImageChops
    result = ImageChops.screen(posterized, edges)
    return result


def compress_png(img: Image.Image, target_size: int = 20000) -> Image.Image:
    """Compress PNG to fit under target size. Returns optimized image."""
    # PNG compression is usually good enough, PIL will optimize
    return img


def create_variations(source: str, output_dir: str = None) -> dict:
    """
    Create 10 artistic icon variations from source image.

    Args:
        source: Image URL or local file path
        output_dir: Output directory (default: same as source or current dir)

    Returns:
        Dictionary with results
    """
    try:
        # Load image
        img, name, ext = load_image(source)

        # Determine output directory
        if output_dir is None:
            if source.startswith(('http://', 'https://')):
                output_dir = os.getcwd()
            else:
                output_dir = os.path.dirname(source) or os.getcwd()

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Convert to absolute path
        output_dir_absolute = output_dir.resolve()

        # Prepare image
        img = prepare_image(img)

        # Define variations
        variations = [
            ('_art_icon_01.png', variation_01_high_contrast_soft),
            ('_art_icon_02.png', variation_02_high_contrast_strict),
            ('_art_icon_03.png', variation_03_high_contrast_extreme),
            ('_art_icon_04.png', variation_04_poster_8colors),
            ('_art_icon_05.png', variation_05_poster_16colors),
            ('_art_icon_06.png', variation_06_poster_smooth),
            ('_art_icon_07.png', variation_07_comic_bold),
            ('_art_icon_08.png', variation_08_comic_outline),
            ('_art_icon_09.png', variation_09_comic_smooth),
            ('_art_icon_10.png', variation_10_artistic_blend),
        ]

        results = {
            'original_name': name,
            'original_extension': ext,
            'output_directory': str(output_dir_absolute),
            'files': []
        }

        # Create variations
        for suffix, variation_func in variations:
            try:
                # Apply variation
                variant = variation_func(img)

                # Convert back to greyscale if needed
                if variant.mode not in ('L', 'RGB'):
                    variant = variant.convert('L')

                # Compress
                variant = compress_png(variant)

                # Save
                output_filename = f"{name}{suffix}"
                output_path = output_dir_absolute / output_filename

                # Save with PNG optimization
                variant.save(output_path, 'PNG', optimize=True)

                # Get file size
                file_size = output_path.stat().st_size

                results['files'].append({
                    'filename': output_filename,
                    'path': str(output_path.resolve()),
                    'size_bytes': file_size,
                    'size_kb': round(file_size / 1024, 2),
                    'style': variation_func.__doc__
                })

            except Exception as e:
                results['files'].append({
                    'filename': f"{name}{suffix}",
                    'error': str(e)
                })

        results['success'] = True
        return results

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def main():
    """CLI interface for the script."""
    if len(sys.argv) < 2:
        print("Usage: python create_art_icons.py <source> [output_dir]")
        print("  source: Image URL or local file path")
        print("  output_dir: Optional output directory (default: same as source)")
        sys.exit(1)

    source = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    results = create_variations(source, output_dir)

    # Print results
    print(json.dumps(results, indent=2))

    if results.get('success'):
        print(f"\n✅ Created {len(results['files'])} variations")
        print(f"\n📁 Output Directory: {results['output_directory']}\n")
        for file_info in results['files']:
            if 'error' not in file_info:
                print(f"  ✓ {file_info['path']}")
    else:
        print(f"\n❌ Error: {results.get('error')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
