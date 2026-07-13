# Image Integration Testing Playbook

Rules for validating Claude vision attachments in Jyotish AI chat.

## Image Handling Rules
- Always use base64-encoded images (or file_path with correct MIME) for tests.
- Accepted formats: **JPEG, PNG, WEBP only**.
- Do NOT use SVG, BMP, HEIC, or animated formats.
- Do NOT upload blank, solid-color, or uniform-variance images — every test image must contain real visual features (objects, edges, textures).
- If the image is not PNG/JPEG/WEBP, transcode to PNG or JPEG before upload.
- If content is animated (GIF/APNG), extract the first frame only.
- Resize large images to reasonable bounds.
- Always re-detect the MIME after any transform.

## Backend Endpoints
- POST /api/chat/attachment — multipart form; returns {url, filename, mime_type}
- POST /api/chat — accepts optional attachment_urls: List[str] (paths returned by upload)
- The chat handler passes each attachment as FileContentWithMimeType to LlmChat.stream_message().
