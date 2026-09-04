DATATYPE_MOCKS = {
    "number": {"valid": "12345", "invalid": "Not_a_number"},
    "phone number": {"valid": "+393331234567", "invalid": "call_me_maybe"},
    "boolean": {"valid": "true", "invalid": "perhaps"},
    "date": {"valid": "2026-09-03", "invalid": "tomorrow_morning"},
    "url": {"valid": "https://www.infobip.com", "invalid": "not-a-link"},
    "email": {"valid": "test@example.com", "invalid": "invalid_email_format"},
    "list": {"valid": "Item 1", "invalid": "Not_in_list"},
    "json": {"valid": '{"key": "value"}', "invalid": "Just plain text"},
    "xml": {"valid": "<tag>value</tag>", "invalid": "Just plain text"},
    
    # Complex types
    "audio": {"valid": "MOCK_AUDIO_URL", "invalid": "Text_instead_of_audio"},
    "contacts": {"valid": "MOCK_CONTACT_DATA", "invalid": "Text_instead_of_contact"},
    "document": {"valid": "MOCK_DOCUMENT_URL", "invalid": "Text_instead_of_doc"},
    "image": {"valid": "MOCK_IMAGE_URL", "invalid": "Text_instead_of_image"},
    "receive location": {"valid": "MOCK_LOCATION", "invalid": "Text_instead_of_location"},
    "send location": {"valid": "MOCK_LOCATION", "invalid": "Text_instead_of_location"},
    "video": {"valid": "MOCK_VIDEO_URL", "invalid": "Text_instead_of_video"},

    # Generic types
    "message": {"valid": "Generic message input", "invalid": None},
    "text": {"valid": "Generic text input", "invalid": None}
}