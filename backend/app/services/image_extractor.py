"""Extract images from PDF documents using PyMuPDF.

Extracted images are saved to ~/.ai-study-assistant/data/chunk_images/
and linked to their source chunks via the chunk_images table.
"""

import logging
import os
import uuid

logger = logging.getLogger(__name__)


def extract_pdf_images(pdf_path: str, output_dir: str, doc_id: str) -> list[dict]:
    """Extract images from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images
        doc_id: Document ID for organizing images

    Returns:
        List of dicts with image_path, page_num, width, height, image_type
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not available, skipping image extraction")
        return []

    images = []
    doc_dir = os.path.join(output_dir, doc_id)
    os.makedirs(doc_dir, exist_ok=True)

    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)

            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue

                    image_bytes = base_image["image"]
                    width = base_image.get("width", 0)
                    height = base_image.get("height", 0)
                    ext = base_image.get("ext", "png")

                    # Skip very small images (icons, logos)
                    if width < 50 or height < 50:
                        continue

                    img_id = str(uuid.uuid4())
                    img_filename = f"{img_id}.{ext}"
                    img_path = os.path.join(doc_dir, img_filename)

                    with open(img_path, "wb") as f:
                        f.write(image_bytes)

                    images.append({
                        "id": img_id,
                        "image_path": img_path,
                        "image_type": "image",
                        "page_num": page_num + 1,
                        "width": width,
                        "height": height,
                    })
                except Exception as e:
                    logger.warning("Failed to extract image xref=%d on page %d: %s", xref, page_num, e)

        doc.close()
        logger.info("Extracted %d images from %s", len(images), os.path.basename(pdf_path))
    except Exception as e:
        logger.warning("Failed to open PDF for image extraction: %s", e)

    return images
