"""
Product utility functions.
"""


def get_product_thumbnail_url(product):
    """
    Get the thumbnail URL for a product, falling back to first image.

    Args:
        product: Product instance or None

    Returns:
        str or None: The thumbnail URL if found, None otherwise
    """
    if not product:
        return None
    thumb = product.media.filter(media_type='image', is_thumbnail=True).first()
    if not thumb:
        thumb = product.media.filter(media_type='image').first()
    if thumb and thumb.file and hasattr(thumb.file, 'url'):
        return thumb.file.url
    return None
