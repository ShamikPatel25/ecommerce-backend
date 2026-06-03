"""
Centralized validation error messages.
Keep in sync with frontend: lib/validationErrors.js
"""


class ValidationErrors:
    """Validation error messages used across the application."""

    # Common
    @staticmethod
    def required(field):
        return f'{field} is required'

    @staticmethod
    def invalid_format(field):
        return f'Invalid {field} format'

    @staticmethod
    def already_exists(field):
        return f'{field} already exists'

    @staticmethod
    def not_found(field):
        return f'{field} not found'


class AuthErrors:
    """Authentication related errors."""
    EMAIL_REQUIRED = 'Email is required'
    EMAIL_INVALID = 'Please enter a valid email address'
    PASSWORD_REQUIRED = 'Password is required'
    PASSWORD_MIN_LENGTH = 'Password must be at least 8 characters'
    PASSWORD_MISMATCH = 'Passwords do not match'
    INVALID_CREDENTIALS = 'Invalid email or password'
    ACCOUNT_INACTIVE = 'Account is inactive'
    TOKEN_EXPIRED = 'Session expired. Please login again'
    UNAUTHORIZED = 'You are not authorized to perform this action'


class StoreErrors:
    """Store related errors."""
    NAME_REQUIRED = 'Store name is required'
    NAME_EXISTS = 'A store with this name already exists'
    SUBDOMAIN_REQUIRED = 'Subdomain is required'
    SUBDOMAIN_EXISTS = 'This subdomain is already taken'
    SUBDOMAIN_INVALID = 'Subdomain can only contain lowercase letters, numbers, and hyphens'
    SUBDOMAIN_RESERVED = 'This subdomain is reserved'


class CategoryErrors:
    """Category related errors."""
    NAME_REQUIRED = 'Category name is required'
    NAME_EXISTS = 'A category with this name already exists under the same parent'
    NAME_SPECIAL_CHARS = 'Special characters are not allowed in category name'
    SLUG_REQUIRED = 'Slug is required'
    SLUG_EXISTS = 'A category with this slug already exists'
    MAX_LEVEL = 'Maximum 3 levels of categories allowed'
    PARENT_NOT_FOUND = 'Parent category not found'
    PARENT_CROSS_TENANT = 'Parent category does not belong to your store'
    HAS_PRODUCTS = 'Cannot delete category with products'
    HAS_CHILDREN = 'Cannot delete category with subcategories'


class ProductErrors:
    """Product related errors."""
    NAME_REQUIRED = 'Product name is required'
    NAME_MAX_LENGTH = 'Product name cannot exceed 100 characters'
    SKU_REQUIRED = 'SKU is required'
    SKU_MAX_LENGTH = 'SKU cannot exceed 30 characters'
    SKU_EXISTS = 'Product with this SKU already exists'
    DESCRIPTION_MAX_LENGTH = 'Description cannot exceed 2000 characters'
    PRICE_REQUIRED = 'Price is required'
    PRICE_POSITIVE = 'Price must be a positive number'
    PRICE_INVALID = 'Please enter a valid price'
    PRICE_NO_DECIMAL = 'Price must be a whole number (no decimals)'
    COMPARE_PRICE_INVALID = 'Compare at price must be higher than selling price'
    COMPARE_PRICE_NO_DECIMAL = 'Compare at price must be a whole number (no decimals)'
    CATEGORY_REQUIRED = 'Category is required'
    CATEGORY_INACTIVE = 'Cannot activate product. Category is inactive. Please activate the category first'
    CATEGORY_CROSS_TENANT = 'Category does not belong to your store'
    STOCK_REQUIRED = 'Stock is required'
    STOCK_POSITIVE = 'Stock must be a positive number'
    STOCK_INTEGER = 'Stock must be a whole number'


class Limits:
    """Character limits - keep in sync with frontend."""
    PRODUCT_NAME = 100
    PRODUCT_SKU = 30
    PRODUCT_DESCRIPTION = 500
    CATEGORY_NAME = 50
    CATEGORY_SLUG = 50
    STORE_NAME = 30
    STORE_SUBDOMAIN = 30
    STORE_DESCRIPTION = 300
    ATTRIBUTE_NAME = 50
    ATTRIBUTE_VALUE = 50


class AttributeErrors:
    """Attribute related errors."""
    NAME_REQUIRED = 'Attribute name is required'
    NAME_EXISTS = 'An attribute with this name already exists'
    VALUE_REQUIRED = 'Attribute value is required'
    VALUE_EXISTS = 'This value already exists for this attribute'
    IN_USE = 'Cannot delete attribute that is in use by products'
    NOT_FOUND = 'Attribute not found'
    VALUES_NOT_FOUND = 'Some attribute values not found'


class VariantErrors:
    """Variant related errors."""
    SKU_EXISTS = 'Variant with this SKU already exists'
    PRICE_POSITIVE = 'Variant price must be a positive number'
    STOCK_POSITIVE = 'Variant stock must be a positive number'
    NO_COMBINATIONS = 'Please select attribute values to generate variants'


class OrderErrors:
    """Order related errors."""
    NOT_FOUND = 'Order not found'
    INVALID_STATUS = 'Invalid order status'
    CANNOT_UPDATE = 'Cannot update order in current status'
    INSUFFICIENT_STOCK = 'Insufficient stock for one or more items'


class MediaErrors:
    """Media related errors."""
    FILE_REQUIRED = 'Please select a file to upload'
    FILE_TOO_LARGE = 'File size exceeds maximum limit'
    INVALID_TYPE = 'Invalid file type. Allowed types: JPG, PNG, GIF, WEBP'
    UPLOAD_FAILED = 'Failed to upload file. Please try again'


class AddressErrors:
    """Address related errors."""
    LINE1_REQUIRED = 'Address line 1 is required'
    CITY_REQUIRED = 'City is required'
    STATE_REQUIRED = 'State is required'
    POSTAL_REQUIRED = 'Postal code is required'
    POSTAL_INVALID = 'Invalid postal code format'
    PHONE_REQUIRED = 'Phone number is required'
    PHONE_INVALID = 'Invalid phone number format'


class CartErrors:
    """Cart related errors."""
    ITEM_NOT_FOUND = 'Item not found in cart'
    QUANTITY_INVALID = 'Invalid quantity'
    OUT_OF_STOCK = 'This item is out of stock'
    MAX_QUANTITY = 'Maximum quantity reached'


class GenericErrors:
    """Generic errors."""
    SOMETHING_WRONG = 'Something went wrong. Please try again'
    NETWORK_ERROR = 'Network error. Please check your connection'
    SERVER_ERROR = 'Server error. Please try again later'
    FORBIDDEN = 'You do not have permission to perform this action'
